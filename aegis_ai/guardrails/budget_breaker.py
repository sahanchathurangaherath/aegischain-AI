from collections import deque
from dataclasses import dataclass
import time

from guardrails.inputs import GuardrailViolation


@dataclass
class SpendRecord:
    timestamp: float
    cost_usd: float


class SpendCircuitBreaker:
    """
    Sliding 60-minute USD spend circuit breaker for hosted LLM calls.
    Trips and falls back to System 1 when hourly spend reaches `max_usd_per_hour`.
    """

    def __init__(self, max_usd_per_hour: float = 2.0, window_seconds: float = 3600.0):
        self.max_usd_per_hour = max_usd_per_hour
        self.window_seconds = window_seconds
        self._records: deque[SpendRecord] = deque()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._records and self._records[0].timestamp < cutoff:
            self._records.popleft()

    def current_hourly_spend(self, now: float | None = None) -> float:
        ts = now if now is not None else time.monotonic()
        self._prune(ts)
        return round(sum(r.cost_usd for r in self._records), 6)

    def check_or_trip(self, now: float | None = None) -> None:
        spend = self.current_hourly_spend(now=now)
        if spend >= self.max_usd_per_hour:
            raise GuardrailViolation(
                code="spend_circuit_breaker_tripped",
                message=f"Hourly LLM spend (${spend:.4f}) reached limit (${self.max_usd_per_hour:.2f}).",
                details={"spend_usd": spend, "limit_usd": self.max_usd_per_hour},
            )

    def record(self, cost_usd: float, now: float | None = None) -> None:
        ts = now if now is not None else time.monotonic()
        self._prune(ts)
        self._records.append(SpendRecord(timestamp=ts, cost_usd=max(0.0, cost_usd)))


def check_action_gate(
    *,
    action_type: str,
    value_usd: float,
    reversibility: str,
    writes_enabled: bool = True,
    approval_threshold: float = 1000.0,
    dual_approval_threshold: float = 10000.0,
) -> dict[str, object]:
    """Evaluate Tier 3 action gate rules before creating an ApprovalRequest."""
    allowed_actions = {"CREATE_PO", "CREATE_TRANSFER"}
    if not writes_enabled:
        raise GuardrailViolation(
            code="writes_disabled_kill_switch",
            message="Global WRITES_ENABLED kill switch is OFF.",
        )
    if action_type not in allowed_actions:
        raise GuardrailViolation(
            code="action_not_allowed",
            message=f"Action '{action_type}' is not in ALLOWED_ACTIONS.",
        )

    if reversibility == "irreversible":
        required_approvers = 2 if value_usd >= dual_approval_threshold else 1
        return {"requires_human": True, "required_approvers": required_approvers, "reason": "irreversible"}
    if value_usd >= dual_approval_threshold:
        return {"requires_human": True, "required_approvers": 2, "reason": "dual_approval_threshold"}
    if value_usd >= approval_threshold:
        return {"requires_human": True, "required_approvers": 1, "reason": "approval_threshold"}
    return {"requires_human": False, "required_approvers": 0, "reason": "below_threshold"}
