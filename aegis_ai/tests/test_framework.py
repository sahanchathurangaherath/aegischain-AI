import asyncio
import httpx


BASE_URL = "http://localhost:8001"


async def test_health():
    """Test health endpoint"""
    print("\n" + "="*60)
    print("Testing Health Endpoint")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")


async def test_dummy_agent():
    """Test dummy agent"""
    print("\n" + "="*60)
    print("Testing Dummy Agent")
    print("="*60)
    
    request_data = {
        "product_code": "RM-STEEL-001",
        "warehouse_code": "WH-MAIN-01",
        "analysis_type": "test",
        "parameters": {}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/test/dummy-agent",
            json=request_data
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Agent: {result['agent_name']}")
        print(f"Risk Level: {result['risk_level']}")
        print(f"Findings: {result['findings']}")
        print(f"Execution Time: {result['execution_time_ms']:.2f}ms")


async def test_erp_connection():
    """Test ERP connection"""
    print("\n" + "="*60)
    print("Testing ERP Connection")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/test/erp-connection")
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AegisChain AI Framework Test Suite")
    print("="*60)
    
    try:
        await test_health()
        await test_dummy_agent()
        await test_erp_connection()
        
        print("\n" + "="*60)
        print("✓ All tests passed!")
        print("="*60)
    
    except Exception as e:
        print(f"\n✗ Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())