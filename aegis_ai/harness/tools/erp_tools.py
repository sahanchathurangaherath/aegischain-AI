from typing import Any
from pydantic import BaseModel, Field

from agents.forecast_agent import ForecastAgent
from agents.inventory_agent import InventoryAgent
from agents.supplier_risk_agent import SupplierRiskAgent
from harness.tools.registry import tool


class InventoryLookupInput(BaseModel):
    product_code: str = Field(..., min_length=1)
    warehouse_code: str | None = None


class ForecastLookupInput(BaseModel):
    product_code: str = Field(..., min_length=1)
    warehouse_code: str | None = None


class SupplierRiskInput(BaseModel):
    supplier_code: str | None = None
    product_code: str | None = None


class ProposePurchaseOrderInput(BaseModel):
    product_code: str = Field(..., min_length=1)
    warehouse_code: str = Field(..., min_length=1)
    supplier_code: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    justification: str = Field(..., min_length=5)


@tool(
    name="get_inventory_balance",
    description="Fetch live on-hand, available, reserved stock and variance for a product/warehouse.",
    input_model=InventoryLookupInput,
    access="read",
)
async def get_inventory_balance(args: InventoryLookupInput) -> dict[str, Any]:
    agent = InventoryAgent()
    result = await agent.execute(args.model_dump(exclude_none=True))
    return result.model_dump()


@tool(
    name="get_forecast",
    description="Compute baseline_ma7 demand forecast, days of supply, and reorder quantity.",
    input_model=ForecastLookupInput,
    access="read",
)
async def get_forecast(args: ForecastLookupInput) -> dict[str, Any]:
    agent = ForecastAgent()
    result = await agent.execute(args.model_dump(exclude_none=True))
    return result.model_dump()


@tool(
    name="get_supplier_risk",
    description="Evaluate supplier on-time delivery rate, delayed shipments, and risk score.",
    input_model=SupplierRiskInput,
    access="read",
)
async def get_supplier_risk(args: SupplierRiskInput) -> dict[str, Any]:
    agent = SupplierRiskAgent()
    result = await agent.execute(args.model_dump(exclude_none=True))
    return result.model_dump()


@tool(
    name="propose_purchase_order",
    description="Propose a purchase order for human approval. Never executes directly.",
    input_model=ProposePurchaseOrderInput,
    access="write",
)
async def propose_purchase_order(args: ProposePurchaseOrderInput) -> dict[str, Any]:
    raise RuntimeError("Write tools must never execute directly inside the agent loop.")
