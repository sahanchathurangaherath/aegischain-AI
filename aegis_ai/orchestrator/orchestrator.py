import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import logging

from orchestrator.intent_classifier import IntentClassifier
from agents.inventory_agent import InventoryAgent
from schemas.agent_schemas import (
    AgentResult, 
    OrchestrationRequest, 
    OrchestrationResponse,
    RiskLevel
)

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Central orchestration engine that:
    1. Classifies user intent
    2. Executes relevant agents in parallel
    3. Combines results
    4. Makes final decisions
    5. Logs everything
    """
    
    def __init__(self):
        self.classifier = IntentClassifier()
        
        # Initialize available agents
        self.agents = {
            'inventory': InventoryAgent(),
            # 'forecast': ForecastAgent(),        # Phase 8
            # 'supplier_risk': SupplierRiskAgent() # Phase 9
        }
        
        logger.info(f"Orchestrator initialized with {len(self.agents)} agents")
    
    async def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResponse:
        """
        Main orchestration method
        
        Args:
            request: OrchestrationRequest with query and context
        
        Returns:
            OrchestrationResponse with combined decision
        """
        decision_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        logger.info(f"[{decision_id}] Starting orchestration for: '{request.query}'")
        
        try:
            # Step 1: Classify intent - which agents to run?
            agents_to_run = self.classifier.classify(
                request.query, 
                request.context.model_dump()
            )
            
            # Step 2: Execute agents in parallel
            agent_results = await self._execute_agents(
                agents_to_run, 
                request.context.model_dump()
            )
            
            # Step 3: Combine results
            combined_result = self._combine_results(agent_results)
            
            # Step 4: Make final decision
            decision = self._make_decision(
                combined_result, 
                request.context.model_dump()
            )
            
            # Step 5: Create response
            response = OrchestrationResponse(
                decision_id=decision_id,
                timestamp=timestamp,
                overall_risk_level=decision['overall_risk_level'],
                summary=decision['summary'],
                action_required=decision['action_required'],
                recommended_actions=decision['recommended_actions'],
                agent_results=agent_results,
                metadata={
                    'query': request.query,
                    'agents_executed': agents_to_run,
                    'total_execution_time_ms': sum(
                        r.execution_time_ms or 0 for r in agent_results
                    )
                }
            )
            
            # Step 6: Log decision (in production, save to database)
            logger.info(
                f"[{decision_id}] Orchestration complete - "
                f"Risk: {response.overall_risk_level}, "
                f"Action Required: {response.action_required}"
            )
            
            return response
        
        except Exception as e:
            logger.error(f"[{decision_id}] Orchestration error: {e}", exc_info=True)
            
            # Return error response
            return OrchestrationResponse(
                decision_id=decision_id,
                timestamp=timestamp,
                overall_risk_level=RiskLevel.UNKNOWN,
                summary=f"Orchestration failed: {str(e)}",
                action_required=True,
                recommended_actions=["Review orchestration logs", "Contact system administrator"],
                agent_results=[],
                metadata={'error': str(e)}
            )
    
    async def _execute_agents(
        self, 
        agent_names: List[str], 
        context: Dict[str, Any]
    ) -> List[AgentResult]:
        """
        Execute multiple agents in parallel
        
        Args:
            agent_names: List of agent names to execute
            context: Execution context
        
        Returns:
            List of AgentResult objects
        """
        # Filter to only available agents
        available_agents = [
            name for name in agent_names 
            if name in self.agents
        ]
        
        if not available_agents:
            logger.warning(f"No available agents for: {agent_names}")
            return []
        
        # Sort by priority
        available_agents.sort(
            key=lambda name: self.classifier.get_agent_priority(name)
        )
        
        logger.info(f"Executing agents: {available_agents}")
        
        # Execute agents in parallel
        tasks = []
        for agent_name in available_agents:
            agent = self.agents[agent_name]
            tasks.append(agent.execute(context))
        
        # Wait for all agents to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        agent_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Agent {available_agents[i]} failed: {result}")
                # Create error result
                error_result = AgentResult(
                    agent_name=available_agents[i],
                    status='error',
                    risk_level=RiskLevel.UNKNOWN,
                    findings={'error': str(result)},
                    recommendations=['Check agent logs'],
                    confidence=0.0
                )
                agent_results.append(error_result)
            else:
                agent_results.append(result)
        
        return agent_results
    
    def _combine_results(self, agent_results: List[AgentResult]) -> Dict[str, Any]:
        """
        Combine results from multiple agents
        
        Args:
            agent_results: List of agent results
        
        Returns:
            Combined findings and metadata
        """
        if not agent_results:
            return {
                'overall_risk_level': RiskLevel.UNKNOWN,
                'all_findings': {},
                'all_recommendations': [],
                'agent_count': 0
            }
        
        # Aggregate all findings
        all_findings = {}
        all_recommendations = []
        
        for result in agent_results:
            all_findings[result.agent_name] = result.findings
            all_recommendations.extend(result.recommendations)
        
        # Calculate overall risk level (take highest risk)
        overall_risk = self._calculate_overall_risk(agent_results)
        
        # Remove duplicate recommendations
        unique_recommendations = list(dict.fromkeys(all_recommendations))
        
        return {
            'overall_risk_level': overall_risk,
            'all_findings': all_findings,
            'all_recommendations': unique_recommendations,
            'agent_count': len(agent_results),
            'agent_names': [r.agent_name for r in agent_results]
        }
    
    def _calculate_overall_risk(self, agent_results: List[AgentResult]) -> RiskLevel:
        """
        Determine overall risk level from all agent results
        Takes the highest risk level found
        
        Args:
            agent_results: List of agent results
        
        Returns:
            Overall risk level
        """
        risk_priority = {
            RiskLevel.CRITICAL: 4,
            RiskLevel.HIGH: 3,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 1,
            RiskLevel.UNKNOWN: 0
        }
        
        max_risk = RiskLevel.LOW
        max_priority = 0
        
        for result in agent_results:
            priority = risk_priority.get(result.risk_level, 0)
            if priority > max_priority:
                max_priority = priority
                max_risk = result.risk_level
        
        return max_risk
    
    def _make_decision(
        self, 
        combined_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make final decision based on combined agent results
        
        This is where business rules and logic are applied
        
        Args:
            combined_result: Combined results from all agents
            context: Original request context
        
        Returns:
            Final decision dictionary
        """
        overall_risk = combined_result['overall_risk_level']
        agent_count = combined_result['agent_count']
        
        # Generate summary
        summary = self._generate_summary(combined_result, context)
        
        # Determine if action is required
        action_required = overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        
        # Prioritize recommendations
        prioritized_actions = self._prioritize_actions(
            combined_result['all_recommendations'],
            overall_risk
        )
        
        decision = {
            'overall_risk_level': overall_risk,
            'summary': summary,
            'action_required': action_required,
            'recommended_actions': prioritized_actions,
            'confidence': self._calculate_decision_confidence(combined_result)
        }
        
        return decision
    
    def _generate_summary(
        self, 
        combined_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> str:
        """
        Generate human-readable summary of the analysis
        
        Args:
            combined_result: Combined agent results
            context: Request context
        
        Returns:
            Summary string
        """
        risk = combined_result['overall_risk_level']
        agent_count = combined_result['agent_count']
        agent_names = combined_result.get('agent_names', [])
        
        # Build summary based on risk level
        if risk == RiskLevel.CRITICAL:
            severity = "CRITICAL issues detected requiring IMMEDIATE attention"
        elif risk == RiskLevel.HIGH:
            severity = "HIGH risk identified. Prompt action recommended"
        elif risk == RiskLevel.MEDIUM:
            severity = "MEDIUM risk detected. Monitor situation closely"
        elif risk == RiskLevel.LOW:
            severity = "Operations within normal parameters"
        else:
            severity = "Analysis completed with uncertain results"
        
        # Add context
        context_parts = []
        if context.get('product_code'):
            context_parts.append(f"Product: {context['product_code']}")
        if context.get('warehouse_code'):
            context_parts.append(f"Warehouse: {context['warehouse_code']}")
        
        context_str = " | ".join(context_parts) if context_parts else "System-wide"
        
        # Combine
        summary = (
            f"Analysis complete from {agent_count} agent(s) "
            f"({', '.join(agent_names)}). "
            f"{severity}. "
            f"Scope: {context_str}."
        )
        
        return summary
    
    def _prioritize_actions(
        self, 
        recommendations: List[str],
        risk_level: RiskLevel
    ) -> List[str]:
        """
        Prioritize and sort recommendations
        
        Args:
            recommendations: List of all recommendations
            risk_level: Overall risk level
        
        Returns:
            Sorted list of recommendations
        """
        if not recommendations:
            return ["No specific actions required at this time"]
        
        # Define priority keywords
        critical_keywords = ['urgent', 'immediate', 'emergency', 'critical', '🔴']
        high_keywords = ['expedite', 'priority', 'soon', 'schedule', '⚠️']
        
        # Categorize recommendations
        critical_actions = []
        high_actions = []
        normal_actions = []
        
        for rec in recommendations:
            rec_lower = rec.lower()
            
            if any(kw in rec_lower for kw in critical_keywords):
                critical_actions.append(rec)
            elif any(kw in rec_lower for kw in high_keywords):
                high_actions.append(rec)
            else:
                normal_actions.append(rec)
        
        # Combine in priority order
        prioritized = critical_actions + high_actions + normal_actions
        
        # Limit to top 10 recommendations
        return prioritized[:10]
    
    def _calculate_decision_confidence(
        self, 
        combined_result: Dict[str, Any]
    ) -> float:
        """
        Calculate overall confidence in the decision
        
        Args:
            combined_result: Combined agent results
        
        Returns:
            Confidence score (0-1)
        """
        # For now, return high confidence
        # In production, this could factor in:
        # - Agent confidence scores
        # - Data quality
        # - Number of agents that agree
        # - Historical accuracy
        
        return 0.85


# Global orchestrator instance
_orchestrator_instance = None

def get_orchestrator() -> Orchestrator:
    """Get or create the global orchestrator instance"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = Orchestrator()
    return _orchestrator_instance