from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    
    # FastAPI Settings
    APP_NAME: str = "AegisChain AI "
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # ERP Connection
    ERP_API_URL: str = "http://localhost:8000/api"
    ERP_API_TOKEN: str = "aegis_erp_token_12345"
    
    # AI Settings
    MAX_AGENTS: int = 10
    AGENT_TIMEOUT: int = 30
    ENABLE_LOGGING: bool = True
    
    # Vector Database
    VECTOR_DB_PATH: str = "./chroma_db"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()