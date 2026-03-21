from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.app.infrastructure.secret_management import validate_secret_management_baseline


class AppSettings(BaseSettings):
    app_name: str = "Superconducting Circuits API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_path: str = "data/database.db"
    audit_database_path: str = "data/audit-log.db"
    session_secret: SecretStr = SecretStr("change-me-session-secret")
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: SecretStr = SecretStr("change-me-bootstrap-password")
    app_base_url: str = "http://localhost:8000"
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str | None = None
    smtp_use_tls: bool = True
    redis_url: str | None = None
    rq_redis_url: str | None = None
    simulation_queue_name: str = "simulation"
    characterization_queue_name: str = "characterization"
    rq_job_timeout_seconds: int = 3600
    rq_failure_ttl_seconds: int = 86400
    rq_result_ttl_seconds: int = 3600
    rq_worker_stale_after_seconds: int = 300
    rq_reconcile_after_seconds: int = 300
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_reload: bool = False

    model_config = SettingsConfigDict(
        env_prefix="SC_",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    settings = AppSettings()
    validate_secret_management_baseline(settings)
    return settings
