from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SingleValidateRequest(BaseModel):
    schema_name: str = Field(..., min_length=1, description="Name of the schema file (without .json)")
    payload: dict[str, Any] = Field(..., description="JSON payload to validate")


class ValidationErrorDetail(BaseModel):
    path: str
    message: str
    validator: str | None = None


class SingleValidateResponse(BaseModel):
    valid: bool
    errors: list[ValidationErrorDetail]


class BatchValidateItem(BaseModel):
    schema_name: str = Field(..., min_length=1)
    payload: dict[str, Any]


class BatchValidateRequest(BaseModel):
    items: list[BatchValidateItem] = Field(..., min_length=1)


class BatchValidateResultItem(BaseModel):
    index: int
    valid: bool
    errors: list[ValidationErrorDetail]


class BatchValidateResponse(BaseModel):
    results: list[BatchValidateResultItem]


class SchemaListResponse(BaseModel):
    schemas: list[str]


class SchemaUploadRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_name: str = Field(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
    schema_definition: dict[str, Any] = Field(..., alias="schema")


class SchemaUploadResponse(BaseModel):
    success: bool
    schema_name: str
    message: str


class GitCheckinRequest(BaseModel):
    message: str = Field(..., min_length=1)


class GitCheckinResponse(BaseModel):
    success: bool
    commit_hash: str


class GitCheckoutRequest(BaseModel):
    target: str = Field(..., min_length=1, description="Branch name or commit hash")


class GitCheckoutResponse(BaseModel):
    success: bool
    target: str


class GitStatusResponse(BaseModel):
    branch: str
    staged: list[str]
    unstaged: list[str]
    untracked: list[str]


class ErrorResponse(BaseModel):
    detail: str | list[dict[str, Any]]
