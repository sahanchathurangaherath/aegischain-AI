import httpx
from typing import Dict, Any, List, Optional
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class ERPClient:
    """
    Client for communicating with Django ERP APIs
    """
    
    def __init__(self):
        self.base_url = settings.ERP_API_URL
        self.headers = {
            "Authorization": f"Token {settings.ERP_API_TOKEN}",
            "Content-Type": "application/json"
        }
        self.timeout = settings.AGENT_TIMEOUT
    
    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """
        Make GET request to ERP API
        
        Args:
            endpoint: API endpoint (e.g., "inventory/products")
            params: Query parameters
        
        Returns:
            JSON response data
        """
        url = f"{self.base_url}/{endpoint}/"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling {url}: {e}")
            raise
    
    def _extract_results(self, response: Any) -> Any:
        """
        Extract results from a paginated response.
        
        Handles both paginated responses (dict with 'results' key) 
        and non-paginated responses (list or dict).
        
        Args:
            response: API response (dict or list)
        
        Returns:
            List of results or original response if not paginated
        """
        if isinstance(response, dict) and "results" in response:
            return response.get("results", [])
        return response
    
    async def post(self, endpoint: str, data: Dict) -> Any:
        """
        Make POST request to ERP API
        
        Args:
            endpoint: API endpoint
            data: Request body
        
        Returns:
            JSON response data
        """
        url = f"{self.base_url}/{endpoint}/"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=data,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling {url}: {e}")
            raise
    
    # Convenience methods for common endpoints
    
    async def get_product(self, product_code: str) -> Optional[Dict]:
        """Get product by code"""
        response = await self.get("inventory/products", {"search": product_code})
        products = self._extract_results(response)
        
        # Find the product with matching code
        matching_product = None
        for product in products:
            if product.get("product_code") == product_code:
                matching_product = product
                break
        
        if not matching_product:
            return None
        
        # If we got a lightweight response (from list serializer), 
        # fetch the full product details using the ID
        if "reorder_point" not in matching_product and "id" in matching_product:
            try:
                full_product = await self.get(f"inventory/products/{matching_product['id']}")
                return full_product
            except Exception:
                # If detail fetch fails, return what we have
                pass
        
        return matching_product
    
    async def get_inventory_balance(
        self, 
        product_code: str, 
        warehouse_code: str
    ) -> Optional[Dict]:
        """Get inventory balance for product at warehouse"""
        response = await self.get(
            "inventory/balances",
            {
                "product__product_code": product_code,
                "warehouse__warehouse_code": warehouse_code
            }
        )
        balances = self._extract_results(response)
        return balances[0] if balances else None
    
    async def get_supplier(self, supplier_code: str) -> Optional[Dict]:
        """Get supplier by code"""
        response = await self.get("procurement/suppliers", {"search": supplier_code})
        suppliers = self._extract_results(response)
        for supplier in suppliers:
            if supplier.get("supplier_code") == supplier_code:
                return supplier
        return None
    
    async def get_delayed_shipments(self) -> List[Dict]:
        """Get all delayed shipments"""
        response = await self.get("procurement/shipments/delayed")
        return self._extract_results(response)
    
    async def get_low_stock_items(self) -> List[Dict]:
        """Get all low stock items"""
        response = await self.get("inventory/balances/low_stock")
        return self._extract_results(response)
    
    async def create_scan(self, scan_data: Dict) -> Dict:
        """Create a QR scan"""
        return await self.post("inventory/scans/scan", scan_data)
    
    async def health_check(self) -> bool:
        """Check if ERP API is accessible"""
        try:
            await self.get("inventory/products", {"page_size": 1})
            return True
        except Exception as e:
            logger.error(f"ERP health check failed: {e}")
            return False