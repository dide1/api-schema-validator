from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user, require_editor  # noqa: F401 — require_editor kept for verify endpoint
from app.exceptions.errors import TemplateNotFoundError
from app.models.domain import User
from app.models.schemas import (
    BatchValidateRequest,
    BatchValidateResponse,
    BatchValidateResultItem,
    SchemaDeleteResponse,
    SchemaDetailResponse,
    SchemaListResponse,
    SchemaUpdateRequest,
    SchemaUploadRequest,
    SchemaUploadResponse,
    SchemaVerifyRequest,
    SchemaVerifyResponse,
    SingleValidateRequest,
    SingleValidateResponse,
    TemplateSummary,
)
from app.services import validator as validator_service

router = APIRouter(prefix="/validate", tags=["validation"])
schemas_router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.post("/single", response_model=SingleValidateResponse)
def validate_single(
    body: SingleValidateRequest,
    user: User = Depends(get_current_user),
) -> SingleValidateResponse:
    valid, errors = validator_service.validate_payload(body.schema_name, body.payload, user)
    return SingleValidateResponse(valid=valid, errors=errors)


@router.post("/batch", response_model=BatchValidateResponse)
def validate_batch(
    body: BatchValidateRequest,
    user: User = Depends(get_current_user),
) -> BatchValidateResponse:
    results: list[BatchValidateResultItem] = []
    for index, item in enumerate(body.items):
        valid, errors = validator_service.validate_payload(item.schema_name, item.payload, user)
        results.append(BatchValidateResultItem(index=index, valid=valid, errors=errors))
    return BatchValidateResponse(results=results)


@schemas_router.get("", response_model=SchemaListResponse)
def list_schemas(user: User = Depends(get_current_user)) -> SchemaListResponse:
    from app.services.template_service import template_service
    from app.storage.metadata_store import get_metadata_store

    templates = template_service.list_accessible_templates(user)

    user_names: dict[str, str] = {u.id: u.name for u in get_metadata_store().list_users()}
    user_names["system"] = "System"

    summaries = [
        TemplateSummary(
            schema_name=t.schema_name,
            owner_id=t.owner_id,
            owner_name=user_names.get(t.owner_id, t.owner_id),
            visibility=t.visibility,
            team_id=t.team_id,
            updated_at=t.updated_at.isoformat() if t.updated_at else None,
        )
        for t in templates
    ]
    return SchemaListResponse(
        schemas=[t.schema_name for t in templates],
        templates=summaries,
    )


@schemas_router.post("/upload", response_model=SchemaUploadResponse)
def upload_schema(
    body: SchemaUploadRequest,
    user: User = Depends(get_current_user),
) -> SchemaUploadResponse:
    template = validator_service.save_schema(
        body.schema_name,
        body.schema_definition,
        user,
        body.visibility,
        body.team_id,
    )
    return SchemaUploadResponse(
        success=True,
        schema_name=body.schema_name,
        message=f"Schema '{body.schema_name}' saved successfully",
        visibility=template.visibility,
    )


@schemas_router.post("/verify", response_model=SchemaVerifyResponse)
def verify_schema(
    body: SchemaVerifyRequest,
    _user: User = Depends(require_editor),
) -> SchemaVerifyResponse:
    valid, message = validator_service.verify_schema(body.schema_definition)
    return SchemaVerifyResponse(valid=valid, message=message)


@schemas_router.get("/{schema_name}", response_model=SchemaDetailResponse)
def get_schema(
    schema_name: str,
    user: User = Depends(get_current_user),
) -> SchemaDetailResponse:
    template, schema = validator_service.get_schema_with_metadata(schema_name, user)
    return SchemaDetailResponse(
        schema_name=schema_name.removesuffix(".json"),
        schema=schema,
        owner_id=template.owner_id if template else None,
        visibility=template.visibility if template else None,
        team_id=template.team_id if template else None,
        updated_at=template.updated_at.isoformat() if template and template.updated_at else None,
    )


@schemas_router.put("/{schema_name}", response_model=SchemaUploadResponse)
def update_schema(
    schema_name: str,
    body: SchemaUpdateRequest,
    user: User = Depends(get_current_user),
) -> SchemaUploadResponse:
    template = validator_service.update_schema(
        schema_name,
        body.schema_definition,
        user,
        body.visibility,
        body.team_id,
    )
    return SchemaUploadResponse(
        success=True,
        schema_name=schema_name.removesuffix(".json"),
        message=f"Schema '{schema_name}' updated successfully",
        visibility=template.visibility,
    )


@schemas_router.delete("/{schema_name}", response_model=SchemaDeleteResponse)
def delete_schema(
    schema_name: str,
    user: User = Depends(get_current_user),
) -> SchemaDeleteResponse:
    safe_name = schema_name.removesuffix(".json")
    try:
        validator_service.delete_schema(safe_name, user)
    except TemplateNotFoundError as exc:
        from app.exceptions.errors import SchemaNotFoundError

        raise SchemaNotFoundError(exc.schema_name) from exc
    return SchemaDeleteResponse(
        success=True,
        schema_name=safe_name,
        message=f"Schema '{safe_name}' deleted successfully",
    )
