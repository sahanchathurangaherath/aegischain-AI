from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import statistics

from agents.base_agent import BaseAgent
from schemas.agent_schemas import AgentResult, AgentStatus, RiskLevel

logger = logging.getLogger(__name__)


class ForecastAgent(BaseAgent):
    """
    Demand Forecasting Agent
    
    Responsibilities:
    - Predict future demand
    - Calculate days of supply
    - Identify potential shortages
    - Analyze demand trends
    - Generate proactive recommendations
    """
    
    def __init__(self):
        super().__init__(name="Forecast Agent")
        self.forecast_horizon_days = 30  # Forecast 30 days ahead
        self.critical_days_threshold = 7  # Critical if stock runs out in < 7 days
        self.warning_days_threshold = 14  # Warning if < 14 days
    
    async def analyze(self, context: Dict[str, Any]) -> AgentResult:
        """
        Perform demand forecasting analysis
        
        Args:
            context: Must contain either:
                - product_code (forecast for specific product)
                - warehouse_code (forecast for warehouse)
                - both (specific product at warehouse)
                - neither (system-wide forecast)
        
        Returns:
            AgentResult with forecast and recommendations
        """
        product_code = context.get("product_code")
        warehouse_code = context.get("warehouse_code")
        
        logger.info(
            f"Forecasting demand - Product: {product_code or 'ALL'}, "
            f"Warehouse: {warehouse_code or 'ALL'}"
        )
        
        # Determine analysis scope
        if product_code and warehouse_code:
            return await self._forecast_specific_item(product_code, warehouse_code)
        elif product_code:
            return await self._forecast_product(product_code)
        elif warehouse_code:
            return await self._forecast_warehouse(warehouse_code)
        else:
            return await self._forecast_system_wide()
    
    async def _forecast_specific_item(
        self,
        product_code: str,
        warehouse_code: str
    ) -> AgentResult:
        """Forecast demand for specific product at specific warehouse"""
        
        try:
            # Get product info
            product = await self.erp_client.get_product(product_code)
            if not product:
                return self._create_error_result(f"Product {product_code} not found")
            
            # Get current inventory
            balance = await self.erp_client.get_inventory_balance(
                product_code,
                warehouse_code
            )
            
            if not balance:
                return self._create_error_result(
                    f"No inventory found for {product_code} at {warehouse_code}"
                )
            
            # Get sales history
            sales_history = await self._get_sales_history(
                product_code,
                warehouse_code,
                days=90
            )
            
            # Calculate forecast
            forecast = self._calculate_forecast(sales_history)
            
            # Assess shortage risk
            shortage_assessment = self._assess_shortage_risk(
                balance,
                product,
                forecast
            )
            
            # Determine risk level
            risk_level = self._determine_risk_level(shortage_assessment)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                shortage_assessment,
                product,
                balance
            )
            
            # Combine findings
            findings = {
                "product_code": product_code,
                "product_name": product["name"],
                "warehouse_code": warehouse_code,
                "current_stock": balance["quantity_on_hand"],
                "available_stock": balance["quantity_available"],
                "reserved_stock": balance["quantity_reserved"],
                **forecast,
                **shortage_assessment
            }
            
            return self.create_result(
                status=AgentStatus.WARNING if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else AgentStatus.SUCCESS,
                risk_level=risk_level,
                findings=findings,
                recommendations=recommendations,
                confidence=forecast.get("confidence", 0.7),
                metadata={
                    "product_code": product_code,
                    "warehouse_code": warehouse_code,
                    "forecast_horizon_days": self.forecast_horizon_days
                }
            )
        
        except Exception as e:
            logger.error(f"Error forecasting {product_code} at {warehouse_code}: {e}")
            return self._create_error_result(str(e))
    
    async def _forecast_product(self, product_code: str) -> AgentResult:
        """Forecast demand for product across all warehouses"""
        
        try:
            # Get product
            product = await self.erp_client.get_product(product_code)
            if not product:
                return self._create_error_result(f"Product {product_code} not found")
            
            # Get all inventory balances for this product
            balances = await self.get_erp_data(
                "inventory/balances",
                {"product__product_code": product_code}
            )
            
            if not balances:
                return self._create_error_result(
                    f"No inventory found for {product_code}"
                )
            
            # Get sales history across all warehouses
            sales_history = await self._get_sales_history(product_code, days=90)
            
            # Calculate forecast
            forecast = self._calculate_forecast(sales_history)
            
            # Calculate total stock
            total_stock = sum(b["quantity_available"] for b in balances)
            
            # Assess shortage risk
            shortage_assessment = {
                "current_stock": total_stock,
                "predicted_demand": forecast["total_demand"],
                "daily_avg_demand": forecast["daily_avg"],
                "days_of_supply": total_stock / forecast["daily_avg"] if forecast["daily_avg"] > 0 else 999,
                "trend": forecast["trend"]
            }
            
            # Determine risk
            risk_level = self._determine_risk_level(shortage_assessment)
            
            # Generate recommendations
            recommendations = self._generate_product_recommendations(
                shortage_assessment,
                product,
                total_stock
            )
            
            findings = {
                "product_code": product_code,
                "product_name": product["name"],
                "total_stock": total_stock,
                "warehouses_count": len(balances),
                **forecast,
                **shortage_assessment
            }
            
            return self.create_result(
                status=AgentStatus.WARNING if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else AgentStatus.SUCCESS,
                risk_level=risk_level,
                findings=findings,
                recommendations=recommendations,
                confidence=forecast.get("confidence", 0.7),
                metadata={"product_code": product_code}
            )
        
        except Exception as e:
            logger.error(f"Error forecasting product {product_code}: {e}")
            return self._create_error_result(str(e))
    
    async def _forecast_warehouse(self, warehouse_code: str) -> AgentResult:
        """Forecast demand for all products in a warehouse"""
        
        try:
            # Get all balances in warehouse
            balances = await self.get_erp_data(
                "inventory/balances",
                {"warehouse__warehouse_code": warehouse_code}
            )
            
            if not balances:
                return self._create_error_result(
                    f"No inventory found in warehouse {warehouse_code}"
                )
            
            # Analyze each product
            critical_items = []
            low_supply_items = []
            
            for balance in balances:
                product_code = balance["product_code"]
                
                # Get sales history for this product
                sales_history = await self._get_sales_history(
                    product_code,
                    warehouse_code,
                    days=90
                )
                
                # Calculate forecast
                forecast = self._calculate_forecast(sales_history)
                
                # Calculate days of supply
                days_of_supply = balance["quantity_available"] / forecast["daily_avg"] if forecast["daily_avg"] > 0 else 999
                
                # Categorize
                if days_of_supply < self.critical_days_threshold:
                    critical_items.append({
                        "product": product_code,
                        "current_stock": balance["quantity_available"],
                        "days_of_supply": round(days_of_supply, 1),
                        "daily_demand": round(forecast["daily_avg"], 2)
                    })
                elif days_of_supply < self.warning_days_threshold:
                    low_supply_items.append({
                        "product": product_code,
                        "current_stock": balance["quantity_available"],
                        "days_of_supply": round(days_of_supply, 1),
                        "daily_demand": round(forecast["daily_avg"], 2)
                    })
            
            # Determine risk
            if critical_items:
                risk_level = RiskLevel.CRITICAL
            elif len(low_supply_items) > len(balances) * 0.3:  # >30% low supply
                risk_level = RiskLevel.HIGH
            elif low_supply_items:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW
            
            findings = {
                "warehouse_code": warehouse_code,
                "total_products": len(balances),
                "critical_items_count": len(critical_items),
                "low_supply_items_count": len(low_supply_items),
                "critical_items": critical_items[:5],  # Top 5
                "low_supply_items": low_supply_items[:5]  # Top 5
            }
            
            recommendations = self._generate_warehouse_recommendations(findings)
            
            return self.create_result(
                status=AgentStatus.WARNING if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else AgentStatus.SUCCESS,
                risk_level=risk_level,
                findings=findings,
                recommendations=recommendations,
                confidence=0.75,
                metadata={"warehouse_code": warehouse_code}
            )
        
        except Exception as e:
            logger.error(f"Error forecasting warehouse {warehouse_code}: {e}")
            return self._create_error_result(str(e))
    
    async def _forecast_system_wide(self) -> AgentResult:
        """System-wide demand forecast"""
        
        try:
            # Get all balances
            all_balances = await self.get_erp_data("inventory/balances")
            
            # Get all sales orders from last 90 days
            sales_orders = await self.get_erp_data(
                "sales/sales-orders",
                {
                    "order_date__gte": (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
                }
            )
            
            # System-level metrics
            total_items = len(all_balances)
            total_value = sum(
                b["quantity_available"] * 10  # Simplified - should use actual unit price
                for b in all_balances
            )
            
            # Calculate average daily orders
            daily_orders = len(sales_orders) / 90 if sales_orders else 0
            
            findings = {
                "total_inventory_items": total_items,
                "total_inventory_value_estimate": round(total_value, 2),
                "avg_daily_orders": round(daily_orders, 2),
                "forecast_horizon_days": self.forecast_horizon_days,
                "projected_orders": round(daily_orders * self.forecast_horizon_days, 0)
            }
            
            recommendations = [
                f"📊 System monitoring {total_items} inventory items",
                f"📈 Average daily orders: {daily_orders:.1f}",
                f"🔮 Projected orders for next {self.forecast_horizon_days} days: {findings['projected_orders']:.0f}"
            ]
            
            return self.create_result(
                status=AgentStatus.SUCCESS,
                risk_level=RiskLevel.LOW,
                findings=findings,
                recommendations=recommendations,
                confidence=0.65,
                metadata={"analysis_scope": "system_wide"}
            )
        
        except Exception as e:
            logger.error(f"Error in system-wide forecast: {e}")
            return self._create_error_result(str(e))
    
    async def _get_sales_history(
        self,
        product_code: str,
        warehouse_code: Optional[str] = None,
        days: int = 90
    ) -> List[Dict]:
        """Get sales history for a product"""
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Build query parameters
        params = {
            "order_date__gte": start_date.strftime("%Y-%m-%d"),
            "order_date__lte": end_date.strftime("%Y-%m-%d")
        }
        
        if warehouse_code:
            params["warehouse__warehouse_code"] = warehouse_code
        
        # Get sales orders
        sales_orders = await self.get_erp_data("sales/sales-orders", params)
        
        # Extract items for this product
        sales_items = []
        for order in sales_orders:
            # Get order items
            order_items = order.get("items", [])
            for item in order_items:
                if item.get("product_code") == product_code:
                    sales_items.append({
                        "order_date": order["order_date"],
                        "quantity": item["quantity_ordered"],
                        "fulfilled": item["quantity_fulfilled"]
                    })
        
        return sales_items
    
    def _calculate_forecast(self, sales_history: List[Dict]) -> Dict[str, Any]:
        """
        Calculate demand forecast using simple time-series analysis
        
        In production, you might use:
        - ARIMA models
        - Prophet (Facebook's forecasting library)
        - Machine learning models
        - Seasonal decomposition
        """
        
        if not sales_history or len(sales_history) < 7:
            return {
                "total_demand": 0,
                "daily_avg": 0,
                "trend": "insufficient_data",
                "confidence": 0.0,
                "forecast_method": "none"
            }
        
        # Aggregate by day
        daily_sales = {}
        for sale in sales_history:
            date = sale["order_date"]
            qty = sale["quantity"]
            
            if date in daily_sales:
                daily_sales[date] += qty
            else:
                daily_sales[date] = qty
        
        # Convert to list
        dates = sorted(daily_sales.keys())
        quantities = [daily_sales[d] for d in dates]
        
        # Calculate statistics
        total_quantity = sum(quantities)
        num_days = len(dates)
        daily_avg = total_quantity / num_days if num_days > 0 else 0
        
        # Calculate moving average (7-day)
        if len(quantities) >= 7:
            recent_avg = statistics.mean(quantities[-7:])
        else:
            recent_avg = daily_avg
        
        # Simple trend detection (compare first half vs second half)
        mid_point = len(quantities) // 2
        if mid_point > 0:
            first_half_avg = statistics.mean(quantities[:mid_point])
            second_half_avg = statistics.mean(quantities[mid_point:])
            
            if second_half_avg > first_half_avg * 1.1:  # 10% increase
                trend = "increasing"
            elif second_half_avg < first_half_avg * 0.9:  # 10% decrease
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        # Forecast for next period
        forecast_daily = recent_avg if recent_avg > 0 else daily_avg
        forecast_total = forecast_daily * self.forecast_horizon_days
        
        # Calculate confidence based on data quality
        if len(quantities) >= 60:
            confidence = 0.85
        elif len(quantities) >= 30:
            confidence = 0.75
        elif len(quantities) >= 14:
            confidence = 0.65
        else:
            confidence = 0.50
        
        # Standard deviation for variability
        std_dev = statistics.stdev(quantities) if len(quantities) > 1 else 0
        
        return {
            "total_demand": round(forecast_total, 2),
            "daily_avg": round(forecast_daily, 2),
            "recent_7day_avg": round(recent_avg, 2),
            "trend": trend,
            "confidence": confidence,
            "forecast_method": "moving_average",
            "variability": round(std_dev, 2),
            "data_points": len(quantities)
        }
    
    def _assess_shortage_risk(
        self,
        balance: Dict,
        product: Dict,
        forecast: Dict
    ) -> Dict[str, Any]:
        """Assess shortage risk based on forecast and current stock"""
        
        current_stock = balance["quantity_available"]
        daily_demand = forecast["daily_avg"]
        
        # Calculate days of supply
        days_of_supply = current_stock / daily_demand if daily_demand > 0 else 999
        
        # Calculate when shortage will occur
        shortage_date = None
        if days_of_supply < self.forecast_horizon_days:
            shortage_date = (
                datetime.now() + timedelta(days=int(days_of_supply))
            ).strftime("%Y-%m-%d")
        
        # Calculate recommended order quantity
        reorder_point = product.get("reorder_point", 0)
        safety_stock = product.get("safety_stock", 0)
        lead_time_days = product.get("lead_time_days", 7)
        
        # Order quantity = (daily demand × lead time) + safety stock - current stock
        recommended_order_qty = max(
            0,
            (daily_demand * lead_time_days) + safety_stock - current_stock
        )
        
        return {
            "days_of_supply": round(days_of_supply, 1),
            "shortage_date": shortage_date,
            "shortage_risk": "high" if days_of_supply < self.critical_days_threshold else "low",
            "recommended_order_quantity": round(recommended_order_qty, 0),
            "lead_time_days": lead_time_days
        }
    
    def _determine_risk_level(self, shortage_assessment: Dict) -> RiskLevel:
        """Determine risk level from shortage assessment"""
        
        days_of_supply = shortage_assessment.get("days_of_supply", 999)
        trend = shortage_assessment.get("trend", "stable")
        
        # Critical: will run out in less than critical threshold
        if days_of_supply < self.critical_days_threshold:
            return RiskLevel.CRITICAL
        
        # High: will run out in less than warning threshold
        if days_of_supply < self.warning_days_threshold:
            return RiskLevel.HIGH
        
        # Medium: increasing demand trend
        if trend == "increasing" and days_of_supply < 30:
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _generate_recommendations(
        self,
        shortage_assessment: Dict,
        product: Dict,
        balance: Dict
    ) -> List[str]:
        """Generate recommendations based on forecast"""
        
        recommendations = []
        
        days_of_supply = shortage_assessment.get("days_of_supply", 999)
        shortage_date = shortage_assessment.get("shortage_date")
        recommended_qty = shortage_assessment.get("recommended_order_quantity", 0)
        trend = shortage_assessment.get("trend", "stable")
        
        # Critical shortage warning
        if days_of_supply < self.critical_days_threshold:
            recommendations.append(
                f"🔴 CRITICAL: Predicted stockout in {int(days_of_supply)} days "
                f"(on {shortage_date}). Place emergency order immediately."
            )
            recommendations.append(
                f"📦 Recommended order quantity: {int(recommended_qty)} units"
            )
        
        # Warning level
        elif days_of_supply < self.warning_days_threshold:
            recommendations.append(
                f"⚠️ WARNING: Only {int(days_of_supply)} days of supply remaining. "
                f"Schedule purchase order within 48 hours."
            )
            recommendations.append(
                f"📦 Recommended order quantity: {int(recommended_qty)} units"
            )
        
        # Trend-based recommendations
        if trend == "increasing":
            recommendations.append(
                "📈 Demand trending upward. Consider increasing safety stock levels."
            )
        elif trend == "decreasing":
            recommendations.append(
                "📉 Demand trending downward. Monitor for potential overstock."
            )
        
        # Lead time considerations
        lead_time = shortage_assessment.get("lead_time_days", 7)
        if days_of_supply < lead_time * 2:
            recommendations.append(
                f"⏰ Stock coverage is less than 2× lead time ({lead_time} days). "
                f"Consider expedited shipping."
            )
        
        # Default recommendation
        if not recommendations:
            recommendations.append(
                f"✅ Stock levels adequate for next {self.forecast_horizon_days} days. "
                f"Continue normal operations."
            )
        
        return recommendations
    
    def _generate_product_recommendations(
        self,
        shortage_assessment: Dict,
        product: Dict,
        total_stock: int
    ) -> List[str]:
        """Generate product-level recommendations"""
        
        recommendations = []
        days_of_supply = shortage_assessment.get("days_of_supply", 999)
        
        if days_of_supply < self.critical_days_threshold:
            recommendations.append(
                f"🔴 System-wide stockout predicted in {int(days_of_supply)} days. "
                f"Initiate emergency procurement."
            )
        elif days_of_supply < self.warning_days_threshold:
            recommendations.append(
                f"⚠️ Product will run out in {int(days_of_supply)} days across all warehouses."
            )
        
        return recommendations
    
    def _generate_warehouse_recommendations(
        self,
        findings: Dict
    ) -> List[str]:
        """Generate warehouse-level recommendations"""
        
        recommendations = []
        critical_count = findings["critical_items_count"]
        low_supply_count = findings["low_supply_items_count"]
        
        if critical_count > 0:
            recommendations.append(
                f"🔴 {critical_count} items predicted to stock out within {self.critical_days_threshold} days. "
                f"Prioritize emergency orders."
            )
        
        if low_supply_count > 5:
            recommendations.append(
                f"⚠️ {low_supply_count} items with less than {self.warning_days_threshold} days supply. "
                f"Review replenishment schedule."
            )
        
        if not recommendations:
            recommendations.append("✅ Warehouse stock levels adequate for forecast period.")
        
        return recommendations
    
    def _create_error_result(self, error_message: str) -> AgentResult:
        """Create an error result"""
        return self.create_result(
            status=AgentStatus.ERROR,
            risk_level=RiskLevel.UNKNOWN,
            findings={"error": error_message},
            recommendations=["Check forecast agent logs for details"],
            confidence=0.0,
            metadata={"error": True}
        )