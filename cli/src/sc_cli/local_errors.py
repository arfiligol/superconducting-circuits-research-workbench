"""CLI-local error contract and machine-readable error payloads."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CliErrorCategory = Literal["not_found", "validation", "forbidden", "conflict"]


class CliFieldError(BaseModel):
    field: str
    message: str


class CliErrorBody(BaseModel):
    code: str
    category: CliErrorCategory
    message: str
    status: int
    field_errors: list[CliFieldError] = Field(default_factory=list)


class CliContractError(Exception):
    def __init__(self, error: CliErrorBody):
        super().__init__(error.message)
        self.error = error


def build_contract_error(
    *,
    code: str,
    category: CliErrorCategory,
    message: str,
    status: int,
    field_errors: list[dict[str, str]] | None = None,
) -> CliContractError:
    return CliContractError(
        CliErrorBody(
            code=code,
            category=category,
            message=message,
            status=status,
            field_errors=[] if field_errors is None else field_errors,
        )
    )
