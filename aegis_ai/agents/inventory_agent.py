from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

from agents.base_agent import BaseAgent
from schemas.agent_schemas import AgentResult, AgentStatus, RiskLevel

logger = logging.getLogger(__name__)


class InventoryAgent(BaseAgent):
    """
    Inventory Intelligence Agent
    
    Responsibilities:
    - Monitor inventory levels
    - Detect stock variance
    - Identify reorder needs
    - Assess stock health
    - Generate alerts and recommendations
    """
    
    def __init__(self):
        super().__init__(name="Inventory Agent")
        self.variance_threshold = 0.10  # 10% variance triggers alert
        self.critical_days_threshold = 3  # Critical if stock lasts < 3 days
    
    async def analyze(self, context: Dict[str, Any]) -> AgentResult:
        """
        Perform inventory analysis
        
        Args:
            context: Must contain either:
                - product_code + warehouse_code (specific item)
                - warehouse_code only (all items in warehouse)
                - product_code only (item across all warehouses)
                - neither (all inventory)
        
        Returns:
            AgentResult with findings and recommendations
        """
        product_code = context.get("product_code")
        warehouse_code = context.get("warehouse_code")
        
        logger.info(
            f"Analyzing inventory - Product: {product_code or 'ALL'}, "
            f"Warehouse: {warehouse_code or 'ALL'}"
        )
        
        # Determine analysis scope
        if product_code and warehouse_code:
            return await self._analyze_specific_item(product_code, warehouse_code)
        elif warehouse_code:
            return await self._analyze_warehouse(warehouse_code)
        elif product_code:
            return await self._analyze_product(product_code)
        else:
            return await self._analyze_all_inventory()
    
    async def _analyze_specific_item(
        self, 
        product_code: str, 
        warehouse_code: str
    ) -> AgentResult:
        """Analyze specific product at specific warehouse"""
        
        try:
            # Get product info
            product = await self.erp_client.get_product(product_code)
            if not product:
                return self._create_error_result(f"Product {product_code} not found")
            
            # Get inventory balance
            balance = await self.erp_client.get_inventory_balance(
                product_code, 
                warehouse_code
            )
            
            if not balance:
                return self._create_no_stock_result(product_code, warehouse_code)
            
            # Perform analysis
            findings = self._analyze_balance(product, balance)
            risk_level = self._assess_risk_level(findings)
            recommendations = self._generate_recommendations(findings, product)
            
            return self.create_result(
                status=AgentStatus.SUCCESS if risk_level == RiskLevel.LOW else AgentStatus.WARNING,
                risk_level=risk_level,
                findings=findings,
                recommendations=recommendations,
                confidence=0.90,
                metadata={
                    "product_code": product_code,
                    "warehouse_code": warehouse_code
                }
            )
        
        except Exception as e:
            logger.error(f"Error analyzing {product_code} at {warehouse_code}: {e}")
            return self._create_error_result(str(e))
    
    async def _analyze_warehouse(self, warehouse_code: str) -> AgentResult:
        """Analyze all inventory in a warehouse"""
        
        try:
            # Get all balances for this warehouse
            balances = await self.get_erp_data(
                "inventory/balances",
                {"warehouse__warehouse_code": warehouse_code}
            )
            
            if not balances:
                return self._create_error_result(
                    f"No inventory found in warehouse {warehouse_code}"
                )
            
            # Analyze each item
            critical_items = []
            low_stock_items = []
            total_items = len(balances)
            
            for balance in balances:
                health = balance.get("stock_health")
                
                if health == "critical":
                    critical_items.append({
                        "product": balance["product_code"],
                        "quantity": balance["quantity_available"],
                        "status": "critical"
                    })
                elif health == "low":
                    low_stock_items.append({
                        "product": balance["product_code"],
                        "quantity": balance["quantity_available"],
                        "status": "low"
                    })
            
            # Determine overall risk
            if critical_items:
                risk_level = RiskLevel.CRITICAL
            elif len(low_stock_items) > total_items * 0.3:  # >30% low stock
                risk_level = RiskLevel.HIGH
            elif low_stock_items:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW
            
            findings = {
                "warehouse_code": warehouse_code,
                "total_items": total_items,
                "critical_items_count": len(critical_items),
                "low_stock_items_count": len(low_stock_items),
                "critical_items": critical_items[:5],  # Top 5
                "low_stock_items": low_stock_items[:5],  # Top 5
                "health_percentage": round(
                    ((total_items - len(critical_items) - len(low_stock_items)) / total_items * 100) if total_items > 0 else 100,
                    2
                )
            }
            
            recommendations = self._generate_warehouse_recommendations(findings)
            
            return self.create_result(
                status=AgentStatus.WARNING if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else AgentStatus.SUCCESS,
                risk_level=risk_level,
                findings=findings,
                recommendations=recommendations,
                confidence=0.85,
                metadata={"warehouse_code": warehouse_code}
            )
        
        except Exception as e:
            logger.error(f"Error analyzing warehouse {warehouse_code}: {e}")
            return self._create_error_result(str(e))
    
    async def _analyze_product(self, product_code: str) -> AgentResult:
        """Analyze product across all warehouses"""
        
        try:
            # Get product
            product = await self.erp_client.get_product(product_code)
            if not product:
                return self._create_error_result(f"Product {product_code} not found")
            
            # Get all balances for this product
            balances = await self.get_erp_data(
                "inventory/balances",
                {"product__product_code": product_code}
            )
            
            if not balances:
                return self._create_error_result(
                    f"No inventory found for product {product_code}"
                )
            
            # Calculate totals
            total_stock = sum(b["quantity_on_hand"] for b in balances)
            total_available = sum(b["quantity_available"] for b in balances)
            total_reserved = sum(b["quantity_reserved"] for b in balances)
            
            # Check against reorder point and safety stock
            reorder_point = product["reorder_point"]
            safety_stock = product["safety_stock"]
            
            # Assess risk
            if total_available < safety_stock:
                risk_level = RiskLevel.CRITICAL
            elif total_available < reorder_point:
                risk_level = RiskLevel.HIGH
            elif total_available < reorder_point * 1.5:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW
            
            findings = {
                "product_code": product_code,
                "product_name": product["name"],
                "total_stock": total_stock,
                "total_available": total_available,
                "total_reserved": total_reserved,
                "reorder_point": reorder_point,
                "safety_stock": safety_stock,
                "warehouses_count": len(balances),
                "warehouses": [
                    {
                        "code": b["warehouse_code"],
                        "quantity": b["quantity_available"]
                    }
                    for b in balances
                ]
            }
            
            recommendations = self._generate_product_recommendations(
                findings, 
                product
            )
            
            return self.create_result(
                status=AgentStatus.WARNING if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else AgentStatus.SUCCESS,
                risk_level=risk_level,
                findings=findings,
                recommendations=recommendations,
                confidence=0.88,
                metadata={"product_code": product_code}
            )
        
        except Exception as e:
            logger.error(f"Error analyzing product {product_code}: {e}")
            return self._create_error_result(str(e))
    
    async def _analyze_all_inventory(self) -> AgentResult:
        """Analyze entire inventory system"""
        
        try:
            # Get all low stock items
            low_stock = await self.erp_client.get_low_stock_items()
            
            # Get all critical items
            critical = await self.get_erp_data("inventory/balances/critical")
            
            # Get total inventory count
            all_balances = await self.get_erp_data("inventory/balances")
            total_items = len(all_balances)
            
            # Calculate health metrics
            critical_percentage = (len(critical) / total_items * 100) if total_items > 0 else 0
            low_stock_percentage = (len(low_stock) / total_items * 100) if total_items > 0 else 0
            healthy_percentage = 100 - critical_percentage - low_stock_percentage
            
            # Assess overall risk
            if critical_percentage > 10:
                risk_level = RiskLevel.CRITICAL
            elif critical_percentage > 5 or low_stock_percentage > 20:
                risk_level = RiskLevel.HIGH
            elif low_stock_percentage > 10:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW
            
            findings = {
                "total_inventory_items": total_items,
                "critical_items_count": len(critical),
                "low_stock_items_count": len(low_stock),
                "healthy_items_count": total_items - len(critical) - len(low_stock),
                "critical_percentage": round(critical_percentage, 2),
                "low_stock_percentage": round(low_stock_percentage, 2),
                "healthy_percentage": round(healthy_percentage, 2),
                "top_critical_items": [
                    {
                        "product": item["product_code"],
                        "warehouse": item["warehouse_code"],
                        "quantity": item["quantity_available"]
                    }
                    for item in critical[:5]
                ]
            }
            
            recommendations = self._generate_system_recommendations(findings)
            
            return self.create_result(
                status=AgentStatus.WARNING if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else AgentStatus.SUCCESS,
                risk_level=risk_level,
                findings=findings,
                recommendations=recommendations,
                confidence=0.92,
                metadata={"analysis_scope": "system_wide"}
            )
        
        except Exception as e:
            logger.error(f"Error analyzing all inventory: {e}")
            return self._create_error_result(str(e))
    
    def _analyze_balance(
        self, 
        product: Dict, 
        balance: Dict
    ) -> Dict[str, Any]:
        """Analyze a single inventory balance"""
        
        current_qty = balance["quantity_on_hand"]
        available_qty = balance["quantity_available"]
        reserved_qty = balance["quantity_reserved"]
        variance = balance.get("variance", 0)
        
        reorder_point = product["reorder_point"]
        safety_stock = product["safety_stock"]
        
        # Calculate variance percentage
        variance_pct = (abs(variance) / current_qty * 100) if current_qty > 0 else 0
        
        # Stock coverage (days of supply) - simplified
        # In production, you'd use actual demand data
        avg_daily_usage = product.get("avg_daily_usage", 10)  # Mock
        days_of_supply = available_qty / avg_daily_usage if avg_daily_usage > 0 else 999
        
        findings = {
            "product_code": product["product_code"],
            "product_name": product["name"],
            "warehouse_code": balance["warehouse_code"],
            "current_stock": current_qty,
            "available_stock": available_qty,
            "reserved_stock": reserved_qty,
            "variance": variance,
            "variance_percentage": round(variance_pct, 2),
            "reorder_point": reorder_point,
            "safety_stock": safety_stock,
            "stock_health": balance["stock_health"],
            "days_of_supply": round(days_of_supply, 1),
            "below_reorder_point": available_qty < reorder_point,
            "below_safety_stock": available_qty < safety_stock
        }
        
        return findings
    
    def _assess_risk_level(self, findings: Dict[str, Any]) -> RiskLevel:
        """Assess risk level based on findings"""
        
        stock_health = findings.get("stock_health")
        variance_pct = findings.get("variance_percentage", 0)
        days_of_supply = findings.get("days_of_supply", 999)
        
        # Critical conditions
        if (stock_health == "critical" or 
            days_of_supply < self.critical_days_threshold or
            variance_pct > 25):
            return RiskLevel.CRITICAL
        
        # High risk conditions
        if (stock_health == "low" or 
            days_of_supply < 7 or
            variance_pct > 15):
            return RiskLevel.HIGH
        
        # Medium risk conditions
        if variance_pct > 10 or days_of_supply < 14:
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _generate_recommendations(
        self, 
        findings: Dict[str, Any],
        product: Dict
    ) -> List[str]:
        """Generate recommendations based on findings"""
        
        recommendations = []
        
        stock_health = findings.get("stock_health")
        variance_pct = findings.get("variance_percentage", 0)
        available = findings.get("available_stock", 0)
        reorder_point = findings.get("reorder_point", 0)
        days_of_supply = findings.get("days_of_supply", 999)
        
        # Critical stock recommendations
        if stock_health == "critical":
            recommendations.append(
                f"🔴 URGENT: Stock critically low ({available} units). "
                f"Place emergency order immediately."
            )
            recommendations.append(
                f"Expected stockout in {int(days_of_supply)} days if no action taken."
            )
        
        # Low stock recommendations
        elif stock_health == "low":
            recommendations.append(
                f"⚠️ Stock below reorder point ({available}/{reorder_point}). "
                f"Initiate purchase order within 24 hours."
            )
        
        # Variance recommendations
        if variance_pct > 20:
            recommendations.append(
                f"📊 Large inventory variance detected ({variance_pct:.1f}%). "
                f"Conduct immediate physical count and investigate discrepancy."
            )
        elif variance_pct > 10:
            recommendations.append(
                f"📊 Inventory variance of {variance_pct:.1f}% detected. "
                f"Schedule physical count within 48 hours."
            )
        
        # Reorder recommendations
        if available < reorder_point and stock_health != "critical":
            qty_needed = reorder_point * 2 - available  # Order to double reorder point
            recommendations.append(
                f"📦 Recommend ordering {qty_needed} units to restore optimal stock levels."
            )
        
        # Days of supply recommendations
        if days_of_supply < 7:
            recommendations.append(
                f"⏰ Only {int(days_of_supply)} days of supply remaining. "
                f"Expedite next shipment if possible."
            )
        
        # General recommendation if no issues
        if not recommendations:
            recommendations.append("✅ Inventory levels are healthy. Continue monitoring.")
        
        return recommendations
    
    def _generate_warehouse_recommendations(
        self, 
        findings: Dict[str, Any]
    ) -> List[str]:
        """Generate warehouse-level recommendations"""
        
        recommendations = []
        
        critical_count = findings["critical_items_count"]
        low_stock_count = findings["low_stock_items_count"]
        health_pct = findings["health_percentage"]
        
        if critical_count > 0:
            recommendations.append(
                f"🔴 {critical_count} items critically low. Prioritize emergency orders."
            )
        
        if low_stock_count > 5:
            recommendations.append(
                f"⚠️ {low_stock_count} items below reorder point. "
                f"Review and process purchase requisitions."
            )
        
        if health_pct < 70:
            recommendations.append(
                f"📉 Warehouse health at {health_pct}%. "
                f"Implement systematic replenishment review."
            )
        else:
            recommendations.append(
                f"✅ Warehouse health good ({health_pct}%). Maintain current processes."
            )
        
        return recommendations
    
    def _generate_product_recommendations(
        self,
        findings: Dict[str, Any],
        product: Dict
    ) -> List[str]:
        """Generate product-level recommendations"""
        
        recommendations = []
        
        total_available = findings["total_available"]
        reorder_point = findings["reorder_point"]
        safety_stock = findings["safety_stock"]
        warehouses_count = findings["warehouses_count"]
        
        if total_available < safety_stock:
            recommendations.append(
                f"🔴 Total available stock ({total_available}) below safety stock ({safety_stock}). "
                f"Place emergency order across all locations."
            )
        elif total_available < reorder_point:
            qty_needed = reorder_point * 2 - total_available
            recommendations.append(
                f"⚠️ Recommend ordering {qty_needed} units system-wide."
            )
        
        # Warehouse distribution recommendation
        if warehouses_count > 1:
            recommendations.append(
                f"📦 Stock distributed across {warehouses_count} warehouses. "
                f"Consider rebalancing if needed."
            )
        
        return recommendations
    
    def _generate_system_recommendations(
        self, 
        findings: Dict[str, Any]
    ) -> List[str]:
        """Generate system-wide recommendations"""
        
        recommendations = []
        
        critical_pct = findings["critical_percentage"]
        low_stock_pct = findings["low_stock_percentage"]
        
        if critical_pct > 10:
            recommendations.append(
                f"🚨 SYSTEM ALERT: {critical_pct}% of inventory critically low. "
                f"Initiate emergency procurement protocol."
            )
        elif critical_pct > 5:
            recommendations.append(
                f"⚠️ {critical_pct}% of inventory critically low. "
                f"Review and expedite pending orders."
            )
        
        if low_stock_pct > 20:
            recommendations.append(
                f"📊 {low_stock_pct}% of inventory below reorder point. "
                f"Conduct system-wide replenishment review."
            )
        
        if critical_pct < 5 and low_stock_pct < 10:
            recommendations.append(
                "✅ Overall inventory health is good. Continue standard operations."
            )
        
        return recommendations
    
    def _create_error_result(self, error_message: str) -> AgentResult:
        """Create an error result"""
        return self.create_result(
            status=AgentStatus.ERROR,
            risk_level=RiskLevel.UNKNOWN,
            findings={"error": error_message},
            recommendations=["Check agent logs for details"],
            confidence=0.0,
            metadata={"error": True}
        )
    
    def _create_no_stock_result(
        self, 
        product_code: str, 
        warehouse_code: str
    ) -> AgentResult:
        """Create result for no stock found"""
        return self.create_result(
            status=AgentStatus.INFO,
            risk_level=RiskLevel.CRITICAL,
            findings={
                "product_code": product_code,
                "warehouse_code": warehouse_code,
                "message": "No inventory record found"
            },
            recommendations=[
                f"Product {product_code} has no stock at {warehouse_code}",
                "Create initial inventory record or check product/warehouse codes"
            ],
            confidence=1.0,
            metadata={"no_stock": True}
        )