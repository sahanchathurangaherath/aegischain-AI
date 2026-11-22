from typing import Any
from schemas.agent_schemas import AgentResult, RiskLevel


_RISK_SCORE = {
    RiskLevel.UNKNOWN: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


def _agents_disagree(results: list[AgentResult]) -> bool:
    """Return True when specialist agents diverge significantly on risk level."""
    scored = [_RISK_SCORE[r.risk_level] for r in results if r.risk_level != RiskLevel.UNKNOWN]
    if len(scored) < 2:
        return False
    return (max(scored) - min(scored)) >= 2


def should_escalate(
    results: list[AgentResult],
    context: dict[str, Any],
    recent_deliberation_exists: bool = False,
) -> tuple[bool, str]:
    """
    Decide whether System 1 results should escalate to System 2 deliberation.

    Returns:
        (escalate: bool, reason: str)
    """
    if context.get("human_query"):
        return True, "human_query"

    if recent_deliberation_exists:
        return False, "cooldown_suppressed"

    if any(r.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) for r in results):
        return True, "high_risk"

    if _agents_disagree(results):
        return True, "disagreement"

    if context.get("proposed_write"):
        return True, "write_proposed"

    return False, "none"
