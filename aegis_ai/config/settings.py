from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "AegisChain AI "
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # ERP Connection
    ERP_API_URL: str = "http://localhost:8000/api"
    ERP_API_TOKEN: str = "aegis_erp_token_12345"
    
    # AI Settings
    MAX_AGENTS: int = 10
    AGENT_TIMEOUT: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()