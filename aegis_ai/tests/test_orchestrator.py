import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from config.settings import settings
from main import app


@pytest.mark.asyncio
async def test_orchestrator_info_endpoint():
    """Orchestrator info endpoint returns registered agents and intent keywords."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/orchestrate/info")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "inventory" in data["available_agents"]
    assert "forecast" in data["available_agents"]
    assert data["agent_count"] >= 2


@pytest.mark.asyncio
@respx.mock
async def test_orchestrate_specific_item_combines_agents():
    """Orchestrator dispatches inventory and forecast agents in parallel and escalates critical risk."""
    base = settings.ERP_API_URL

    respx.get(f"{base}/inventory/products/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "product_code": "RM-STEEL-001",
                    "name": "Structural Steel Plate",
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
    respx.get(f"{base}/sales/sales-orders/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "order_date": f"2026-10-{day:02d}",
                    "items": [
                        {
                            "product_code": "RM-STEEL-001",
                            "quantity_ordered": 15,
                            "quantity_fulfilled": 15,
                        }
                    ],
                }
                for day in range(1, 10)
            ],
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/orchestrate",
            json={
                "query": "Check inventory status and forecast future demand for RM-STEEL-001",
                "context": {
                    "product_code": "RM-STEEL-001",
                    "warehouse_code": "WH-MAIN-01",
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["overall_risk_level"] == "critical"
    assert data["action_required"] is True
    assert len(data["agent_results"]) >= 1
    assert len(data["recommended_actions"]) > 0
