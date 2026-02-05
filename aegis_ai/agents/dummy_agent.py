from typing import Dict, Any
from agents.base_agent import BaseAgent
from schemas.agent_schemas import AgentResult, AgentStatus, RiskLevel


class DummyAgent(BaseAgent):
    """
    Dummy agent for testing the framework
    """
    
    def __init__(self):
        super().__init__(name="Dummy Agent")
    
    async def analyze(self, context: Dict[str, Any]) -> AgentResult:
        """
        Simple dummy analysis
        """
        
        # Simulate analysis
        product_code = context.get("product_code", "UNKNOWN")
        
        findings = {
            "product_code": product_code,
            "analysis_performed": True,
            "test_metric": 42
        }
        
        recommendations = [
            "This is a test recommendation",
            "Agent framework is working correctly"
        ]
        
        return self.create_result(
            status=AgentStatus.SUCCESS,
            risk_level=RiskLevel.LOW,
            findings=findings,
            recommendations=recommendations,
            confidence=0.95,
            metadata={"is_dummy": True}
        )