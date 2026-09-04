import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development").strip().lower()
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./rcaa.db")
    cors_origins: tuple[str, ...] = tuple(
        x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if x.strip()
    )
    razorpay_key_id: str = os.getenv("RAZORPAY_KEY_ID", "")
    razorpay_key_secret: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    razorpay_webhook_secret: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    settlement_window_days: int = int(os.getenv("SETTLEMENT_WINDOW_DAYS", "3"))
    redis_url: str = os.getenv("REDIS_URL", "")
    ai_provider: str = os.getenv("AI_PROVIDER", "mock").strip().lower()
    ai_api_key: str = os.getenv("AI_API_KEY", "")
    ai_base_url: str = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
    ai_model: str = os.getenv("AI_MODEL", "gpt-4o-mini")
    ai_timeout_seconds: float = float(os.getenv("AI_TIMEOUT_SECONDS", "20"))
    auth_secret: str = os.getenv("AUTH_SECRET", "")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    auth_bootstrap_token: str = os.getenv("AUTH_BOOTSTRAP_TOKEN", "")
    testing: bool = os.getenv("TESTING", "0") == "1"
    reconciliation_timestamp_tolerance_minutes: int = int(os.getenv("RECONCILIATION_TIMESTAMP_TOLERANCE_MINUTES", "30"))
    reconciliation_amount_tolerance: str = os.getenv("RECONCILIATION_AMOUNT_TOLERANCE", "0.00")
    reconciliation_timezone: str = os.getenv("RECONCILIATION_TIMEZONE", "UTC")
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "10"))
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    db_pool_timeout_seconds: int = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30"))
    db_pool_recycle_seconds: int = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))
    db_pool_pre_ping: bool = _env_bool("DB_POOL_PRE_PING", True)
    rcaa_version: str = os.getenv("RCAA_VERSION", "0.1.0")
    build_id: str = os.getenv("BUILD_ID", "local")
    git_commit_sha: str = os.getenv("GIT_COMMIT_SHA", "unknown")


settings = Settings()


def validate_startup_config() -> None:
    """Validate deployment-sensitive configuration without exposing secret values."""
    if settings.testing or settings.app_env not in {"production", "prod"}:
        return

    errors: list[str] = []
    if not settings.database_url or settings.database_url.startswith("sqlite"):
        errors.append("DATABASE_URL must point to PostgreSQL in production")
    if len(settings.auth_secret) < 32:
        errors.append("AUTH_SECRET must contain at least 32 characters in production")
    if not settings.cors_origins:
        errors.append("CORS_ORIGINS must contain at least one allowed origin")
    if settings.ai_provider in {"openai", "openai_compatible"} and not settings.ai_api_key:
        errors.append("AI_API_KEY is required when an external AI provider is enabled")
    if settings.ai_provider not in {"mock", "deterministic", "openai", "openai_compatible"}:
        errors.append("AI_PROVIDER is not supported")
    if settings.razorpay_key_id and not settings.razorpay_key_secret:
        errors.append("RAZORPAY_KEY_SECRET is required when RAZORPAY_KEY_ID is configured")
    if settings.razorpay_key_secret and not settings.razorpay_key_id:
        errors.append("RAZORPAY_KEY_ID is required when RAZORPAY_KEY_SECRET is configured")
    if settings.razorpay_key_id and not settings.razorpay_webhook_secret:
        errors.append("RAZORPAY_WEBHOOK_SECRET is required when Razorpay credentials are configured")
    if settings.db_pool_size < 1 or settings.db_max_overflow < 0 or settings.db_pool_timeout_seconds < 1 or settings.db_pool_recycle_seconds < 0:
        errors.append("Database pool settings are invalid")
    if errors:
        raise RuntimeError("Production configuration validation failed: " + "; ".join(errors))
