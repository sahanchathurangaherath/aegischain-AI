import os
import sys
from pathlib import Path
from typing import Any

# Allow importing aegis_ai services when launched from repo root
AEGIS_AI_DIR = Path(__file__).resolve().parent.parent / "aegis_ai"
if str(AEGIS_AI_DIR) not in sys.path:
    sys.path.insert(0, str(AEGIS_AI_DIR))

from mcp.server.fastmcp import FastMCP
from services.erp_client import ERPClient

mcp = FastMCP("aegischain-erp")


def _client() -> ERPClient:
    return ERPClient()


@mcp.tool()
async def get_product(product_code: str) -> dict[str, Any]:
    """Fetch product master data including reorder point, safety stock, and unit economics."""
    product = await _client().get_product(product_code)
    return product or {"error": f"Product '{product_code}' not found"}


@mcp.tool()
async def get_inventory_balance(product_code: str, warehouse_code: str) -> dict[str, Any]:
    """Return live on-hand, reserved, and available stock for a product at a warehouse."""
    balance = await _client().get_inventory_balance(product_code, warehouse_code)
    return balance or {"error": f"No balance found for '{product_code}' at '{warehouse_code}'"}


@mcp.tool()
async def get_low_stock_items() -> list[dict[str, Any]]:
    """List all inventory balances currently below their product reorder point."""
    return await _client().get_low_stock_items()


@mcp.tool()
async def get_delayed_shipments() -> list[dict[str, Any]]:
    """List all inbound supplier shipments currently experiencing delivery delays."""
    return await _client().get_delayed_shipments()


@mcp.tool()
async def get_supplier(supplier_code: str) -> dict[str, Any]:
    """Fetch supplier master data, lead time, reliability score, and risk level."""
    supplier = await _client().get_supplier(supplier_code)
    return supplier or {"error": f"Supplier '{supplier_code}' not found"}


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
