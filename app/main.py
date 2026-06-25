from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from jsonschema.exceptions import SchemaError
from starlette.middleware.sessions import SessionMiddleware

import app.config  # noqa: F401 — load environment before services
from app.config import AUTH_ENABLED, CORS_ORIGINS, IS_LAMBDA, JWT_SECRET
from app.exceptions.errors import (
    BadRequestError,
    ForbiddenError,
    SchemaNotFoundError,
    TemplateNotFoundError,
    UnauthorizedError,
    ValidationServiceError,
)
from app.exceptions.handlers import (
    bad_request_handler,
    forbidden_handler,
    request_validation_error_handler,
    schema_error_handler,
    schema_not_found_handler,
    template_not_found_handler,
    unauthorized_handler,
    unhandled_exception_handler,
    validation_service_error_handler,
)
from app.routers import auth, validate
from app.routers.invites import router as invites_router
from app.routers.payloads import router as payloads_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    if AUTH_ENABLED:
        from app.services.template_service import template_service
        template_service.seed_bundled_templates()
    yield


app = FastAPI(
    title="API Schema Validator",
    description="Validate JSON payloads against user-defined schemas with Git integration",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if AUTH_ENABLED:
    app.add_middleware(SessionMiddleware, secret_key=JWT_SECRET)

app.add_exception_handler(BadRequestError, bad_request_handler)
app.add_exception_handler(UnauthorizedError, unauthorized_handler)
app.add_exception_handler(ForbiddenError, forbidden_handler)
app.add_exception_handler(SchemaNotFoundError, schema_not_found_handler)
app.add_exception_handler(TemplateNotFoundError, template_not_found_handler)
app.add_exception_handler(ValidationServiceError, validation_service_error_handler)
app.add_exception_handler(SchemaError, schema_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(validate.router)
app.include_router(validate.schemas_router)
app.include_router(auth.router)
app.include_router(invites_router)
app.include_router(payloads_router)

if not IS_LAMBDA:
    from git.exc import GitCommandError

    from app.exceptions.handlers import git_command_error_handler
    from app.routers import git_ops

    app.add_exception_handler(GitCommandError, git_command_error_handler)
    app.include_router(git_ops.router)


@app.get("/health")
def health() -> dict[str, str]:
    body: dict[str, str] = {"status": "ok"}
    if IS_LAMBDA:
        body["runtime"] = "aws-lambda"
    return body
