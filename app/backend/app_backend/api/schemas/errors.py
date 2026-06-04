from typing import Literal

from pydantic import BaseModel, Field


class ApiFieldErrorResponse(BaseModel):
    field: str
    message: str


class ApiErrorBodyResponse(BaseModel):
    code: str
    category: Literal["not_found", "validation", "forbidden", "conflict"]
    message: str
    status: int
    field_errors: list[ApiFieldErrorResponse] = Field(default_factory=list)


class ApiErrorResponse(BaseModel):
    error: ApiErrorBodyResponse
