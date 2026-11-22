import asyncio
import httpx
import pytest
import respx

from config.settings import settings
from routing.escalation import should_escalate
from schemas.agent_schemas import AgentResult, AgentStatus, RiskLevel
from system1.reflex import System1Reflex
from system2.deliberate import run_deliberation


def _make_result(name: str, risk: RiskLevel) -> AgentResult:
    return AgentResult(
        agent_name=name,
        status=AgentStatus.SUCCESS,
        risk_level=risk,
        findings={},
        recommendations=[],
        confidence=0.9,
    )


def test_escalation_high_risk_and_cooldown_suppression():
    critical = [_make_result("Inventory Agent", RiskLevel.CRITICAL)]

    escalate, reason = should_escalate(critical, {}, recent_deliberation_exists=False)
    assert escalate is True
    assert reason == "high_risk"

    # Cooldown suppresses duplicate escalation for automated events
    escalate_cd, reason_cd = should_escalate(critical, {}, recent_deliberation_exists=True)
    assert escalate_cd is False
    assert reason_cd == "cooldown_suppressed"

    # Human queries always bypass cooldown
    escalate_human, reason_human = should_escalate(
        critical, {"human_query": True}, recent_deliberation_exists=True
    )
    assert escalate_human is True
    assert reason_human == "human_query"


def test_escalation_on_agent_disagreement():
    results = [
        _make_result("Inventory Agent", RiskLevel.LOW),
        _make_result("Forecast Agent", RiskLevel.HIGH),
    ]
    escalate, reason = should_escalate(results, {})
    assert escalate is True
    assert reason in ("high_risk", "disagreement")

    # Medium vs Low is not enough to trigger disagreement
    mild = [
        _make_result("Inventory Agent", RiskLevel.LOW),
        _make_result("Forecast Agent", RiskLevel.MEDIUM),
    ]
    escalate_mild, reason_mild = should_escalate(mild, {})
    assert escalate_mild is False
    assert reason_mild == "none"


@pytest.mark.asyncio
@respx.mock
async def test_system1_reflex_returns_partial_results_on_timeout():
    """If one agent times out, System 1 still returns results from healthy agents."""
    base = settings.ERP_API_URL
    respx.get(f"{base}/inventory/products/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "product_code": "RM-STEEL-001",
                    "name": "Steel Plate",
                    "reorder_point": 100,
                    "safety_stock": 50,
                    "lead_time_days": 7,
                }
            ],
        )
    )
    respx.get(f"{base}/inventory/balances/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "product_code": "RM-STEEL-001",
                    "warehouse_code": "WH-MAIN-01",
                    "quantity_on_hand": 10,
                    "quantity_available": 10,
                    "quantity_reserved": 0,
                    "variance": 0,
                    "stock_health": "critical",
                }
            ],
        )
    )

    reflex = System1Reflex(per_agent_timeout_s=0.05)

    async def slow_execute(_context):
        await asyncio.sleep(0.5)

    reflex.agents["forecast"].execute = slow_execute  # type: ignore[method-assign]

    outcome = await reflex.evaluate(
        event_id="11111111-1111-1111-1111-111111111111",
        event_type="BalanceBelowReorderPoint",
        payload={"product_code": "RM-STEEL-001", "warehouse_code": "WH-MAIN-01"},
    )

    assert len(outcome.results) == 2
    by_name = {r.agent_name: r for r in outcome.results}
    assert by_name["Inventory Agent"].risk_level == RiskLevel.CRITICAL
    assert by_name["Forecast Agent"].metadata.get("timeout") is True
    assert outcome.escalated is True
    assert outcome.escalation_reason == "high_risk"

    # With SYSTEM2_ENABLED=False, run_deliberation cleanly returns None
    deliberation = await run_deliberation(outcome, {"product_code": "RM-STEEL-001"})
    assert deliberation is None
