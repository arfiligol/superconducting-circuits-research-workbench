from typing import Literal

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.app.api.schemas.errors import ApiErrorBodyResponse, ApiFieldErrorResponse
from src.app.services.service_errors import ServiceError

ApiErrorCategory = Literal["not_found", "validation", "forbidden", "conflict"]


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, _service_error_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _request_validation_handler)


async def _service_error_handler(_: Request, exc: Exception) -> JSONResponse:
    service_exc = exc if isinstance(exc, ServiceError) else _unexpected_service_error(exc)
    payload = normalize_service_error_payload(service_exc)
    return JSONResponse(
        status_code=service_exc.status_code,
        content={"error": payload.model_dump()},
    )


async def _http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    http_exc = (
        exc if isinstance(exc, HTTPException) else HTTPException(status_code=500, detail=str(exc))
    )
    payload = normalize_http_exception_payload(http_exc)
    return JSONResponse(status_code=http_exc.status_code, content={"error": payload.model_dump()})


async def _request_validation_handler(_: Request, exc: Exception) -> JSONResponse:
    validation_exc = exc if isinstance(exc, RequestValidationError) else RequestValidationError([])
    field_errors = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
        }
        for error in validation_exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": ApiErrorBodyResponse(
                code="request_validation_failed",
                category="validation",
                message="Request validation failed.",
                status=status.HTTP_422_UNPROCESSABLE_CONTENT,
                field_errors=[
                    ApiFieldErrorResponse(
                        field=field_error["field"],
                        message=field_error["message"],
                    )
                    for field_error in field_errors
                ],
            ).model_dump()
        },
    )


def normalize_service_error_payload(exc: ServiceError) -> ApiErrorBodyResponse:
    return ApiErrorBodyResponse(
        code=exc.code,
        category=exc.category,
        message=exc.message,
        status=exc.status_code,
        field_errors=[
            ApiFieldErrorResponse(field=field_error.field, message=field_error.message)
            for field_error in exc.field_errors
        ],
    )


def normalize_http_exception_payload(exc: HTTPException) -> ApiErrorBodyResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        raw_payload = dict(detail)
        return ApiErrorBodyResponse(
            code=str(raw_payload.get("code", _default_error_code(exc.status_code))),
            category=_coerce_error_category(raw_payload.get("category"), exc.status_code),
            message=str(raw_payload.get("message", "Request failed.")),
            status=exc.status_code,
            field_errors=_coerce_field_errors(raw_payload.get("field_errors")),
        )

    return ApiErrorBodyResponse(
        code=_default_error_code(exc.status_code),
        category=_default_error_category(exc.status_code),
        message=str(detail),
        status=exc.status_code,
        field_errors=[],
    )


def _default_error_code(status_code: int) -> str:
    if status_code == status.HTTP_404_NOT_FOUND:
        return "resource_not_found"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "forbidden"
    if status_code == status.HTTP_409_CONFLICT:
        return "conflict"
    if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
        return "validation_error"
    return "request_failed"


def _default_error_category(status_code: int) -> ApiErrorCategory:
    if status_code == status.HTTP_404_NOT_FOUND:
        return "not_found"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "forbidden"
    if status_code == status.HTTP_409_CONFLICT:
        return "conflict"
    return "validation"


def _coerce_error_category(
    raw_category: object,
    status_code: int,
) -> ApiErrorCategory:
    if raw_category == "not_found":
        return "not_found"
    if raw_category == "validation":
        return "validation"
    if raw_category == "forbidden":
        return "forbidden"
    if raw_category == "conflict":
        return "conflict"
    return _default_error_category(status_code)


def _coerce_field_errors(raw_field_errors: object) -> list[ApiFieldErrorResponse]:
    if not isinstance(raw_field_errors, list):
        return []

    field_errors: list[ApiFieldErrorResponse] = []
    for raw_field_error in raw_field_errors:
        if not isinstance(raw_field_error, dict):
            continue
        field = raw_field_error.get("field")
        message = raw_field_error.get("message")
        if isinstance(field, str) and isinstance(message, str):
            field_errors.append(ApiFieldErrorResponse(field=field, message=message))
    return field_errors


def _unexpected_service_error(exc: Exception) -> ServiceError:
    return ServiceError(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="request_failed",
        category="validation",
        message=str(exc),
    )
