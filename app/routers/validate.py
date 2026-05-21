from fastapi import APIRouter

from app.models.schemas import (
    BatchValidateRequest,
    BatchValidateResponse,
    BatchValidateResultItem,
    SchemaListResponse,
    SchemaUploadRequest,
    SchemaUploadResponse,
    SingleValidateRequest,
    SingleValidateResponse,
)
from app.services import validator as validator_service

router = APIRouter(prefix="/validate", tags=["validation"])
schemas_router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.post("/single", response_model=SingleValidateResponse)
def validate_single(body: SingleValidateRequest) -> SingleValidateResponse:
    valid, errors = validator_service.validate_payload(body.schema_name, body.payload)
    return SingleValidateResponse(valid=valid, errors=errors)


@router.post("/batch", response_model=BatchValidateResponse)
def validate_batch(body: BatchValidateRequest) -> BatchValidateResponse:
    results: list[BatchValidateResultItem] = []
    for index, item in enumerate(body.items):
        valid, errors = validator_service.validate_payload(item.schema_name, item.payload)
        results.append(BatchValidateResultItem(index=index, valid=valid, errors=errors))
    return BatchValidateResponse(results=results)


@schemas_router.get("", response_model=SchemaListResponse)
def list_schemas() -> SchemaListResponse:
    names = validator_service.list_schemas()
    return SchemaListResponse(schemas=names)


@schemas_router.post("/upload", response_model=SchemaUploadResponse)
def upload_schema(body: SchemaUploadRequest) -> SchemaUploadResponse:
    validator_service.save_schema(body.schema_name, body.schema_definition)
    return SchemaUploadResponse(
        success=True,
        schema_name=body.schema_name,
        message=f"Schema '{body.schema_name}' saved successfully",
    )
