from typing import Any
import structlog

from config.settings import settings
from harness.context import build_context
from harness.loop import DeliberationResult, run_agent_loop
from prompts.registry import load_prompt
from providers.llm import LLMProvider
from system1.reflex import ReflexOutcome

logger = structlog.get_logger(__name__)


async def run_deliberation(
    outcome: ReflexOutcome,
    payload: dict[str, Any],
    *,
    entity_memory: dict[str, Any] | None = None,
    episodic_items: list[dict[str, Any]] | None = None,
    semantic_chunks: list[dict[str, Any]] | None = None,
    provider: LLMProvider | None = None,
) -> DeliberationResult | None:
    """
    Deliberative tier entrypoint. When SYSTEM2_ENABLED is False, escalations
    are recorded on the Assessment without invoking an LLM.
    """
    if not settings.SYSTEM2_ENABLED:
        logger.info(
            "system2_disabled_skipping_deliberation",
            event_id=outcome.event_id,
            reason=outcome.escalation_reason,
        )
        return None

    prompt = load_prompt("system2_deliberate")
    live_state = {
        result.agent_name: {
            "risk_level": result.risk_level.value,
            "findings": result.findings,
            "recommendations": result.recommendations,
        }
        for result in outcome.results
    }

    assembled = build_context(
        system_prompt=prompt.system_prompt,
        event_payload={"event_type": outcome.event_type, **payload},
        live_state=live_state,
        entity_memory=entity_memory,
        episodic_items=episodic_items,
        semantic_chunks=semantic_chunks,
    )

    return await run_agent_loop(
        event_id=outcome.event_id,
        trigger_reason=outcome.escalation_reason,
        prompt_version=prompt.prompt_version,
        assembled=assembled,
        provider=provider,
    )
