import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from git.exc import GitCommandError
from jsonschema.exceptions import SchemaError

from app.exceptions.errors import SchemaNotFoundError, ValidationServiceError

logger = logging.getLogger(__name__)


async def schema_not_found_handler(_request: Request, exc: SchemaNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": f"Schema '{exc.schema_name}' not found"},
    )


async def validation_service_error_handler(
    _request: Request, exc: ValidationServiceError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": exc.message},
    )


async def schema_error_handler(_request: Request, exc: SchemaError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc.message)},
    )


async def git_command_error_handler(_request: Request, exc: GitCommandError) -> JSONResponse:
    stderr = exc.stderr or str(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": stderr.strip() if stderr else "Git command failed"},
    )


async def request_validation_error_handler(
    _request: Request, exc: RequestValidationError
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
    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )


async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
