import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from config.settings import settings
from main import app


def _mock_sales_orders(product_code: str, daily_qty: int = 20, days: int = 10) -> list[dict]:
    return [
        {
            "order_date": f"2026-10-{day:02d}",
            "items": [
                {
                    "product_code": product_code,
                    "quantity_ordered": daily_qty,
                    "quantity_fulfilled": daily_qty,
                }
            ],
        }
        for day in range(1, days + 1)
    ]


@pytest.mark.asyncio
@respx.mock
async def test_forecast_agent_specific_item_shortage():
    """Forecast agent computes baseline_ma7 and flags critical shortage when stock < 7 days of supply."""
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
                    "quantity_on_hand": 40,
                    "quantity_available": 40,
                    "quantity_reserved": 0,
                }
            ],
        )
    )
    respx.get(f"{base}/sales/sales-orders/").mock(
        return_value=httpx.Response(200, json=_mock_sales_orders("RM-STEEL-001", daily_qty=20, days=10))
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/agents/forecast",
            json={
                "product_code": "RM-STEEL-001",
                "warehouse_code": "WH-MAIN-01",
                "analysis_type": "demand_forecast",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["agent_name"] == "Forecast Agent"
    assert data["risk_level"] == "critical"
    assert data["findings"]["forecast_method"] == "baseline_ma7"
    assert data["findings"]["daily_avg"] == 20.0
    assert data["findings"]["days_of_supply"] == 2.0
    assert data["findings"]["recommended_order_quantity"] == 150


@pytest.mark.asyncio
@respx.mock
async def test_forecast_agent_warehouse_summary():
    """Warehouse forecast identifies critical items based on baseline_ma7 velocity."""
    base = settings.ERP_API_URL

    respx.get(f"{base}/inventory/balances/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "product_code": "RM-STEEL-001",
                    "warehouse_code": "WH-MAIN-01",
                    "quantity_available": 30,
                }
            ],
        )
    )
    respx.get(f"{base}/sales/sales-orders/").mock(
        return_value=httpx.Response(200, json=_mock_sales_orders("RM-STEEL-001", daily_qty=10, days=10))
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/agents/forecast",
            json={
                "warehouse_code": "WH-MAIN-01",
                "analysis_type": "warehouse_forecast",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "critical"
    assert data["findings"]["total_products"] == 1
    assert data["findings"]["critical_items_count"] == 1
