import asyncio
from dataclasses import dataclass
import time
from typing import Any
import structlog

from agents.forecast_agent import ForecastAgent
from agents.inventory_agent import InventoryAgent
from agents.supplier_risk_agent import SupplierRiskAgent
from routing.escalation import should_escalate
from schemas.agent_schemas import AgentResult, AgentStatus, RiskLevel

logger = structlog.get_logger(__name__)

EVENT_AGENT_MAP: dict[str, list[str]] = {
    "InventoryMovementRecorded": ["inventory"],
    "BalanceBelowReorderPoint": ["inventory", "forecast"],
    "ShipmentDelayed": ["supplier_risk"],
    "SupplierQualityIncident": ["supplier_risk"],
}


@dataclass
class ReflexOutcome:
    event_id: str
    event_type: str
    results: list[AgentResult]
    escalated: bool
    escalation_reason: str
    latency_ms: float


class System1Reflex:
    """
    Fast deterministic reflex tier. Runs specialist rule agents in parallel
    with per-agent timeouts and returns partial results on single-agent failure.
    """

    def __init__(self, per_agent_timeout_s: float = 10.0):
        self.per_agent_timeout_s = per_agent_timeout_s
        self.agents = {
            "inventory": InventoryAgent(),
            "forecast": ForecastAgent(),
            "supplier_risk": SupplierRiskAgent(),
        }

    async def _run_single_agent(
        self, agent_key: str, context: dict[str, Any]
    ) -> AgentResult:
        agent = self.agents[agent_key]
        try:
            return await asyncio.wait_for(
                agent.execute(context),
                timeout=self.per_agent_timeout_s,
            )
        except TimeoutError:
            logger.warning("system1_agent_timeout", agent=agent_key, timeout_s=self.per_agent_timeout_s)
            return AgentResult(
                agent_name=agent.name,
                status=AgentStatus.ERROR,
                risk_level=RiskLevel.UNKNOWN,
                findings={"error": f"Timed out after {self.per_agent_timeout_s}s"},
                recommendations=["Review agent latency and ERP response time"],
                confidence=0.0,
                metadata={"timeout": True},
            )
        except Exception as exc:
            logger.error("system1_agent_error", agent=agent_key, error=str(exc))
            return AgentResult(
                agent_name=agent.name,
                status=AgentStatus.ERROR,
                risk_level=RiskLevel.UNKNOWN,
                findings={"error": str(exc)},
                recommendations=["Inspect agent error logs"],
                confidence=0.0,
                metadata={"error": True},
            )

    async def evaluate(
        self,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
        recent_deliberation_exists: bool = False,
    ) -> ReflexOutcome:
        start = time.perf_counter()
        agent_keys = EVENT_AGENT_MAP.get(event_type, ["inventory"])

        tasks = [self._run_single_agent(key, payload) for key in agent_keys if key in self.agents]
        results = list(await asyncio.gather(*tasks))

        escalated, reason = should_escalate(
            results=results,
            context=payload,
            recent_deliberation_exists=recent_deliberation_exists,
        )
        latency_ms = round((time.perf_counter() - start) * 1000.0, 2)

        logger.info(
            "system1_evaluation_complete",
            event_id=event_id,
            event_type=event_type,
            agents=agent_keys,
            escalated=escalated,
            escalation_reason=reason,
            latency_ms=latency_ms,
        )

        return ReflexOutcome(
            event_id=event_id,
            event_type=event_type,
            results=results,
            escalated=escalated,
            escalation_reason=reason,
            latency_ms=latency_ms,
        )
