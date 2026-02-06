import asyncio
import httpx
import json
from datetime import datetime


BASE_URL = "http://localhost:8001"


async def test_orchestrator_info():
    """Test orchestrator info endpoint"""
    print("\n" + "="*60)
    print("Test 1: Orchestrator Information")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/orchestrate/info")
        info = response.json()
        
        print(f"\n📊 Available Agents: {info['agent_count']}")
        for agent in info['available_agents']:
            print(f"  • {agent}")
        
        print(f"\n🔑 Intent Keywords:")
        for intent, keywords in info['intent_keywords'].items():
            print(f"  • {intent}: {', '.join(keywords[:5])}...")


async def test_specific_item():
    """Test orchestration for specific item"""
    print("\n" + "="*60)
    print("Test 2: Specific Item Analysis")
    print("="*60)
    
    request_data = {
        "query": "Check inventory status for RM-STEEL-001 at main warehouse",
        "context": {
            "product_code": "RM-STEEL-001",
            "warehouse_code": "WH-MAIN-01"
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/orchestrate",
            json=request_data
        )
        
        result = response.json()
        
        print(f"\n🆔 Decision ID: {result['decision_id']}")
        print(f"⏰ Timestamp: {result['timestamp']}")
        print(f"⚠️  Overall Risk: {result['overall_risk_level'].upper()}")
        print(f"🎯 Action Required: {result['action_required']}")
        
        print(f"\n📝 Summary:")
        print(f"  {result['summary']}")
        
        print(f"\n🤖 Agent Results:")
        for agent_result in result['agent_results']:
            print(f"  • {agent_result['agent_name']}: {agent_result['risk_level']} ({agent_result['execution_time_ms']:.2f}ms)")
        
        print(f"\n💡 Recommended Actions:")
        for i, action in enumerate(result['recommended_actions'], 1):
            print(f"  {i}. {action}")
        
        print(f"\n📊 Metadata:")
        metadata = result['metadata']
        print(f"  • Query: {metadata.get('query')}")
        print(f"  • Agents Executed: {metadata.get('agents_executed')}")
        print(f"  • Total Execution Time: {metadata.get('total_execution_time_ms', 0):.2f}ms")


async def test_warehouse_health():
    """Test warehouse-wide analysis"""
    print("\n" + "="*60)
    print("Test 3: Warehouse Health Check")
    print("="*60)
    
    request_data = {
        "query": "How is warehouse WH-MAIN-01 doing? Any critical stock issues?",
        "context": {
            "warehouse_code": "WH-MAIN-01"
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/orchestrate",
            json=request_data
        )
        
        result = response.json()
        
        print(f"\n⚠️  Overall Risk: {result['overall_risk_level'].upper()}")
        print(f"🎯 Action Required: {result['action_required']}")
        print(f"\n📝 Summary: {result['summary']}")
        
        print(f"\n💡 Top Recommendations:")
        for i, action in enumerate(result['recommended_actions'][:3], 1):
            print(f"  {i}. {action}")


async def test_system_wide():
    """Test system-wide comprehensive analysis"""
    print("\n" + "="*60)
    print("Test 4: System-Wide Health Check")
    print("="*60)
    
    request_data = {
        "query": "Give me a full supply chain health report with all critical issues",
        "context": {}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/orchestrate",
            json=request_data
        )
        
        result = response.json()
        
        print(f"\n🆔 Decision ID: {result['decision_id']}")
        print(f"⚠️  Overall Risk: {result['overall_risk_level'].upper()}")
        print(f"🎯 Action Required: {result['action_required']}")
        
        print(f"\n📝 Executive Summary:")
        print(f"  {result['summary']}")
        
        print(f"\n🤖 Agents Executed:")
        for agent_result in result['agent_results']:
            print(f"  • {agent_result['agent_name']}")
            print(f"    - Risk: {agent_result['risk_level']}")
            print(f"    - Status: {agent_result['status']}")
            print(f"    - Confidence: {agent_result['confidence']}")
        
        print(f"\n💡 Priority Actions:")
        for i, action in enumerate(result['recommended_actions'][:5], 1):
            print(f"  {i}. {action}")


async def test_natural_language():
    """Test natural language queries"""
    print("\n" + "="*60)
    print("Test 5: Natural Language Query")
    print("="*60)
    
    queries = [
        {
            "query": "Do I have enough steel in stock or should I reorder?",
            "context": {"product_code": "RM-STEEL-001"}
        },
        {
            "query": "Show me all critical inventory issues",
            "context": {}
        },
        {
            "query": "What's the stock situation for widgets?",
            "context": {"product_code": "FG-WIDGET-001"}
        }
    ]
    
    for i, request_data in enumerate(queries, 1):
        print(f"\n--- Query {i} ---")
        print(f"Q: {request_data['query']}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BASE_URL}/api/orchestrate",
                json=request_data
            )
            
            result = response.json()
            print(f"A: Risk={result['overall_risk_level']}, Action={result['action_required']}")
            print(f"   {result['recommended_actions'][0] if result['recommended_actions'] else 'No actions needed'}")


async def main():
    """Run all orchestrator tests"""
    print("\n" + "="*60)
    print("🛡️ AegisChain Orchestrator Test Suite")
    print("="*60)
    
    try:
        await test_orchestrator_info()
        await test_specific_item()
        await test_warehouse_health()
        await test_system_wide()
        await test_natural_language()
        
        print("\n" + "="*60)
        print("✅ All orchestrator tests completed!")
        print("="*60)
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())