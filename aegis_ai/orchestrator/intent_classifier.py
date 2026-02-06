from typing import List, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)


class IntentClassifier:
    """
    Classifies user queries/commands to determine which agents should be activated
    
    This is a rule-based classifier. In production, you might use:
    - NLP models (spaCy, BERT)
    - LLM-based classification
    - Machine learning models
    """
    
    def __init__(self):
        # Keywords for each agent
        self.intent_keywords = {
            'inventory': [
                'inventory', 'stock', 'warehouse', 'variance', 'balance',
                'reorder', 'shortage', 'stockout', 'supply', 'quantity'
            ],
            'forecast': [
                'forecast', 'demand', 'predict', 'future', 'trend',
                'shortage', 'requirement', 'projection', 'estimate'
            ],
            'supplier_risk': [
                'supplier', 'vendor', 'delay', 'shipment', 'delivery',
                'risk', 'reliability', 'on-time', 'late', 'carrier'
            ]
        }
    
    def classify(self, query: str, context: Dict[str, Any]) -> List[str]:
        """
        Determine which agents should be activated
        
        Args:
            query: Natural language query or command
            context: Additional context (product_code, warehouse_code, etc.)
        
        Returns:
            List of agent names to execute
        """
        query_lower = query.lower()
        agents_needed = set()
        
        # Keyword-based classification
        for agent_name, keywords in self.intent_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                agents_needed.add(agent_name)
        
        # Context-based classification
        # If specific product/warehouse mentioned, always check inventory
        if context.get('product_code') or context.get('warehouse_code'):
            if 'check' in query_lower or 'status' in query_lower or 'analyze' in query_lower:
                agents_needed.add('inventory')
        
        # If supplier mentioned, add supplier risk
        if context.get('supplier_code'):
            agents_needed.add('supplier_risk')
        
        # Special patterns
        if re.search(r'\b(all|comprehensive|full|complete)\b', query_lower):
            # Run all available agents for comprehensive analysis
            agents_needed.update(['inventory', 'forecast', 'supplier_risk'])
        
        # If asking about future, include forecast
        if re.search(r'\b(will|future|next|upcoming|expect)\b', query_lower):
            agents_needed.add('forecast')
        
        # Default: if no agents identified and context has data, run inventory
        if not agents_needed:
            if context.get('product_code') or context.get('warehouse_code'):
                agents_needed.add('inventory')
            else:
                # Default to inventory for general queries
                agents_needed.add('inventory')
        
        agents_list = list(agents_needed)
        logger.info(f"Intent classification: '{query}' → Agents: {agents_list}")
        
        return agents_list
    
    def get_agent_priority(self, agent_name: str) -> int:
        """
        Get execution priority for an agent (lower = higher priority)
        Some agents should run before others
        """
        priority_map = {
            'inventory': 1,      # Run first - fundamental data
            'forecast': 2,       # Run second - needs inventory data
            'supplier_risk': 3   # Run third - can use forecast data
        }
        return priority_map.get(agent_name, 99)