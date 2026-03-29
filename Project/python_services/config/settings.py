from __future__ import annotations

from typing import Optional
from urllib.parse import quote, urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


PLACEHOLDER_SECRET_VALUES = {
    "change-this-admin-token",
    "change-this-connector-secret",
    "change-this-growchief-webhook-secret",
    "change-this-in-production",
    "change-this-internal-api-token",
    "change-this-postiz-webhook-secret",
    "change-this-telegram-auth-bridge-secret",
    "dev-connector-secret",
}


def _normalize_optional_string(value: object) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_optional_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        return int(normalized)
    return value


def _is_local_url(value: Optional[str]) -> bool:
    if not value:
        return True

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False

    host = (parsed.hostname or "").lower()
    return host in {"", "localhost", "127.0.0.1", "0.0.0.0", "backend", "frontend"}


class Settings(BaseSettings):
    """Application settings"""

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # Database
    DATABASE_URL: str
    CHATGPT_CONNECTOR_DATABASE_URL: Optional[str] = None
    REDIS_URL: Optional[str] = None

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_STORAGE_BUCKET: Optional[str] = None
    SUPABASE_STORAGE_PUBLIC_URL: Optional[str] = None
    CUSTOMER_TOKEN_ENCRYPTION_KEY: Optional[str] = None

    # AI APIs
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str

    # Media Generation
    FAL_AI_API_KEY: str
    GOOGLE_AI_API_KEY: Optional[str] = None
    HEYGEN_API_KEY: Optional[str] = None
    GOOGLE_TTS_API_KEY: Optional[str] = None

    # Object storage
    STORAGE_PROVIDER: str = "supabase"
    STORAGE_BUCKET_NAME: Optional[str] = None
    STORAGE_PUBLIC_URL: Optional[str] = None
    STORAGE_CACHE_CONTROL_SECONDS: int = 3600
    STORAGE_SIGNED_URL_TTL_SECONDS: int = 3600
    STORAGE_HTTP_TIMEOUT_SECONDS: int = 30
    STORAGE_UPSERT: bool = True

    # Legacy S3-compatible / Cloudflare R2 fallback
    R2_ACCOUNT_ID: Optional[str] = None
    R2_ACCESS_KEY_ID: Optional[str] = None
    R2_SECRET_ACCESS_KEY: Optional[str] = None
    R2_BUCKET_NAME: Optional[str] = None
    R2_PUBLIC_URL: Optional[str] = None

    # Proxies
    IPROYAL_USERNAME: str
    IPROYAL_PASSWORD: str
    IPROYAL_PROXY_HOST: str = "geo.iproyal.com"
    IPROYAL_PROXY_PORT: int = 12321
    PROXY_ENABLED: bool = False
    PROXY_SERVER: Optional[str] = None
    BROWSER_PROFILE_ROOT: str = "/app/browser_profiles"
    DEFAULT_PROXY_REGION_CODE: str = "US"
    DEFAULT_PROXY_LOCALE: str = "en-US"
    DEFAULT_PROXY_TIMEZONE: str = "America/New_York"

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    # TELEGRAM_CHAT_ID is optional — chat IDs are discovered automatically when
    # users send /start and are stored in the telegram_subscribers table.
    # Only set this if you need a legacy hardcoded fallback.
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None  # Set via setWebhook secret_token
    TELEGRAM_AUTH_BRIDGE_SECRET: Optional[str] = None

    # Temporal
    TEMPORAL_ADDRESS: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "ai-influencer-tasks"
    WORKER_CONCURRENCY: int = 10

    # Social Media Platforms
    POSTIZ_API_URL: Optional[str] = "http://localhost:3100"
    POSTIZ_API_KEY: Optional[str] = None
    POSTIZ_WEBHOOK_SECRET: Optional[str] = None
    GROWCHIEF_API_URL: Optional[str] = "http://localhost:3200"
    GROWCHIEF_API_KEY: Optional[str] = None
    GROWCHIEF_WEBHOOK_SECRET: Optional[str] = None
    CUSTOMER_POSTIZ_FALLBACK_ENABLED: bool = True

    # Customer OAuth provider configuration
    LINKEDIN_OAUTH_CLIENT_ID: Optional[str] = None
    LINKEDIN_OAUTH_CLIENT_SECRET: Optional[str] = None
    FACEBOOK_OAUTH_CLIENT_ID: Optional[str] = None
    FACEBOOK_OAUTH_CLIENT_SECRET: Optional[str] = None
    TWITTER_OAUTH_CLIENT_ID: Optional[str] = None
    TWITTER_OAUTH_CLIENT_SECRET: Optional[str] = None
    YOUTUBE_OAUTH_CLIENT_ID: Optional[str] = None
    YOUTUBE_OAUTH_CLIENT_SECRET: Optional[str] = None

    # OpenClaw Configuration
    OPENCLAW_API_URL: str = "http://localhost:8081"
    OPENCLAW_API_KEY: Optional[str] = None
    OPENCLAW_AGENT_ID: str = "main"
    OPENCLAW_MISSION_CONTROL_URL: str = "http://localhost:8081"
    FRONTEND_PUBLIC_URL: Optional[str] = None
    BACKEND_PUBLIC_URL: Optional[str] = None
    CHATGPT_CONNECTOR_PUBLIC_URL: str = "http://localhost:8010"
    CHATGPT_CONNECTOR_SESSION_SECRET: str = "dev-connector-secret"
    OPENAI_OAUTH_CLIENT_ID: Optional[str] = None
    OPENAI_OAUTH_CLIENT_SECRET: Optional[str] = None
    OPENAI_OAUTH_REDIRECT_URI: Optional[str] = None
    INTERNAL_API_TOKEN: Optional[str] = None
    APP_ADMIN_TOKEN: Optional[str] = None

    # Additional Settings
    DEFAULT_AI_MODEL: str = "gpt-4"
    LOG_LEVEL: str = "INFO"
    JWT_SECRET_KEY: str = "change-this-in-production"
    WEEKLY_WORKFLOW_ENABLED: bool = True
    APPROVAL_TIMEOUT_DAYS: int = 7
    ENGAGEMENT_DELAY_HOURS: int = 2
    STEALTH_ACCOUNT_COUNT: int = 5
    SYNDICATE_ENGAGEMENT_THRESHOLD: float = 2.0
    API_QUOTA_LOOKBACK_DAYS: int = 30
    API_QUOTA_ALERT_THRESHOLD: float = 80.0
    API_QUOTA_REFRESH_TTL_SECONDS: int = 60
    OPENAI_MONTHLY_TOKEN_LIMIT: Optional[int] = None
    ANTHROPIC_MONTHLY_TOKEN_LIMIT: Optional[int] = None
    GOOGLE_AI_MONTHLY_TOKEN_LIMIT: Optional[int] = None
    GOOGLE_TTS_MONTHLY_CHAR_LIMIT: Optional[int] = None
    FAL_AI_MONTHLY_REQUEST_LIMIT: Optional[int] = None
    HEYGEN_MONTHLY_JOB_LIMIT: Optional[int] = None

    # Legacy S3-compatible storage settings
    R2_ENDPOINT_URL: Optional[str] = None
    R2_PUBLIC_DOMAIN: Optional[str] = None

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_value(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return value

    @field_validator(
        "REDIS_URL",
        "FRONTEND_PUBLIC_URL",
        "BACKEND_PUBLIC_URL",
        "CHATGPT_CONNECTOR_PUBLIC_URL",
        "OPENAI_OAUTH_REDIRECT_URI",
        "TELEGRAM_WEBHOOK_SECRET",
        "TELEGRAM_AUTH_BRIDGE_SECRET",
        "POSTIZ_WEBHOOK_SECRET",
        "GROWCHIEF_WEBHOOK_SECRET",
        "CHATGPT_CONNECTOR_SESSION_SECRET",
        "JWT_SECRET_KEY",
        "INTERNAL_API_TOKEN",
        "APP_ADMIN_TOKEN",
        "CUSTOMER_TOKEN_ENCRYPTION_KEY",
        "SUPABASE_STORAGE_BUCKET",
        "SUPABASE_STORAGE_PUBLIC_URL",
        "STORAGE_BUCKET_NAME",
        "STORAGE_PUBLIC_URL",
        "LINKEDIN_OAUTH_CLIENT_ID",
        "LINKEDIN_OAUTH_CLIENT_SECRET",
        "FACEBOOK_OAUTH_CLIENT_ID",
        "FACEBOOK_OAUTH_CLIENT_SECRET",
        "TWITTER_OAUTH_CLIENT_ID",
        "TWITTER_OAUTH_CLIENT_SECRET",
        "YOUTUBE_OAUTH_CLIENT_ID",
        "YOUTUBE_OAUTH_CLIENT_SECRET",
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_NAME",
        "R2_PUBLIC_URL",
        "R2_ENDPOINT_URL",
        "R2_PUBLIC_DOMAIN",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value):
        return _normalize_optional_string(value)

    @field_validator("STORAGE_PROVIDER", mode="before")
    @classmethod
    def normalize_storage_provider(cls, value):
        normalized = _normalize_optional_string(value)
        if not normalized:
            return "supabase"

        lowered = normalized.lower()
        if lowered in {"supabase", "supabase_storage"}:
            return "supabase"
        if lowered in {"s3", "s3_compatible", "r2", "cloudflare_r2", "cloudflare-r2"}:
            return "s3"

        raise ValueError(
            "STORAGE_PROVIDER must be one of: supabase, s3, r2, s3_compatible"
        )

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def normalize_environment_value(cls, value):
        normalized = _normalize_optional_string(value)
        return normalized.lower() if normalized else "development"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def normalize_cors_origins(cls, value):
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            return ",".join(str(item).strip() for item in value if str(item).strip())
        return str(value)

    @field_validator("OPENAI_OAUTH_REDIRECT_URI", mode="before")
    @classmethod
    def normalize_oauth_redirect_uri(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @field_validator(
        "OPENAI_MONTHLY_TOKEN_LIMIT",
        "ANTHROPIC_MONTHLY_TOKEN_LIMIT",
        "GOOGLE_AI_MONTHLY_TOKEN_LIMIT",
        "GOOGLE_TTS_MONTHLY_CHAR_LIMIT",
        "FAL_AI_MONTHLY_REQUEST_LIMIT",
        "HEYGEN_MONTHLY_JOB_LIMIT",
        mode="before",
    )
    @classmethod
    def normalize_optional_ints(cls, value):
        return _normalize_optional_int(value)

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]

    @property
    def is_production_like(self) -> bool:
        return (
            self.ENVIRONMENT in {"production", "staging"}
            or not bool(self.DEBUG)
            or not _is_local_url(self.FRONTEND_PUBLIC_URL)
            or not _is_local_url(self.BACKEND_PUBLIC_URL)
            or not _is_local_url(self.CHATGPT_CONNECTOR_PUBLIC_URL)
        )

    @staticmethod
    def is_placeholder_secret(value: Optional[str]) -> bool:
        return value is not None and value in PLACEHOLDER_SECRET_VALUES

    @model_validator(mode="after")
    def apply_connector_defaults(self):
        if not self.CHATGPT_CONNECTOR_DATABASE_URL:
            self.CHATGPT_CONNECTOR_DATABASE_URL = self.DATABASE_URL
        if not self.OPENAI_OAUTH_REDIRECT_URI:
            connector_url = self.CHATGPT_CONNECTOR_PUBLIC_URL.rstrip("/")
            self.OPENAI_OAUTH_REDIRECT_URI = f"{connector_url}/oauth/callback"

        for origin in self.cors_origins_list:
            if origin == "*":
                raise ValueError(
                    "CORS_ORIGINS cannot include '*' when credentials are enabled"
                )
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"CORS_ORIGINS contains an invalid origin: {origin}")

        if self.is_production_like:
            required_secrets = {
                "JWT_SECRET_KEY": self.JWT_SECRET_KEY,
                "CHATGPT_CONNECTOR_SESSION_SECRET": self.CHATGPT_CONNECTOR_SESSION_SECRET,
                "INTERNAL_API_TOKEN": self.INTERNAL_API_TOKEN,
                "APP_ADMIN_TOKEN": self.APP_ADMIN_TOKEN,
                "POSTIZ_WEBHOOK_SECRET": self.POSTIZ_WEBHOOK_SECRET,
                "GROWCHIEF_WEBHOOK_SECRET": self.GROWCHIEF_WEBHOOK_SECRET,
                "CUSTOMER_TOKEN_ENCRYPTION_KEY": self.CUSTOMER_TOKEN_ENCRYPTION_KEY,
            }
            for key, value in required_secrets.items():
                if not value or self.is_placeholder_secret(value):
                    raise ValueError(
                        f"{key} must be set to a non-default value in production-like environments"
                    )
            required_provider_keys = {
                "POSTIZ_API_KEY": self.POSTIZ_API_KEY,
                "GROWCHIEF_API_KEY": self.GROWCHIEF_API_KEY,
            }
            for key, value in required_provider_keys.items():
                if not value:
                    raise ValueError(
                        f"{key} must be configured in production-like environments"
                    )

        if self.STORAGE_PROVIDER == "supabase":
            resolved_bucket = self.STORAGE_BUCKET_NAME or self.SUPABASE_STORAGE_BUCKET
        else:
            resolved_bucket = self.STORAGE_BUCKET_NAME or self.R2_BUCKET_NAME
        if not resolved_bucket:
            if self.STORAGE_PROVIDER == "supabase":
                raise ValueError(
                    "SUPABASE_STORAGE_BUCKET or STORAGE_BUCKET_NAME must be configured for STORAGE_PROVIDER=supabase"
                )
            raise ValueError(
                "R2_BUCKET_NAME or STORAGE_BUCKET_NAME must be configured for STORAGE_PROVIDER=s3"
            )
        self.STORAGE_BUCKET_NAME = resolved_bucket

        if (
            self.is_production_like
            and self.STORAGE_PROVIDER == "supabase"
            and resolved_bucket != "media"
        ):
            raise ValueError(
                "SUPABASE_STORAGE_BUCKET/STORAGE_BUCKET_NAME must be set to 'media' in production-like environments"
            )

        if self.STORAGE_PROVIDER == "supabase":
            public_base_url = (
                self.STORAGE_PUBLIC_URL or self.SUPABASE_STORAGE_PUBLIC_URL
            )
            if not public_base_url:
                public_base_url = (
                    f"{self.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/"
                    f"{quote(resolved_bucket, safe='')}"
                )
            self.STORAGE_PUBLIC_URL = public_base_url.rstrip("/")
        else:
            missing_legacy_config = [
                key
                for key, value in {
                    "R2_ENDPOINT_URL": self.R2_ENDPOINT_URL,
                    "R2_ACCESS_KEY_ID": self.R2_ACCESS_KEY_ID,
                    "R2_SECRET_ACCESS_KEY": self.R2_SECRET_ACCESS_KEY,
                }.items()
                if not value
            ]
            if missing_legacy_config:
                raise ValueError(
                    "Missing S3-compatible storage configuration: "
                    + ", ".join(missing_legacy_config)
                )

            public_base_url = (
                self.STORAGE_PUBLIC_URL or self.R2_PUBLIC_DOMAIN or self.R2_PUBLIC_URL
            )
            if not public_base_url:
                raise ValueError(
                    "STORAGE_PUBLIC_URL, R2_PUBLIC_DOMAIN, or R2_PUBLIC_URL must be configured for STORAGE_PROVIDER=s3"
                )
            self.STORAGE_PUBLIC_URL = public_base_url.rstrip("/")

        return self

    class Config:
        env_file = (".env", "../.env.local")
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()
