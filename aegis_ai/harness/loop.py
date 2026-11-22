from dataclasses import dataclass, field
import re
import time
from typing import Any
import structlog

from config.settings import settings
from harness.blackboard import Blackboard
from harness.context import AssembledContext, compact_tool_output
import harness.tools.erp_tools  # noqa: F401 - registers default ERP tools
from harness.tools.registry import dispatch_tool, list_llm_tools
from providers.llm import LLMProvider, Message, get_provider

logger = structlog.get_logger(__name__)

_CITATION_PATTERN = re.compile(r"\[(Assessment:[^\]]+|Doc:[^\]]+)\]")


def extract_citations(text: str) -> list[str]:
    return list(dict.fromkeys(_CITATION_PATTERN.findall(text or "")))


@dataclass
class DeliberationResult:
    event_id: str
    trigger_reason: str
    prompt_version: str
    model_name: str
    conclusion: str
    proposed_action: dict[str, Any] | None = None
    citations: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    assembled_context: dict[str, Any] = field(default_factory=dict)
    blackboard: dict[str, Any] = field(default_factory=dict)
    terminated_by: str = "completed"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


async def run_agent_loop(
    *,
    event_id: str,
    trigger_reason: str,
    prompt_version: str,
    assembled: AssembledContext,
    provider: LLMProvider | None = None,
    allowed_tools: list[str] | None = None,
    max_steps: int | None = None,
    max_wall_s: float | None = None,
    max_tokens: int | None = None,
) -> DeliberationResult:
    """
    Bounded System 2 reasoning loop with hard caps on steps, wall time, and tokens.
    Every cap exits cleanly with `terminated_by` populated.
    """
    llm = provider or get_provider()
    step_limit = max_steps or settings.MAX_DELIBERATION_STEPS
    wall_limit = max_wall_s or settings.MAX_DELIBERATION_WALL_S
    token_limit = max_tokens or settings.MAX_DELIBERATION_TOKENS

    tools = list_llm_tools(allowed_tools)
    blackboard = Blackboard(event_id=event_id)
    messages: list[Message] = [
        Message(role="system", content=assembled.system_prompt),
        Message(role="user", content=assembled.user_prompt),
    ]

    tool_trace: list[dict[str, Any]] = []
    proposed_action: dict[str, Any] | None = None
    last_content = ""
    total_in = 0
    total_out = 0
    total_cost = 0.0
    model_name = settings.LLM_MODEL
    terminated_by = "completed"

    start = time.perf_counter()

    for step in range(1, step_limit + 1):
        elapsed = time.perf_counter() - start
        if elapsed >= wall_limit:
            terminated_by = "max_wall_time"
            logger.warning("deliberation_wall_time_cap", event_id=event_id, elapsed_s=round(elapsed, 2))
            break

        if (total_in + total_out) >= token_limit:
            terminated_by = "max_tokens"
            logger.warning("deliberation_token_cap", event_id=event_id, tokens=total_in + total_out)
            break

        response = await llm.complete(messages=messages, tools=tools)
        total_in += response.tokens_in
        total_out += response.tokens_out
        total_cost += response.cost_usd
        if response.model_name:
            model_name = response.model_name
        if response.content:
            last_content = response.content

        if not response.tool_calls:
            terminated_by = "completed"
            break

        messages.append(Message(role="assistant", content=response.content or ""))

        for call in response.tool_calls:
            result = await dispatch_tool(call.name, call.arguments)
            tool_trace.append(
                {
                    "step": step,
                    "tool": call.name,
                    "arguments": call.arguments,
                    "ok": result.ok,
                    "proposed": result.proposed,
                    "executed": result.executed,
                    "error": result.error,
                }
            )

            if result.proposed and not result.executed:
                proposed_action = {"tool": call.name, "payload": result.data}
                blackboard.write(agent="system2", key=f"proposal:{call.name}", value=result.data, source="proposal")
            elif result.ok:
                blackboard.write(agent=call.name, key=f"tool:{call.name}", value=result.data, source="live_erp")

            compacted = compact_tool_output(
                tool_name=call.name,
                reason=f"step_{step}_{trigger_reason}",
                data=result.data if result.ok else {"error": result.error},
            )
            messages.append(
                Message(role="tool", name=call.name, tool_call_id=call.id, content=compacted)
            )
    else:
        terminated_by = "max_steps"

    latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
    citations = extract_citations(last_content)

    logger.info(
        "deliberation_complete",
        event_id=event_id,
        prompt_version=prompt_version,
        model=model_name,
        terminated_by=terminated_by,
        tool_calls=len(tool_trace),
        citations=len(citations),
        tokens=total_in + total_out,
        cost_usd=round(total_cost, 6),
        latency_ms=latency_ms,
    )

    return DeliberationResult(
        event_id=event_id,
        trigger_reason=trigger_reason,
        prompt_version=prompt_version,
        model_name=model_name,
        conclusion=last_content,
        proposed_action=proposed_action,
        citations=citations,
        tool_calls=tool_trace,
        assembled_context={
            "allocation": assembled.allocation,
            "conflicts": assembled.conflicts,
        },
        blackboard=blackboard.snapshot(),
        terminated_by=terminated_by,
        tokens_in=total_in,
        tokens_out=total_out,
        cost_usd=round(total_cost, 6),
        latency_ms=latency_ms,
    )
