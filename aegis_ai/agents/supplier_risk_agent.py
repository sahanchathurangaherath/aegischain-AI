from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import statistics

from agents.base_agent import BaseAgent
from schemas.agent_schemas import AgentResult, AgentStatus, RiskLevel

logger = logging.getLogger(__name__)


class SupplierRiskAgent(BaseAgent):
    """
    Supplier Risk Assessment Agent
    
    Responsibilities:
    - Assess supplier reliability
    - Track delivery performance
    - Predict delivery delays
    - Analyze supplier risk factors
    - Generate supplier recommendations
    """
    
    def __init__(self):
        super().__init__(name="Supplier Risk Agent")
        self.analysis_period_days = 180  # Analyze last 6 months
        self.delay_threshold_days = 3    # Delays > 3 days are significant
        self.critical_delay_days = 7     # Delays > 7 days are critical
    
    async def analyze(self, context: Dict[str, Any]) -> AgentResult:
        """
        Perform supplier risk analysis
        
        Args:
            context: Must contain either:
                - supplier_code (analyze specific supplier)
                - product_code (find and analyze product's suppliers)
                - neither (analyze all high-risk suppliers)
        
        Returns:
            AgentResult with risk assessment
        """
        supplier_code = context.get("supplier_code")
        product_code = context.get("product_code")
        
        logger.info(
            f"Analyzing supplier risk - Supplier: {supplier_code or 'AUTO'}, "
            f"Product: {product_code or 'N/A'}"
        )
        
        # Determine analysis scope
        if supplier_code:
            return await self._analyze_specific_supplier(supplier_code)
        elif product_code:
            return await self._analyze_product_suppliers(product_code)
        else:
            return await self._analyze_all_suppliers()
    
    async def _analyze_specific_supplier(
        self,
        supplier_code: str
    ) -> AgentResult:
        """Analyze a specific supplier's performance"""
        
        try:
            # Get supplier info
            supplier = await self.erp_client.get_supplier(supplier_code)
            if not supplier:
                return self._create_error_result(f"Supplier {supplier_code} not found")
            
            # Get supplier's shipment history
            shipment_history = await self._get_shipment_history(supplier_code)
            
            # Get pending shipments
            pending_shipments = await self._get_pending_shipments(supplier_code)
            
            # Calculate performance metrics
            performance = self._calculate_performance_metrics(
                shipment_history,
                supplier
            )
            
            # Analyze pending shipments for current risks
            pending_analysis = self._analyze_pending_shipments(pending_shipments)
            
            # Assess overall risk
            risk_assessment = self._assess_supplier_risk(
                performance,
                pending_analysis,
                supplier
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                risk_assessment,
                supplier,
                performance
            )
            
            # Combine findings
            findings = {
                "supplier_code": supplier_code,
                "supplier_name": supplier["name"],
                "supplier_type": supplier["supplier_type"],
                **performance,
                **pending_analysis,
                **risk_assessment
            }
            
            # Determine overall risk level
            risk_level = self._determine_risk_level(risk_assessment)
            
            return self.create_result(
                status=AgentStatus.WARNING if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else AgentStatus.SUCCESS,
                risk_level=risk_level,
                findings=findings,
                recommendations=recommendations,
                confidence=0.85,
                metadata={
                    "supplier_code": supplier_code,
                    "analysis_period_days": self.analysis_period_days
                }
            )
        
        except Exception as e:
            logger.error(f"Error analyzing supplier {supplier_code}: {e}")
            return self._create_error_result(str(e))
    
    async def _analyze_product_suppliers(
        self,
        product_code: str
    ) -> AgentResult:
        """Analyze suppliers for a specific product"""
        
        try:
            # Get product
            product = await self.erp_client.get_product(product_code)
            if not product:
                return self._create_error_result(f"Product {product_code} not found")
            
            # Get purchase orders for this product
            purchase_orders = await self.get_erp_data(
                "procurement/purchase-orders",
                {"items__product__product_code": product_code}
            )
            
            if not purchase_orders:
                return self._create_error_result(
                    f"No purchase history found for product {product_code}"
                )
            
            # Extract unique suppliers
            supplier_codes = set()
            for po in purchase_orders:
                supplier_codes.add(po["supplier"]["supplier_code"])
            
            # Analyze each supplier
            supplier_analyses = []
            for supplier_code in supplier_codes:
                supplier = await self.erp_client.get_supplier(supplier_code)
                shipments = await self._get_shipment_history(supplier_code)
                performance = self._calculate_performance_metrics(shipments, supplier)
                
                supplier_analyses.append({
                    "supplier_code": supplier_code,
                    "supplier_name": supplier["name"],
                    "reliability_score": supplier["reliability_score"],
                    "on_time_rate": performance["on_time_delivery_rate"],
                    "avg_delay_days": performance["avg_delay_days"],
                    "risk_level": supplier["risk_level"]
                })
            
            # Sort by risk (highest risk first)
            risk_priority = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
            supplier_analyses.sort(
                key=lambda s: risk_priority.get(s['risk_level'], 0),
                reverse=True
            )
            
            # Determine overall risk
            highest_risk = supplier_analyses[0]["risk_level"] if supplier_analyses else "LOW"
            
            findings = {
                "product_code": product_code,
                "product_name": product["name"],
                "suppliers_count": len(supplier_analyses),
                "suppliers": supplier_analyses,
                "primary_supplier": supplier_analyses[0] if supplier_analyses else None,
                "highest_risk_level": highest_risk
            }
            
            recommendations = self._generate_product_supplier_recommendations(findings)
            
            # Map risk level string to RiskLevel enum
            risk_level_map = {
                'CRITICAL': RiskLevel.CRITICAL,
                'HIGH': RiskLevel.HIGH,
                'MEDIUM': RiskLevel.MEDIUM,
                'LOW': RiskLevel.LOW
            }
            risk_level = risk_level_map.get(highest_risk, RiskLevel.MEDIUM)
            
            return self.create_result(
                status=AgentStatus.WARNING if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else AgentStatus.SUCCESS,
                risk_level=risk_level,
                findings=findings,
                recommendations=recommendations,
                confidence=0.80,
                metadata={"product_code": product_code}
            )
        
        except Exception as e:
            logger.error(f"Error analyzing suppliers for product {product_code}: {e}")
            return self._create_error_result(str(e))
    
    async def _analyze_all_suppliers(self) -> AgentResult:
        """Analyze all high-risk suppliers"""
        
        try:
            # Get all suppliers
            all_suppliers = await self.get_erp_data("procurement/suppliers")
            
            # Get delayed shipments
            delayed_shipments = await self.erp_client.get_delayed_shipments()
            
            # Categorize suppliers by risk
            critical_suppliers = []
            high_risk_suppliers = []
            
            for supplier in all_suppliers:
                risk_level = supplier.get("risk_level")
                reliability = supplier.get("reliability_score", 100)
                
                supplier_summary = {
                    "supplier_code": supplier["supplier_code"],
                    "name": supplier["name"],
                    "reliability_score": reliability,
                    "risk_level": risk_level
                }
                
                if risk_level == "CRITICAL":
                    critical_suppliers.append(supplier_summary)
                elif risk_level == "HIGH":
                    high_risk_suppliers.append(supplier_summary)
            
            # Calculate system-wide metrics
            total_suppliers = len(all_suppliers)
            active_suppliers = len([s for s in all_suppliers if s.get("is_active", False)])
            avg_reliability = statistics.mean(
                [s.get("reliability_score", 100) for s in all_suppliers]
            ) if all_suppliers else 100
            
            # Determine overall risk
            if critical_suppliers:
                risk_level = RiskLevel.CRITICAL
            elif len(high_risk_suppliers) > total_suppliers * 0.2:  # >20% high risk
                risk_level = RiskLevel.HIGH
            elif high_risk_suppliers:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW
            
            findings = {
                "total_suppliers": total_suppliers,
                "active_suppliers": active_suppliers,
                "critical_suppliers_count": len(critical_suppliers),
                "high_risk_suppliers_count": len(high_risk_suppliers),
                "delayed_shipments_count": len(delayed_shipments),
                "avg_reliability_score": round(avg_reliability, 2),
                "critical_suppliers": critical_suppliers[:5],  # Top 5
                "high_risk_suppliers": high_risk_suppliers[:5]  # Top 5
            }
            
            recommendations = self._generate_system_recommendations(findings)
            
            return self.create_result(
                status=AgentStatus.WARNING if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else AgentStatus.SUCCESS,
                risk_level=risk_level,
                findings=findings,
                recommendations=recommendations,
                confidence=0.90,
                metadata={"analysis_scope": "system_wide"}
            )
        
        except Exception as e:
            logger.error(f"Error analyzing all suppliers: {e}")
            return self._create_error_result(str(e))
    
    async def _get_shipment_history(
        self,
        supplier_code: str
    ) -> List[Dict]:
        """Get shipment history for a supplier"""
        
        # Get shipments from last analysis_period_days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.analysis_period_days)
        
        # Get all shipments for this supplier
        shipments = await self.get_erp_data(
            "procurement/shipments",
            {
                "purchase_order__supplier__supplier_code": supplier_code,
                "status": "RECEIVED"  # Only completed shipments
            }
        )
        
        return shipments
    
    async def _get_pending_shipments(
        self,
        supplier_code: str
    ) -> List[Dict]:
        """Get pending shipments from a supplier"""
        
        shipments = await self.get_erp_data(
            "procurement/shipments",
            {
                "purchase_order__supplier__supplier_code": supplier_code,
                "status__in": "IN_TRANSIT,DELAYED,PENDING"
            }
        )
        
        return shipments
    
    def _calculate_performance_metrics(
        self,
        shipments: List[Dict],
        supplier: Dict
    ) -> Dict[str, Any]:
        """Calculate supplier performance metrics"""
        
        if not shipments:
            return {
                "total_shipments": 0,
                "on_time_deliveries": 0,
                "delayed_deliveries": 0,
                "on_time_delivery_rate": 0,
                "avg_delay_days": 0,
                "max_delay_days": 0,
                "data_available": False
            }
        
        total_shipments = len(shipments)
        delayed_shipments = [s for s in shipments if s.get("delay_days", 0) > 0]
        on_time_shipments = total_shipments - len(delayed_shipments)
        
        # Calculate on-time delivery rate
        on_time_rate = (on_time_shipments / total_shipments * 100) if total_shipments > 0 else 100
        
        # Calculate average delay
        delays = [s.get("delay_days", 0) for s in delayed_shipments]
        avg_delay = statistics.mean(delays) if delays else 0
        max_delay = max(delays) if delays else 0
        
        # Recent performance (last 30 days)
        recent_date = datetime.now() - timedelta(days=30)
        recent_shipments = [
            s for s in shipments 
            if datetime.fromisoformat(s.get("actual_arrival_date", "2000-01-01")) > recent_date
        ]
        recent_delayed = len([s for s in recent_shipments if s.get("delay_days", 0) > 0])
        recent_on_time_rate = (
            ((len(recent_shipments) - recent_delayed) / len(recent_shipments) * 100)
            if recent_shipments else 100
        )
        
        return {
            "total_shipments": total_shipments,
            "on_time_deliveries": on_time_shipments,
            "delayed_deliveries": len(delayed_shipments),
            "on_time_delivery_rate": round(on_time_rate, 2),
            "recent_on_time_rate": round(recent_on_time_rate, 2),
            "avg_delay_days": round(avg_delay, 2),
            "max_delay_days": max_delay,
            "data_available": True
        }
    
    def _analyze_pending_shipments(
        self,
        pending_shipments: List[Dict]
    ) -> Dict[str, Any]:
        """Analyze pending shipments for current risks"""
        
        if not pending_shipments:
            return {
                "pending_shipments_count": 0,
                "already_delayed_count": 0,
                "at_risk_count": 0,
                "current_risk": "none"
            }
        
        already_delayed = [s for s in pending_shipments if s.get("delay_days", 0) > 0]
        
        # Check for shipments at risk (expected soon but not yet shipped)
        at_risk = []
        for shipment in pending_shipments:
            if shipment.get("status") == "PENDING":
                expected = datetime.fromisoformat(shipment.get("expected_arrival_date"))
                days_until = (expected - datetime.now()).days
                if days_until < 3:  # Expected in less than 3 days but not shipped
                    at_risk.append(shipment)
        
        # Determine current risk level
        if len(already_delayed) > 2:
            current_risk = "critical"
        elif already_delayed or at_risk:
            current_risk = "high"
        else:
            current_risk = "low"
        
        return {
            "pending_shipments_count": len(pending_shipments),
            "already_delayed_count": len(already_delayed),
            "at_risk_count": len(at_risk),
            "current_risk": current_risk,
            "delayed_shipments": [
                {
                    "shipment_number": s.get("shipment_number"),
                    "delay_days": s.get("delay_days")
                }
                for s in already_delayed[:3]  # Top 3
            ]
        }
    
    def _assess_supplier_risk(
        self,
        performance: Dict,
        pending_analysis: Dict,
        supplier: Dict
    ) -> Dict[str, Any]:
        """Assess overall supplier risk"""
        
        risk_factors = []
        risk_score = 0  # 0-100, higher is worse
        
        # Factor 1: On-time delivery rate
        on_time_rate = performance.get("on_time_delivery_rate", 100)
        if on_time_rate < 70:
            risk_factors.append(f"Poor on-time delivery rate: {on_time_rate}%")
            risk_score += 30
        elif on_time_rate < 85:
            risk_factors.append(f"Below-average on-time delivery: {on_time_rate}%")
            risk_score += 15
        
        # Factor 2: Average delay
        avg_delay = performance.get("avg_delay_days", 0)
        if avg_delay > self.critical_delay_days:
            risk_factors.append(f"Significant average delay: {avg_delay} days")
            risk_score += 25
        elif avg_delay > self.delay_threshold_days:
            risk_factors.append(f"Moderate average delay: {avg_delay} days")
            risk_score += 10
        
        # Factor 3: Recent performance degradation
        recent_rate = performance.get("recent_on_time_rate", 100)
        if recent_rate < on_time_rate - 10:  # 10% drop
            risk_factors.append("Recent performance degradation detected")
            risk_score += 20
        
        # Factor 4: Current pending delays
        already_delayed = pending_analysis.get("already_delayed_count", 0)
        if already_delayed > 0:
            risk_factors.append(f"{already_delayed} pending shipment(s) already delayed")
            risk_score += already_delayed * 10
        
        # Factor 5: Reliability score
        reliability = supplier.get("reliability_score", 100)
        if reliability < 70:
            risk_factors.append(f"Low reliability score: {reliability}")
            risk_score += 20
        
        # Factor 6: Max delay incidents
        max_delay = performance.get("max_delay_days", 0)
        if max_delay > 14:
            risk_factors.append(f"Major delay incident: {max_delay} days")
            risk_score += 15
        
        # Determine risk category
        if risk_score >= 70:
            risk_category = "CRITICAL"
        elif risk_score >= 40:
            risk_category = "HIGH"
        elif risk_score >= 20:
            risk_category = "MEDIUM"
        else:
            risk_category = "LOW"
        
        return {
            "risk_score": min(risk_score, 100),
            "risk_category": risk_category,
            "risk_factors": risk_factors,
            "risk_factors_count": len(risk_factors)
        }
    
    def _determine_risk_level(self, risk_assessment: Dict) -> RiskLevel:
        """Convert risk category to RiskLevel enum"""
        
        category = risk_assessment.get("risk_category", "LOW")
        
        mapping = {
            "CRITICAL": RiskLevel.CRITICAL,
            "HIGH": RiskLevel.HIGH,
            "MEDIUM": RiskLevel.MEDIUM,
            "LOW": RiskLevel.LOW
        }
        
        return mapping.get(category, RiskLevel.MEDIUM)
    
    def _generate_recommendations(
        self,
        risk_assessment: Dict,
        supplier: Dict,
        performance: Dict
    ) -> List[str]:
        """Generate recommendations based on supplier risk"""
        
        recommendations = []
        risk_category = risk_assessment.get("risk_category")
        risk_factors = risk_assessment.get("risk_factors", [])
        
        # Critical risk recommendations
        if risk_category == "CRITICAL":
            recommendations.append(
                f"🔴 CRITICAL: Supplier {supplier['supplier_code']} poses significant risk. "
                f"Immediate action required."
            )
            recommendations.append(
                "🔍 Initiate supplier review meeting within 48 hours"
            )
            recommendations.append(
                "🔄 Identify and qualify alternative suppliers immediately"
            )
            recommendations.append(
                "📦 Increase safety stock for items from this supplier"
            )
        
        # High risk recommendations
        elif risk_category == "HIGH":
            recommendations.append(
                f"⚠️ HIGH RISK: Supplier {supplier['supplier_code']} showing concerning patterns"
            )
            recommendations.append(
                "📞 Schedule performance review with supplier"
            )
            recommendations.append(
                "🔄 Have backup supplier on standby"
            )
        
        # Medium risk recommendations
        elif risk_category == "MEDIUM":
            recommendations.append(
                f"⚠️ Monitor supplier {supplier['supplier_code']} closely"
            )
            recommendations.append(
                "📊 Track performance metrics weekly"
            )
        
        # Specific recommendations based on factors
        on_time_rate = performance.get("on_time_delivery_rate", 100)
        if on_time_rate < 80:
            recommendations.append(
                f"📈 Work with supplier to improve on-time delivery from {on_time_rate}% to >95%"
            )
        
        avg_delay = performance.get("avg_delay_days", 0)
        if avg_delay > 5:
            recommendations.append(
                f"⏰ Address average delay of {avg_delay} days with supplier"
            )
        
        # Risk factor specific recommendations
        for factor in risk_factors[:3]:  # Top 3 factors
            if "degradation" in factor.lower():
                recommendations.append(
                    "📉 Investigate root cause of recent performance decline"
                )
            elif "delayed" in factor.lower():
                recommendations.append(
                    "🚚 Follow up on pending delayed shipments"
                )
        
        # Default recommendation
        if not recommendations:
            recommendations.append(
                f"✅ Supplier {supplier['supplier_code']} performing well. Continue standard monitoring."
            )
        
        return recommendations
    
    def _generate_product_supplier_recommendations(
        self,
        findings: Dict
    ) -> List[str]:
        """Generate recommendations for product suppliers"""
        
        recommendations = []
        highest_risk = findings.get("highest_risk_level")
        suppliers_count = findings.get("suppliers_count", 0)
        
        if highest_risk in ["CRITICAL", "HIGH"]:
            recommendations.append(
                f"⚠️ Primary supplier has {highest_risk} risk level"
            )
            
            if suppliers_count == 1:
                recommendations.append(
                    "🔄 URGENT: Single source risk. Identify and qualify second supplier."
                )
            else:
                recommendations.append(
                    "🔄 Consider shifting volume to more reliable supplier"
                )
        
        if suppliers_count == 1:
            recommendations.append(
                "📊 Recommend developing multi-source strategy to reduce risk"
            )
        
        return recommendations
    
    def _generate_system_recommendations(
        self,
        findings: Dict
    ) -> List[str]:
        """Generate system-wide supplier recommendations"""
        
        recommendations = []
        critical_count = findings.get("critical_suppliers_count", 0)
        high_risk_count = findings.get("high_risk_suppliers_count", 0)
        
        if critical_count > 0:
            recommendations.append(
                f"🔴 {critical_count} supplier(s) at CRITICAL risk level. "
                f"Initiate supplier risk mitigation program."
            )
        
        if high_risk_count > 5:
            recommendations.append(
                f"⚠️ {high_risk_count} supplier(s) at HIGH risk. "
                f"Conduct systematic supplier performance review."
            )
        
        avg_reliability = findings.get("avg_reliability_score", 100)
        if avg_reliability < 85:
            recommendations.append(
                f"📉 Average supplier reliability at {avg_reliability}%. "
                f"Implement supplier development program."
            )
        
        if not recommendations:
            recommendations.append(
                "✅ Supplier base health good. Continue standard risk monitoring."
            )
        
        return recommendations
    
    def _create_error_result(self, error_message: str) -> AgentResult:
        """Create an error result"""
        return self.create_result(
            status=AgentStatus.ERROR,
            risk_level=RiskLevel.UNKNOWN,
            findings={"error": error_message},
            recommendations=["Check supplier risk agent logs for details"],
            confidence=0.0,
            metadata={"error": True}
        )