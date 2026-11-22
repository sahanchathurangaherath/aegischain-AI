import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any
import yaml

AEGIS_AI_DIR = Path(__file__).resolve().parents[2]
if str(AEGIS_AI_DIR) not in sys.path:
    sys.path.insert(0, str(AEGIS_AI_DIR))

from config.settings import settings
from harness.context import build_context
from harness.loop import run_agent_loop
from prompts.registry import load_prompt
from providers.llm import LLMResponse, ReplayProvider, ToolCall, get_provider


def _build_replay_provider_for_scenario(scenario: dict[str, Any]) -> ReplayProvider:
    expect = scenario["expect"]
    responses: list[LLMResponse] = []
    for idx, tool_name in enumerate(expect.get("tools_called", [])):
        args: dict[str, Any]
        if tool_name == "propose_purchase_order":
            args = {
                "product_code": scenario["event_payload"].get("product_code", "RM-STEEL-001"),
                "warehouse_code": scenario["event_payload"].get("warehouse_code", "WH-MAIN-01"),
                "supplier_code": scenario.get("entity_memory", {}).get("supplier_code", "SUP-001"),
                "quantity": 200,
                "justification": "Automated eval proposal based on stockout risk.",
            }
        elif tool_name == "get_supplier_risk":
            args = {"supplier_code": scenario["event_payload"].get("supplier_code", "SUP-001")}
        else:
            args = {
                "product_code": scenario["event_payload"].get("product_code", "RM-STEEL-001"),
                "warehouse_code": scenario["event_payload"].get("warehouse_code", "WH-MAIN-01"),
            }
        responses.append(
            LLMResponse(
                content=f"Calling {tool_name}.",
                tool_calls=[ToolCall(id=f"eval_{idx}", name=tool_name, arguments=args)],
                tokens_in=150,
                tokens_out=35,
                model_name="replay-eval",
            )
        )

    citations = []
    if scenario.get("episodic_items"):
        citations.append(f"[Assessment:{scenario['episodic_items'][0]['id']}]")
    if scenario.get("semantic_chunks"):
        c = scenario["semantic_chunks"][0]
        citations.append(f"[Doc:{c['document_id']}:Chunk:{c['chunk_index']}]")
    cite_str = " ".join(citations) or "[Assessment:0]"

    responses.append(
        LLMResponse(
            content=f"Evaluation conclusion for {scenario['id']} grounded in {cite_str}.",
            tool_calls=[],
            tokens_in=200,
            tokens_out=40,
            model_name="replay-eval",
        )
    )
    return ReplayProvider(responses)


async def run_eval_suite(
    scenarios_path: Path,
    ablate: str = "none",
    use_live_provider: bool = False,
) -> dict[str, Any]:
    raw = yaml.safe_load(scenarios_path.read_text(encoding="utf-8"))
    scenarios = raw["scenarios"]
    baseline = raw.get("baseline", {})
    prompt = load_prompt("system2_deliberate")

    tool_hits = 0
    tool_total = 0
    write_matches = 0
    citation_passes = 0
    total_cost = 0.0
    latencies: list[float] = []
    per_case: list[dict[str, Any]] = []

    for sc in scenarios:
        entity_mem = {} if ablate == "entity" else sc.get("entity_memory", {})
        episodic = [] if ablate == "episodic" else sc.get("episodic_items", [])
        semantic = [] if ablate == "semantic" else sc.get("semantic_chunks", [])

        assembled = build_context(
            system_prompt=prompt.system_prompt,
            event_payload=sc["event_payload"],
            live_state=sc["live_state"],
            entity_memory=entity_mem,
            episodic_items=episodic,
            semantic_chunks=semantic,
        )

        provider = get_provider() if use_live_provider else _build_replay_provider_for_scenario(sc)
        result = await run_agent_loop(
            event_id=f"eval-{sc['id']}",
            trigger_reason=sc["trigger_reason"],
            prompt_version=prompt.prompt_version,
            assembled=assembled,
            provider=provider,
        )

        called_names = {tc["tool"] for tc in result.tool_calls}
        expected_tools = set(sc["expect"].get("tools_called", []))
        matched_tools = len(expected_tools & called_names)
        tool_hits += matched_tools
        tool_total += max(1, len(expected_tools))

        proposed_write = result.proposed_action is not None
        if proposed_write == bool(sc["expect"].get("proposes_write", False)):
            write_matches += 1

        cites_ok = len(result.citations) >= int(sc["expect"].get("cites_minimum", 1))
        if cites_ok:
            citation_passes += 1

        total_cost += result.cost_usd
        latencies.append(result.latency_ms)
        per_case.append(
            {
                "id": sc["id"],
                "tools_called": sorted(called_names),
                "proposed_write": proposed_write,
                "citations": result.citations,
                "terminated_by": result.terminated_by,
                "latency_ms": result.latency_ms,
            }
        )

    n = max(1, len(scenarios))
    latencies.sort()
    p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else 0.0

    summary = {
        "ablate": ablate,
        "provider": settings.LLM_PROVIDER if use_live_provider else "replay",
        "prompt_version": prompt.prompt_version,
        "cases": len(scenarios),
        "tool_selection_accuracy": round(tool_hits / max(1, tool_total), 4),
        "write_proposal_accuracy": round(write_matches / n, 4),
        "citation_rate": round(citation_passes / n, 4),
        "avg_cost_usd": round(total_cost / n, 6),
        "p95_latency_ms": round(p95, 2),
        "baseline_gate": baseline,
        "results": per_case,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AegisChain System 2 evaluation suite.")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path(__file__).resolve().parent / "scenarios.yaml",
    )
    parser.add_argument(
        "--ablate",
        choices=["none", "episodic", "semantic", "entity"],
        default="none",
    )
    parser.add_argument("--live", action="store_true", help="Use configured LLM_PROVIDER instead of replay.")
    args = parser.parse_args()

    report = asyncio.run(run_eval_suite(args.scenarios, ablate=args.ablate, use_live_provider=args.live))
    print(json.dumps(report, indent=2))

    min_tool_acc = report["baseline_gate"].get("min_tool_selection_accuracy", 0.0)
    if args.ablate == "none" and report["tool_selection_accuracy"] < min_tool_acc:
        print(
            f"EVAL GATE FAILED: tool_selection_accuracy={report['tool_selection_accuracy']} < {min_tool_acc}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
