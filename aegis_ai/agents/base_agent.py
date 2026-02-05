from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import time

from services.erp_client import ERPClient
from schemas.agent_schemas import AgentResult, AgentStatus, RiskLevel

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents
    All agents must inherit from this class
    """
    
    def __init__(self, name: str):
        self.name = name
        self.erp_client = ERPClient()
        logger.info(f"Initialized {self.name}")
    
    @abstractmethod
    async def analyze(self, context: Dict[str, Any]) -> AgentResult:
        """
        Core analysis method - must be implemented by each agent
        
        Args:
            context: Dictionary containing analysis context
        
        Returns:
            AgentResult with findings and recommendations
        """
        pass
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Execute agent analysis with timing and error handling
        
        Args:
            context: Analysis context
        
        Returns:
            AgentResult
        """
        start_time = time.time()
        
        try:
            logger.info(f"{self.name} starting analysis...")
            result = await self.analyze(context)
            
            # Add execution time
            execution_time = (time.time() - start_time) * 1000  # Convert to ms
            result.execution_time_ms = execution_time
            
            logger.info(
                f"{self.name} completed in {execution_time:.2f}ms "
                f"- Risk: {result.risk_level}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"{self.name} error: {e}", exc_info=True)
            
            # Return error result
            execution_time = (time.time() - start_time) * 1000
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                risk_level=RiskLevel.UNKNOWN,
                findings={"error": str(e)},
                recommendations=["Check agent logs for details"],
                confidence=0.0,
                metadata={"error_type": type(e).__name__},
                execution_time_ms=execution_time
            )
    
    async def get_erp_data(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> Any:
        """
        Fetch data from ERP API
        
        Args:
            endpoint: API endpoint
            params: Query parameters
        
        Returns:
            API response data
        """
        return await self.erp_client.get(endpoint, params)
    
    async def post_erp_data(self, endpoint: str, data: Dict) -> Any:
        """
        Post data to ERP API
        
        Args:
            endpoint: API endpoint
            data: Request body
        
        Returns:
            API response data
        """
        return await self.erp_client.post(endpoint, data)
    
    def create_result(
        self,
        status: AgentStatus,
        risk_level: RiskLevel,
        findings: Dict[str, Any],
        recommendations: List[str],
        confidence: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Helper method to create AgentResult
        
        Args:
            status: Agent status
            risk_level: Risk level
            findings: Analysis findings
            recommendations: List of recommendations
            confidence: Confidence score (0-1)
            metadata: Additional metadata
        
        Returns:
            AgentResult
        """
        return AgentResult(
            agent_name=self.name,
            status=status,
            risk_level=risk_level,
            findings=findings,
            recommendations=recommendations,
            confidence=confidence,
            metadata=metadata or {}
        )