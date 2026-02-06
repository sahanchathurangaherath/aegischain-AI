import requests

BASE_URL = "http://localhost:8000/api"


def create_low_stock_scan():
    """
    Create a QR scan that reduces stock below reorder point
    """
    print("Creating low stock scenario...")
    
    # First, check current stock
    try:
        response = requests.get(
            f"{BASE_URL}/inventory/balances/",
            params={
                "product__product_code": "RM-STEEL-001",
                "warehouse__warehouse_code": "WH-MAIN-01"
            },
            timeout=10
        )
    except requests.exceptions.RequestException as e:
        print(f"Error contacting ERP API: {e}")
        return
    
    try:
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch balances: {e}\nResponse text: {response.text}")
        return

    data = response.json()
    # Support paginated responses (DRF PageNumberPagination)
    if isinstance(data, dict) and "results" in data:
        items = data.get("results", [])
    else:
        items = data or []

    if not items:
        print("No inventory balances found for that product/warehouse.")
        return

    current = items[0]
    print(f"\nCurrent Stock: {current.get('quantity_on_hand')}")
    print(f"Reorder Point: 500")
    print(f"Safety Stock: 200")
        
    # Create an OUT scan to reduce stock
    scan_data = {
        "product_code": "RM-STEEL-001",
        "warehouse_code": "WH-MAIN-01",
        "scan_type": "OUT",
        "quantity": 400,  # Large outbound
        "scanned_by": "test_user",
        "reference_number": "TEST-LOW-STOCK",
        "notes": "Test scenario - reducing stock",
        "auto_process": True
    }

    try:
        response = requests.post(
            f"{BASE_URL}/inventory/scans/scan/",
            json=scan_data,
            timeout=10
        )
    except requests.exceptions.RequestException as e:
        print(f"Error creating scan: {e}")
        return

    try:
        response.raise_for_status()
    except Exception:
        print(f"\n❌ Failed to create scan: {response.status_code} - {response.text}")
        return

    result = response.json()
    # Support both direct and nested inventory_balance in response
    new_balance = result.get('inventory_balance') or result.get('inventory_balance_response') or result
    qty = None
    if isinstance(new_balance, dict):
        qty = new_balance.get('quantity_on_hand') or new_balance.get('quantity_available')

    print("\n✅ Low stock scenario created!")
    if qty is not None:
        print(f"New Stock Level: {qty}")
    else:
        print(f"Response: {result}")
    print("\nNow run the inventory agent to see alerts!")


if __name__ == "__main__":
    create_low_stock_scan()