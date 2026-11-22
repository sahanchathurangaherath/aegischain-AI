from dataclasses import dataclass, field
import json
from typing import Any
import structlog

logger = structlog.get_logger(__name__)

BUDGET: dict[str, int] = {
    "system": 400,
    "event": 300,
    "state": 1_200,
    "entity": 800,
    "episodic": 1_500,
    "semantic": 2_000,
    "tools": 1_000,
    "scratch": 4_000,
}


def estimate_tokens(text: str) -> int:
    """Fast deterministic token estimate (~4 characters per token)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def truncate_to_budget(text: str, max_tokens: int) -> tuple[str, bool]:
    """Truncate a single section to its token budget without affecting other sections."""
    if estimate_tokens(text) <= max_tokens:
        return text, False
    char_limit = max(0, max_tokens * 4 - 16)
    return text[:char_limit].rstrip() + "\n...[truncated]", True


def compact_tool_output(tool_name: str, reason: str, data: dict[str, Any], max_tokens: int = 500) -> str:
    """
    Compact large tool outputs by keeping numeric metrics and keys while
    dropping verbose prose, always preserving why the tool was called.
    """
    raw = json.dumps({"tool": tool_name, "called_for": reason, "data": data}, default=str)
    if estimate_tokens(raw) <= max_tokens:
        return raw

    compact_data: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, (int, float, bool)) or v is None:
            compact_data[k] = v
        elif isinstance(v, str):
            compact_data[k] = v[:120]
        elif isinstance(v, dict):
            compact_data[k] = {
                dk: dv for dk, dv in v.items() if isinstance(dv, (int, float, bool, str))
            }
        elif isinstance(v, list):
            compact_data[k] = v[:5]

    compacted = json.dumps(
        {"tool": tool_name, "called_for": reason, "compacted": True, "data": compact_data},
        default=str,
    )
    text, _ = truncate_to_budget(compacted, max_tokens)
    return text


def resolve_state_conflicts(
    live_state: dict[str, Any],
    entity_memory: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Live ERP state always overrides stale entity memory on overlapping keys.
    Every conflict is logged for provenance and auditability.
    """
    merged_entity = dict(entity_memory)
    conflicts: list[dict[str, Any]] = []

    for key, live_val in live_state.items():
        if key in merged_entity and merged_entity[key] != live_val:
            conflicts.append(
                {
                    "field": key,
                    "live_erp_value": live_val,
                    "stale_entity_value": merged_entity[key],
                    "resolution": "live_erp_wins",
                }
            )
            logger.warning(
                "context_conflict_live_erp_wins",
                field=key,
                live_value=live_val,
                stale_entity_value=merged_entity[key],
            )
            merged_entity[key] = live_val

    return merged_entity, conflicts


@dataclass
class AssembledContext:
    system_prompt: str
    user_prompt: str
    allocation: dict[str, Any] = field(default_factory=dict)
    conflicts: list[dict[str, Any]] = field(default_factory=list)


def build_context(
    *,
    system_prompt: str,
    event_payload: dict[str, Any],
    live_state: dict[str, Any],
    entity_memory: dict[str, Any] | None = None,
    episodic_items: list[dict[str, Any]] | None = None,
    semantic_chunks: list[dict[str, Any]] | None = None,
    budget: dict[str, int] | None = None,
) -> AssembledContext:
    """
    Assemble a strictly token-budgeted deliberation context with provenance,
    conflict resolution (live ERP > entity memory), and untrusted document delimiters.
    """
    limits = {**BUDGET, **(budget or {})}
    allocation: dict[str, Any] = {}

    resolved_entity, conflicts = resolve_state_conflicts(live_state, entity_memory or {})

    sys_text, sys_trunc = truncate_to_budget(system_prompt, limits["system"])
    allocation["system"] = {"tokens": estimate_tokens(sys_text), "budget": limits["system"], "truncated": sys_trunc}

    event_text, event_trunc = truncate_to_budget(json.dumps(event_payload, default=str), limits["event"])
    allocation["event"] = {"tokens": estimate_tokens(event_text), "budget": limits["event"], "truncated": event_trunc}

    state_text, state_trunc = truncate_to_budget(json.dumps(live_state, default=str), limits["state"])
    allocation["state"] = {"tokens": estimate_tokens(state_text), "budget": limits["state"], "truncated": state_trunc}

    entity_text, entity_trunc = truncate_to_budget(json.dumps(resolved_entity, default=str), limits["entity"])
    allocation["entity"] = {"tokens": estimate_tokens(entity_text), "budget": limits["entity"], "truncated": entity_trunc}

    ep_lines: list[str] = []
    ep_tokens = 0
    ep_trunc = False
    for item in episodic_items or []:
        line = f"[Assessment:{item.get('id', 'unknown')}] {json.dumps(item, default=str)}"
        line_tokens = estimate_tokens(line)
        if ep_tokens + line_tokens > limits["episodic"]:
            ep_trunc = True
            break
        ep_lines.append(line)
        ep_tokens += line_tokens
    allocation["episodic"] = {"tokens": ep_tokens, "budget": limits["episodic"], "truncated": ep_trunc, "count": len(ep_lines)}

    sem_blocks: list[str] = []
    sem_tokens = 0
    sem_trunc = False
    for chunk in semantic_chunks or []:
        doc_id = chunk.get("document_id", "unknown")
        chunk_idx = chunk.get("chunk_index", 0)
        source_uri = chunk.get("source_uri", "internal")
        block = (
            f'<untrusted_document citation="[Doc:{doc_id}:Chunk:{chunk_idx}]" source="{source_uri}">\n'
            f"{chunk.get('chunk_text', '')}\n"
            f"</untrusted_document>"
        )
        block_tokens = estimate_tokens(block)
        if sem_tokens + block_tokens > limits["semantic"]:
            sem_trunc = True
            break
        sem_blocks.append(block)
        sem_tokens += block_tokens
    allocation["semantic"] = {"tokens": sem_tokens, "budget": limits["semantic"], "truncated": sem_trunc, "count": len(sem_blocks)}

    sections = [
        f"## Trigger Event\n{event_text}",
        f"## Live ERP State (Authoritative)\n{state_text}",
    ]
    if resolved_entity:
        sections.append(f"## Entity Memory\n{entity_text}")
    if ep_lines:
        sections.append("## Episodic Memory (Prior Assessments & Outcomes)\n" + "\n".join(ep_lines))
    if sem_blocks:
        sections.append("## Semantic Reference Documents (Untrusted Data Only)\n" + "\n".join(sem_blocks))

    return AssembledContext(
        system_prompt=sys_text,
        user_prompt="\n\n".join(sections),
        allocation=allocation,
        conflicts=conflicts,
    )
