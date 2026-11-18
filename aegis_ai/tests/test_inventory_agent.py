import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from config.settings import settings
from main import app


@pytest.mark.asyncio
@respx.mock
async def test_inventory_agent_flags_low_stock():
    """Specific item with critical stock returns critical risk level and urgent recommendation."""
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
                    "quantity_on_hand": 2,
                    "quantity_available": 2,
                    "quantity_reserved": 0,
                    "variance": 0,
                    "stock_health": "critical",
                }
            ],
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/agents/inventory",
            json={
                "product_code": "RM-STEEL-001",
                "warehouse_code": "WH-MAIN-01",
                "analysis_type": "inventory_check",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["agent_name"] == "Inventory Agent"
    assert data["risk_level"] == "critical"
    assert data["findings"]["below_safety_stock"] is True
    assert any("URGENT" in rec for rec in data["recommendations"])


@pytest.mark.asyncio
@respx.mock
async def test_inventory_agent_warehouse_analysis():
    """Warehouse-level check aggregates critical and healthy items accurately."""
    base = settings.ERP_API_URL

    respx.get(f"{base}/inventory/balances/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "product_code": "RM-STEEL-001",
                    "warehouse_code": "WH-MAIN-01",
                    "quantity_available": 5,
                    "stock_health": "critical",
                },
                {
                    "product_code": "PK-BOX-002",
                    "warehouse_code": "WH-MAIN-01",
                    "quantity_available": 500,
                    "stock_health": "healthy",
                },
            ],
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/agents/inventory",
            json={
                "warehouse_code": "WH-MAIN-01",
                "analysis_type": "warehouse_check",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "critical"
    assert data["findings"]["total_items"] == 2
    assert data["findings"]["critical_items_count"] == 1
    assert data["findings"]["health_percentage"] == 50.0
