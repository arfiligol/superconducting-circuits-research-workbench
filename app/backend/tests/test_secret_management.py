import pytest
from pydantic import SecretStr
from src.app.infrastructure.secret_management import (
    SecretConfigurationError,
    validate_secret_management_baseline,
)
from src.app.main import create_application
from src.app.settings import AppSettings


def test_secret_management_allows_development_placeholders() -> None:
    settings = AppSettings()

    validate_secret_management_baseline(settings)
    app = create_application(settings=settings)

    assert app.title == "Superconducting Circuits API"


def test_secret_management_rejects_default_session_secret_in_production() -> None:
    settings = AppSettings(
        environment="production",
        session_secret=SecretStr("change-me-session-secret"),
        bootstrap_admin_password=SecretStr("strong-bootstrap-password-2026"),
    )

    with pytest.raises(SecretConfigurationError) as exc_info:
        create_application(settings=settings)

    assert exc_info.value.code == "unsafe_secret_configuration"
    assert "SC_SESSION_SECRET" in str(exc_info.value)
    assert "change-me-session-secret" not in str(exc_info.value)


def test_secret_management_rejects_default_bootstrap_password_in_staging() -> None:
    settings = AppSettings(
        environment="staging",
        session_secret=SecretStr("safe-session-secret-value-for-staging-2026"),
        bootstrap_admin_password=SecretStr("change-me-bootstrap-password"),
    )

    with pytest.raises(SecretConfigurationError) as exc_info:
        validate_secret_management_baseline(settings)

    assert exc_info.value.code == "unsafe_secret_configuration"
    assert "SC_BOOTSTRAP_ADMIN_PASSWORD" in str(exc_info.value)
    assert "change-me-bootstrap-password" not in str(exc_info.value)


def test_secret_management_accepts_safe_non_dev_secrets() -> None:
    settings = AppSettings(
        environment="production",
        session_secret=SecretStr("safe-session-secret-value-for-production-2026"),
        bootstrap_admin_password=SecretStr("safe-bootstrap-password-2026"),
    )

    validate_secret_management_baseline(settings)
    app = create_application(settings=settings)

    assert app.title == "Superconducting Circuits API"
