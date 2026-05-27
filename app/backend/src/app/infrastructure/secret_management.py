from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

_DEVELOPMENT_ENVIRONMENTS = frozenset({"development", "dev", "local", "test"})
_UNSAFE_SESSION_SECRETS = frozenset(
    {
        "",
        "change-me",
        "change-me-session-secret",
        "default",
        "default-secret",
        "secret",
        "session-secret",
    }
)
_UNSAFE_BOOTSTRAP_PASSWORDS = frozenset(
    {
        "",
        "admin",
        "bootstrap",
        "change-me",
        "change-me-bootstrap-password",
        "default",
        "password",
    }
)
_MIN_SESSION_SECRET_LENGTH = 32
_MIN_BOOTSTRAP_PASSWORD_LENGTH = 16


class SecretSettings(Protocol):
    @property
    def environment(self) -> str: ...

    @property
    def session_secret(self) -> object: ...

    @property
    def bootstrap_admin_password(self) -> object: ...


@dataclass(frozen=True)
class SecretValidationViolation:
    variable_name: str
    reason: str


class SecretConfigurationError(RuntimeError):
    def __init__(self, violations: tuple[SecretValidationViolation, ...]) -> None:
        self.code = "unsafe_secret_configuration"
        self.violations = violations
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        details = ", ".join(
            f"{violation.variable_name}: {violation.reason}" for violation in self.violations
        )
        return f"Unsafe secret configuration detected. {details}"


def validate_secret_management_baseline(settings: SecretSettings) -> None:
    if _is_development_environment(settings.environment):
        return

    session_secret = _coerce_secret_value(settings.session_secret)
    bootstrap_password = _coerce_secret_value(settings.bootstrap_admin_password)

    violations: list[SecretValidationViolation] = []
    if _is_unsafe_secret(
        session_secret,
        unsafe_values=_UNSAFE_SESSION_SECRETS,
        min_length=_MIN_SESSION_SECRET_LENGTH,
    ):
        violations.append(
            SecretValidationViolation(
                variable_name="SC_SESSION_SECRET",
                reason=(
                    "must not use placeholder/default values and must be at least "
                    f"{_MIN_SESSION_SECRET_LENGTH} characters outside development/test."
                ),
            )
        )
    if _is_unsafe_secret(
        bootstrap_password,
        unsafe_values=_UNSAFE_BOOTSTRAP_PASSWORDS,
        min_length=_MIN_BOOTSTRAP_PASSWORD_LENGTH,
    ):
        violations.append(
            SecretValidationViolation(
                variable_name="SC_BOOTSTRAP_ADMIN_PASSWORD",
                reason=(
                    "must not use placeholder/default values and must be at least "
                    f"{_MIN_BOOTSTRAP_PASSWORD_LENGTH} characters outside development/test."
                ),
            )
        )

    if violations:
        raise SecretConfigurationError(tuple(violations))


def _is_development_environment(environment: str) -> bool:
    return environment.strip().casefold() in _DEVELOPMENT_ENVIRONMENTS


def _coerce_secret_value(secret: object) -> str:
    get_secret_value = getattr(secret, "get_secret_value", None)
    if callable(get_secret_value):
        value = get_secret_value()
        return value if isinstance(value, str) else str(value)
    return str(secret)


def _is_unsafe_secret(
    value: str,
    *,
    unsafe_values: frozenset[str],
    min_length: int,
) -> bool:
    normalized = value.strip()
    if len(normalized) < min_length:
        return True
    return normalized.casefold() in unsafe_values
