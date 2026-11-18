import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from config.settings import settings
from main import app


@pytest.mark.asyncio
@respx.mock
async def test_health_endpoint():
    """Health check endpoint returns healthy status when ERP is reachable."""
    base = settings.ERP_API_URL
    respx.get(f"{base}/inventory/products/").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "product_code": "RM-STEEL-001"}])
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["erp_connection"] == "ok"


@pytest.mark.asyncio
async def test_dummy_agent_endpoint():
    """Dummy agent returns valid AgentResult structure."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/test/dummy-agent",
            json={
                "product_code": "RM-STEEL-001",
                "warehouse_code": "WH-MAIN-01",
                "analysis_type": "test",
                "parameters": {},
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["agent_name"] == "Dummy Agent"
    assert "findings" in data


@pytest.mark.asyncio
@respx.mock
async def test_supplier_risk_agent_flags_delayed_supplier():
    """Supplier Risk Agent flags high/critical risk when supplier has delayed shipments."""
    base = settings.ERP_API_URL

    respx.get(f"{base}/procurement/suppliers/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "supplier_code": "SUP-001",
                    "name": "Apex Metals Ltd",
                    "supplier_type": "MANUFACTURER",
                    "reliability_score": 60.0,
                    "risk_level": "HIGH",
                }
            ],
        )
    )
    respx.get(f"{base}/procurement/shipments/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "shipment_number": "SHP-001",
                    "status": "DELAYED",
                    "delay_days": 9,
                    "actual_arrival_date": "2026-10-15",
                    "expected_arrival_date": "2026-10-06",
                },
                {
                    "shipment_number": "SHP-002",
                    "status": "DELAYED",
                    "delay_days": 8,
                    "actual_arrival_date": "2026-10-20",
                    "expected_arrival_date": "2026-10-12",
                },
            ],
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/agents/supplier-risk",
            json={"supplier_code": "SUP-001"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["agent_name"] == "Supplier Risk Agent"
    assert data["risk_level"] in ("high", "critical")
    assert data["findings"]["supplier_code"] == "SUP-001"
