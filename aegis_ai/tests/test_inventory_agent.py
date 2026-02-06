import asyncio
import httpx
import json


BASE_URL = "http://localhost:8001"


async def test_specific_item():
    """Test inventory analysis for specific item"""
    print("\n" + "="*60)
    print("Test 1: Analyzing Specific Item")
    print("="*60)
    
    request_data = {
        "product_code": "RM-STEEL-001",
        "warehouse_code": "WH-MAIN-01",
        "analysis_type": "inventory_check"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/agents/inventory",
            json=request_data
        )
        
        result = response.json()
        
        print(f"\n📊 Agent: {result['agent_name']}")
        print(f"⚠️  Risk Level: {result['risk_level'].upper()}")
        print(f"✅ Status: {result['status']}")
        print(f"🎯 Confidence: {result['confidence']}")
        print(f"⏱️  Execution Time: {result['execution_time_ms']:.2f}ms")
        
        print(f"\n📋 Key Findings:")
        findings = result['findings']
        for key, value in findings.items():
            if key not in ['warehouses', 'critical_items', 'low_stock_items']:
                print(f"  • {key}: {value}")
        
        print(f"\n💡 Recommendations:")
        for i, rec in enumerate(result['recommendations'], 1):
            print(f"  {i}. {rec}")


async def test_warehouse():
    """Test warehouse analysis"""
    print("\n" + "="*60)
    print("Test 2: Analyzing Warehouse")
    print("="*60)
    
    request_data = {
        "warehouse_code": "WH-MAIN-01",
        "analysis_type": "warehouse_check"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/agents/inventory",
            json=request_data
        )
        
        result = response.json()
        
        print(f"\n📊 Agent: {result['agent_name']}")
        print(f"⚠️  Risk Level: {result['risk_level'].upper()}")
        print(f"✅ Status: {result['status']}")
        
        findings = result['findings']
        print(f"\n📋 Warehouse Summary:")
        print(f"  • Total Items: {findings['total_items']}")
        print(f"  • Critical Items: {findings['critical_items_count']}")
        print(f"  • Low Stock Items: {findings['low_stock_items_count']}")
        print(f"  • Health: {findings['health_percentage']}%")
        
        print(f"\n💡 Recommendations:")
        for rec in result['recommendations']:
            print(f"  • {rec}")


async def test_system_wide():
    """Test system-wide analysis"""
    print("\n" + "="*60)
    print("Test 3: System-Wide Analysis")
    print("="*60)
    
    request_data = {
        "analysis_type": "system_check"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/agents/inventory",
            json=request_data
        )
        
        result = response.json()
        
        print(f"\n📊 Agent: {result['agent_name']}")
        print(f"⚠️  Risk Level: {result['risk_level'].upper()}")
        
        findings = result['findings']
        print(f"\n📋 System-Wide Inventory Health:")
        print(f"  • Total Inventory Items: {findings['total_inventory_items']}")
        print(f"  • Critical Items: {findings['critical_items_count']} ({findings['critical_percentage']}%)")
        print(f"  • Low Stock Items: {findings['low_stock_items_count']} ({findings['low_stock_percentage']}%)")
        print(f"  • Healthy Items: {findings['healthy_items_count']} ({findings['healthy_percentage']}%)")
        
        if findings.get('top_critical_items'):
            print(f"\n🔴 Top Critical Items:")
            for item in findings['top_critical_items']:
                print(f"  • {item['product']} @ {item['warehouse']}: {item['quantity']} units")
        
        print(f"\n💡 Recommendations:")
        for rec in result['recommendations']:
            print(f"  • {rec}")


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🛡️ AegisChain Inventory Agent Test Suite")
    print("="*60)
    
    try:
        await test_specific_item()
        await test_warehouse()
        await test_system_wide()
        
        print("\n" + "="*60)
        print("✅ All inventory agent tests completed!")
        print("="*60)
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())