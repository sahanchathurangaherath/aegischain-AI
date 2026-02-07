from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from config.settings import settings
from services.erp_client import ERPClient
from agents.dummy_agent import DummyAgent
from agents.inventory_agent import InventoryAgent
from agents.forecast_agent import ForecastAgent
from agents.supplier_risk_agent import SupplierRiskAgent

from schemas.agent_schemas import AgentContext, AgentResult
from orchestrator.orchestrator import get_orchestrator
from schemas.agent_schemas import OrchestrationRequest, OrchestrationResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events - startup and shutdown
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Test ERP connection
    erp_client = ERPClient()
    erp_healthy = await erp_client.health_check()
    
    if erp_healthy:
        logger.info("✓ ERP connection healthy")
    else:
        logger.warning(" ERP connection failed - some features may not work")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")


# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-agent AI orchestration for supply chain intelligence",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    
    # Check ERP connection
    erp_client = ERPClient()
    erp_healthy = await erp_client.health_check()
    
    return {
        "status": "healthy" if erp_healthy else "degraded",
        "service": "aegischain_ai",
        "erp_connection": "ok" if erp_healthy else "failed",
        "erp_endpoint": settings.ERP_API_URL
    }


@app.get("/api/info")
async def api_info():
    """API information"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "max_agents": settings.MAX_AGENTS,
        "agent_timeout": settings.AGENT_TIMEOUT,
        "erp_url": settings.ERP_API_URL
    }


# Test endpoints
@app.post("/api/test/dummy-agent", response_model=AgentResult)
async def test_dummy_agent(context: AgentContext):
    """
    Test the dummy agent
    
    Example request:
```json
    {
        "product_code": "TEST-001",
        "analysis_type": "test"
    }
```
    """
    try:
        agent = DummyAgent()
        result = await agent.execute(context.model_dump())
        return result
    except Exception as e:
        logger.error(f"Error testing dummy agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/test/erp-connection")
async def test_erp_connection():
    """
    Test ERP connection and fetch sample data
    """
    try:
        erp_client = ERPClient()
        
        # Try to fetch products
        products = await erp_client.get("inventory/products", {"page_size": 5})
        
        # Try to fetch low stock items
        low_stock = await erp_client.get_low_stock_items()
        
        return {
            "success": True,
            "message": "ERP connection working",
            "sample_products": len(products),
            "low_stock_items": len(low_stock)
        }
    
    except Exception as e:
        logger.error(f"ERP connection test failed: {e}")
        return {
            "success": False,
            "message": f"ERP connection failed: {str(e)}"
        }


@app.post("/api/agents/inventory", response_model=AgentResult)
async def run_inventory_agent(context: AgentContext):
    """
    Run the Inventory Agent
    
    Analyzes inventory levels, detects variance, and generates recommendations.
    

    """
    try:
        agent = InventoryAgent()
        result = await agent.execute(context.model_dump())
        return result
    except Exception as e:
        logger.error(f"Error running inventory agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/orchestrate", response_model=OrchestrationResponse)
async def orchestrate(request: OrchestrationRequest):
    """
    Main orchestration endpoint - The brain of AegisChain
    
    This endpoint:
    1. Analyzes the query to determine which agents to run
    2. Executes agents in parallel
    3. Combines results
    4. Makes a final decision
    5. Returns actionable recommendations
    
   
    """
    try:
        orchestrator = get_orchestrator()
        response = await orchestrator.orchestrate(request)
        return response
    except Exception as e:
        logger.error(f"Orchestration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    


@app.post("/api/agents/forecast", response_model=AgentResult)
async def run_forecast_agent(context: AgentContext):
    """
    Run the Forecast Agent
    
    Predicts future demand and identifies potential shortages.
    
   
    """
    try:
        agent = ForecastAgent()
        result = await agent.execute(context.model_dump())
        return result
    except Exception as e:
        logger.error(f"Error running forecast agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    


# Add endpoint
@app.post("/api/agents/supplier-risk", response_model=AgentResult)
async def run_supplier_risk_agent(context: AgentContext):
    """
    Run the Supplier Risk Agent
    
    Assesses supplier reliability and delivery performance.
    

    """
    try:
        agent = SupplierRiskAgent()
        result = await agent.execute(context.model_dump())
        return result
    except Exception as e:
        logger.error(f"Error running supplier risk agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orchestrate/info")
async def orchestrator_info():
    """Get information about the orchestrator"""
    orchestrator = get_orchestrator()
    
    return {
        "available_agents": list(orchestrator.agents.keys()),
        "agent_count": len(orchestrator.agents),
        "intent_keywords": orchestrator.classifier.intent_keywords,
        "status": "operational"
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

