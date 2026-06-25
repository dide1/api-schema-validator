from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jsonschema.exceptions import SchemaError

from app.exceptions.errors import (
    BadRequestError,
    ForbiddenError,
    SchemaNotFoundError,
    TemplateNotFoundError,
    UnauthorizedError,
    ValidationServiceError,
)
from app.logging_config import get_logger

logger = get_logger(__name__)


def _path(request: Request) -> str:
    return f"{request.method} {request.url.path}"


async def schema_not_found_handler(request: Request, exc: SchemaNotFoundError) -> JSONResponse:
    logger.warning(
        "Schema not found",
        extra={"schema_name": exc.schema_name, "endpoint": _path(request)},
    )
    return JSONResponse(
        status_code=404,
        content={"detail": f"Schema '{exc.schema_name}' not found"},
    )


async def template_not_found_handler(request: Request, exc: TemplateNotFoundError) -> JSONResponse:
    logger.warning(
        "Template not found",
        extra={"schema_name": exc.schema_name, "endpoint": _path(request)},
    )
    return JSONResponse(
        status_code=404,
        content={"detail": f"Template '{exc.schema_name}' not found"},
    )


async def bad_request_handler(request: Request, exc: BadRequestError) -> JSONResponse:
    logger.warning(
        "Bad request",
        extra={"error_detail": exc.message, "endpoint": _path(request)},
    )
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message},
    )


async def unauthorized_handler(request: Request, exc: UnauthorizedError) -> JSONResponse:
    logger.warning(
        "Unauthorized access attempt",
        extra={"error_detail": exc.message, "endpoint": _path(request)},
    )
    return JSONResponse(
        status_code=401,
        content={"detail": exc.message},
    )


async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
    logger.warning(
        "Forbidden — insufficient permissions",
        extra={"error_detail": exc.message, "endpoint": _path(request)},
    )
    return JSONResponse(
        status_code=403,
        content={"detail": exc.message},
    )


async def validation_service_error_handler(
    request: Request, exc: ValidationServiceError
) -> JSONResponse:
    logger.error(
        "Validation service internal error",
        extra={"error_detail": exc.message, "endpoint": _path(request)},
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": exc.message},
    )


async def schema_error_handler(request: Request, exc: SchemaError) -> JSONResponse:
    logger.warning(
        "Invalid JSON schema definition",
        extra={"error_detail": exc.message, "endpoint": _path(request)},
    )
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc.message)},
    )


async def git_command_error_handler(request: Request, exc: Exception) -> JSONResponse:
    stderr = getattr(exc, "stderr", None) or str(exc)
    detail = stderr.strip() if stderr else "Git command failed"
    logger.error(
        "Git command failed",
        extra={"error_detail": detail, "endpoint": _path(request)},
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": detail},
    )


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", [])]
        errors.append(
            {
                "field": ".".join(loc),
                "message": err.get("msg", "Validation error"),
                "type": err.get("type", "value_error"),
            }
        )
    logger.warning(
        "Request body validation failed",
        extra={"validation_errors": errors, "endpoint": _path(request)},
    )
    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception — this is a bug, please investigate in CloudWatch logs",
        extra={
            "error_type": type(exc).__name__,
            "error_detail": str(exc),
            "endpoint": _path(request),
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
