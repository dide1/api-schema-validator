import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from git.exc import GitCommandError
from jsonschema.exceptions import SchemaError

import app.config  # noqa: F401 — load environment before services
from app.exceptions.errors import SchemaNotFoundError, ValidationServiceError
from app.exceptions.handlers import (
    git_command_error_handler,
    request_validation_error_handler,
    schema_error_handler,
    schema_not_found_handler,
    unhandled_exception_handler,
    validation_service_error_handler,
)
from app.routers import git_ops, validate

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="API Schema Validator",
    description="Validate JSON payloads against user-defined schemas with Git integration",
    version="1.0.0",
)

app.add_exception_handler(SchemaNotFoundError, schema_not_found_handler)
app.add_exception_handler(ValidationServiceError, validation_service_error_handler)
app.add_exception_handler(SchemaError, schema_error_handler)
app.add_exception_handler(GitCommandError, git_command_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(validate.router)
app.include_router(validate.schemas_router)
app.include_router(git_ops.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
