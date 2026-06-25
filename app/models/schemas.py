from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.domain import Visibility


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


class TemplateSummary(BaseModel):
    schema_name: str
    owner_id: str
    owner_name: str
    visibility: Visibility
    team_id: str | None = None
    updated_at: str | None = None


class SchemaListResponse(BaseModel):
    schemas: list[str]
    templates: list[TemplateSummary] = Field(default_factory=list)


class SchemaUploadRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_name: str = Field(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
    schema_definition: dict[str, Any] = Field(..., alias="schema")
    visibility: Visibility = Visibility.PRIVATE
    team_id: str | None = None


class SchemaUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_definition: dict[str, Any] | None = Field(default=None, alias="schema")
    visibility: Visibility | None = None
    team_id: str | None = None


class SchemaVerifyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_definition: dict[str, Any] = Field(..., alias="schema")


class SchemaVerifyResponse(BaseModel):
    valid: bool
    message: str | None = None


class SchemaDetailResponse(BaseModel):
    schema_name: str
    schema_definition: dict[str, Any] = Field(..., alias="schema")
    owner_id: str | None = None
    visibility: Visibility | None = None
    team_id: str | None = None
    updated_at: str | None = None


class SchemaUploadResponse(BaseModel):
    success: bool
    schema_name: str
    message: str
    visibility: Visibility | None = None


class SchemaDeleteResponse(BaseModel):
    success: bool
    schema_name: str
    message: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    team_id: str | None = None


class UserUpdateRequest(BaseModel):
    role: str | None = None
    team_id: str | None = None


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


class InviteResponse(BaseModel):
    token: str
    team_id: str
    invited_by: str
    created_at: str
    expires_at: str
    link: str | None = None


class ErrorResponse(BaseModel):
    detail: str | list[dict[str, Any]]
