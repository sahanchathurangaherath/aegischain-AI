import sys
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # FastAPI Settings
    APP_NAME: str = "AegisChain AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # CORS Settings
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # ERP Connection
    ERP_API_URL: str = "http://localhost:8000/api"
    ERP_API_TOKEN: str = ""

    # AI Settings
    MAX_AGENTS: int = 10
    AGENT_TIMEOUT: int = 30
    ENABLE_LOGGING: bool = True

    # Outbox Worker & Escalation Routing
    DATABASE_URL: str = ""
    SYSTEM2_ENABLED: bool = False
    ESCALATION_COOLDOWN_HOURS: int = 6
    OUTBOX_POLL_INTERVAL_S: float = 1.0
    OUTBOX_BATCH_SIZE: int = 10
    OUTBOX_MAX_ATTEMPTS: int = 5

    # LLM Provider & Deliberation Harness
    LLM_PROVIDER: str = "replay"  # gemini | ollama | replay
    LLM_MODEL: str = "gemini-2.5-flash"
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    MAX_DELIBERATION_STEPS: int = 6
    MAX_DELIBERATION_WALL_S: float = 45.0
    MAX_DELIBERATION_TOKENS: int = 12000
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    @model_validator(mode="after")
    def validate_required_secrets(self) -> "Settings":
        if not self.DEBUG and not self.ERP_API_TOKEN and "pytest" not in sys.modules:
            raise ValueError("ERP_API_TOKEN must be set when DEBUG is False")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]


# Global settings instance
settings = Settings()
