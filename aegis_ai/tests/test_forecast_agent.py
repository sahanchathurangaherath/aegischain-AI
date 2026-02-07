import asyncio
import httpx


BASE_URL = "http://localhost:8001"


async def test_specific_item_forecast():
    """Test forecast for specific item"""
    print("\n" + "="*60)
    print("Test 1: Specific Item Forecast")
    print("="*60)
    
    request_data = {
        "product_code": "RM-STEEL-001",
        "warehouse_code": "WH-MAIN-01",
        "analysis_type": "demand_forecast"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/agents/forecast",
            json=request_data
        )
        
        result = response.json()
        
        print(f"\n📊 Agent: {result['agent_name']}")
        print(f"⚠️  Risk Level: {result['risk_level'].upper()}")
        print(f"🎯 Confidence: {result['confidence']}")
        
        findings = result['findings']
        print(f"\n📈 Forecast Results:")
        print(f"  • Current Stock: {findings.get('current_stock')}")
        print(f"  • Daily Avg Demand: {findings.get('daily_avg')}")
        print(f"  • Total Forecast ({findings.get('forecast_horizon_days', 30)} days): {findings.get('total_demand')}")
        print(f"  • Days of Supply: {findings.get('days_of_supply')}")
        print(f"  • Trend: {findings.get('trend')}")
        
        if findings.get('shortage_date'):
            print(f"  • ⚠️  Predicted Shortage Date: {findings['shortage_date']}")
        
        print(f"\n💡 Recommendations:")
        for i, rec in enumerate(result['recommendations'], 1):
            print(f"  {i}. {rec}")


async def test_multi_agent_orchestration():
    """Test orchestration with multiple agents"""
    print("\n" + "="*60)
    print("Test 2: Multi-Agent Orchestration")
    print("="*60)
    
    request_data = {
        "query": "Analyze steel inventory status and predict future needs",
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
        print(f"⚠️  Overall Risk: {result['overall_risk_level'].upper()}")
        print(f"🎯 Action Required: {result['action_required']}")
        
        print(f"\n🤖 Agents Executed:")
        for agent_result in result['agent_results']:
            print(f"  • {agent_result['agent_name']}: {agent_result['risk_level']} ({agent_result['execution_time_ms']:.2f}ms)")
        
        print(f"\n📝 Summary:")
        print(f"  {result['summary']}")
        
        print(f"\n💡 Combined Recommendations:")
        for i, action in enumerate(result['recommended_actions'][:5], 1):
            print(f"  {i}. {action}")


async def test_warehouse_forecast():
    """Test warehouse-level forecast"""
    print("\n" + "="*60)
    print("Test 3: Warehouse Forecast")
    print("="*60)
    
    request_data = {
        "warehouse_code": "WH-MAIN-01",
        "analysis_type": "warehouse_forecast"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/agents/forecast",
            json=request_data
        )
        
        result = response.json()
        
        print(f"\n📊 Agent: {result['agent_name']}")
        print(f"⚠️  Risk Level: {result['risk_level'].upper()}")
        
        findings = result['findings']
        print(f"\n📦 Warehouse Forecast Summary:")
        print(f"  • Total Products: {findings.get('total_products')}")
        print(f"  • Critical Items: {findings.get('critical_items_count')}")
        print(f"  • Low Supply Items: {findings.get('low_supply_items_count')}")
        
        if findings.get('critical_items'):
            print(f"\n🔴 Critical Items:")
            for item in findings['critical_items']:
                print(f"  • {item['product']}: {item['days_of_supply']} days of supply")
        
        print(f"\n💡 Recommendations:")
        for rec in result['recommendations']:
            print(f"  • {rec}")


async def main():
    """Run all forecast tests"""
    print("\n" + "="*60)
    print("🛡️ AegisChain Forecast Agent Test Suite")
    print("="*60)
    
    try:
        await test_specific_item_forecast()
        await test_warehouse_forecast()
        await test_multi_agent_orchestration()
        
        print("\n" + "="*60)
        print("✅ All forecast agent tests completed!")
        print("="*60)
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())