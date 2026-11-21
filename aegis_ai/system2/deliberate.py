from typing import Any
import structlog

from config.settings import settings
from system1.reflex import ReflexOutcome

logger = structlog.get_logger(__name__)


async def run_deliberation(
    outcome: ReflexOutcome,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
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

    logger.info(
        "system2_deliberation_queued",
        event_id=outcome.event_id,
        event_type=outcome.event_type,
        reason=outcome.escalation_reason,
    )
    return {
        "event_id": outcome.event_id,
        "status": "queued",
        "reason": outcome.escalation_reason,
    }
