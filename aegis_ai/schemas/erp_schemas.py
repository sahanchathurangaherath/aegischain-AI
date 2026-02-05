from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


class ProductSchema(BaseModel):
    """Product data from ERP"""
    id: int
    product_code: str
    name: str
    category: str
    unit_price: float
    reorder_point: int
    safety_stock: int
    is_active: bool


class InventoryBalanceSchema(BaseModel):
    """Inventory balance from ERP"""
    id: int
    product_code: str
    product_name: str
    warehouse_code: str
    warehouse_name: str
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int
    variance: int
    stock_health: str


class SupplierSchema(BaseModel):
    """Supplier data from ERP"""
    id: int
    supplier_code: str
    name: str
    reliability_score: float
    on_time_delivery_rate: float
    risk_level: str
    is_active: bool


class ShipmentSchema(BaseModel):
    """Shipment data from ERP"""
    id: int
    shipment_number: str
    po_number: str
    status: str
    expected_arrival_date: date
    delay_days: int
    is_delayed: bool
    carrier: str


class ScanResponseSchema(BaseModel):
    """Response from QR scan endpoint"""
    success: bool
    message: str
    scan: dict
    inventory_balance: Optional[dict] = None