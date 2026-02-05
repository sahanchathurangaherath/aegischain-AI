from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class RiskLevel(str, Enum):
    """Risk level enumeration"""
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentStatus(str, Enum):
    """Agent execution status"""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


class AgentContext(BaseModel):
    """
    Context passed to agents for analysis
    """
    product_code: Optional[str] = None
    warehouse_code: Optional[str] = None
    supplier_code: Optional[str] = None
    analysis_type: str = Field(default="general", description="Type of analysis to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_code": "RM-STEEL-001",
                "warehouse_code": "WH-MAIN-01",
                "analysis_type": "inventory_check",
                "parameters": {"days_history": 30}
            }
        }


class AgentResult(BaseModel):
    """
    Result returned by an agent
    """
    agent_name: str
    status: AgentStatus
    risk_level: RiskLevel
    findings: Dict[str, Any]
    recommendations: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_name": "Inventory Agent",
                "status": "warning",
                "risk_level": "medium",
                "findings": {
                    "current_stock": 150,
                    "reorder_point": 200,
                    "variance": 10
                },
                "recommendations": [
                    "Schedule reorder within 3 days",
                    "Verify physical count"
                ],
                "confidence": 0.85,
                "metadata": {"warehouse": "WH-MAIN-01"},
                "execution_time_ms": 245.5
            }
        }


class OrchestrationRequest(BaseModel):
    """
    Request to the orchestrator
    """
    query: str = Field(description="Natural language query or command")
    context: AgentContext
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Check inventory status for product RM-STEEL-001",
                "context": {
                    "product_code": "RM-STEEL-001",
                    "warehouse_code": "WH-MAIN-01"
                }
            }
        }


class OrchestrationResponse(BaseModel):
    """
    Response from the orchestrator
    """
    decision_id: str
    timestamp: datetime
    overall_risk_level: RiskLevel
    summary: str
    action_required: bool
    recommended_actions: List[str]
    agent_results: List[AgentResult]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "decision_id": "dec-123456",
                "timestamp": "2024-01-15T10:30:00Z",
                "overall_risk_level": "medium",
                "summary": "Inventory check complete. Stock below reorder point.",
                "action_required": True,
                "recommended_actions": [
                    "Create purchase order for 500 units",
                    "Schedule delivery within 7 days"
                ],
                "agent_results": [],
                "metadata": {"total_agents": 2}
            }
        }