from dataclasses import dataclass, field
from typing import Literal

ApiErrorCategory = Literal[
    "auth_required",
    "permission_denied",
    "validation",
    "validation_error",
    "not_found",
    "forbidden",
    "conflict",
    "task_not_ready",
    "task_execution_failed",
    "persistence_error",
    "internal_error",
]


@dataclass(frozen=True)
class ServiceFieldError:
    field: str
    message: str


@dataclass
class ServiceError(Exception):
    status_code: int
    code: str
    category: ApiErrorCategory
    message: str
    field_errors: tuple[ServiceFieldError, ...] = field(default_factory=tuple)

    def __str__(self) -> str:
        return self.message


def service_error(
    status_code: int,
    *,
    code: str,
    category: ApiErrorCategory,
    message: str,
    field_errors: tuple[ServiceFieldError, ...] = (),
) -> ServiceError:
    return ServiceError(
        status_code=status_code,
        code=code,
        category=category,
        message=message,
        field_errors=field_errors,
    )
