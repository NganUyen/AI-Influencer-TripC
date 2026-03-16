from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # Database
    DATABASE_URL: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # AI APIs
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str

    # Media Generation
    FAL_AI_API_KEY: str
    PLAYHT_API_KEY: str
    PLAYHT_USER_ID: str
    HEYGEN_API_KEY: Optional[str] = None

    # Cloudflare R2
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    R2_PUBLIC_URL: str

    # Proxies
    IPROYAL_USERNAME: str
    IPROYAL_PASSWORD: str
    IPROYAL_PROXY_HOST: str = "geo.iproyal.com"
    IPROYAL_PROXY_PORT: int = 12321

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str

    # Temporal
    TEMPORAL_ADDRESS: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "ai-influencer-tasks"
    WORKER_CONCURRENCY: int = 10

    # Social Media Platforms
    POSTIZ_API_URL: Optional[str] = "http://localhost:3100"
    POSTIZ_API_KEY: Optional[str] = None
    GROWCHIEF_API_URL: Optional[str] = "http://localhost:3200"
    GROWCHIEF_API_KEY: Optional[str] = None

    # OpenClaw Configuration
    OPENCLAW_API_URL: str = "http://localhost:8080"
    OPENCLAW_API_KEY: Optional[str] = None
    OPENCLAW_MISSION_CONTROL_URL: str = "http://localhost:8081"

    # Additional Settings
    DEFAULT_AI_MODEL: str = "gpt-4"
    LOG_LEVEL: str = "INFO"
    JWT_SECRET_KEY: str = "change-this-in-production"
    WEEKLY_WORKFLOW_ENABLED: bool = True
    APPROVAL_TIMEOUT_DAYS: int = 7
    ENGAGEMENT_DELAY_HOURS: int = 2
    STEALTH_ACCOUNT_COUNT: int = 5
    SYNDICATE_ENGAGEMENT_THRESHOLD: float = 2.0

    # Storage Settings
    R2_ENDPOINT_URL: str = ""
    R2_PUBLIC_DOMAIN: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
