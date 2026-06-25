import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.exceptions.errors import BadRequestError, ForbiddenError, TemplateNotFoundError
from app.models.domain import SavedPayload, User, Visibility
from app.models.schemas import (
    PayloadDeleteResponse,
    PayloadDetail,
    PayloadListResponse,
    PayloadSaveRequest,
    PayloadSummary,
    PayloadUpdateRequest,
)
from app.storage.metadata_store import get_metadata_store, new_payload_id


def _now() -> datetime:
    return datetime.now(UTC)


router = APIRouter(prefix="/payloads", tags=["payloads"])

_VIS_RANK: dict[Visibility, int] = {
    Visibility.PRIVATE: 0,
    Visibility.TEAM: 1,
    Visibility.PUBLIC: 2,
}


def _check_vis_cap(requested: Visibility, schema_name: str) -> None:
    """Raise BadRequestError if requested visibility exceeds the schema's visibility."""
    store = get_metadata_store()
    template = store.get_template(schema_name)
    if template is None:
        return  # schema not found — let the payload save; schema validation happens elsewhere
    if _VIS_RANK[requested] > _VIS_RANK[template.visibility]:
        allowed = [v.value for v, r in _VIS_RANK.items() if r <= _VIS_RANK[template.visibility]]
        raise BadRequestError(
            f"Payload visibility '{requested}' exceeds schema visibility '{template.visibility}'. "
            f"Allowed: {', '.join(allowed)}."
        )


def _can_read(payload: SavedPayload, user: User) -> bool:
    if payload.owner_id == user.id:
        return True
    if payload.visibility == Visibility.PUBLIC:
        return True
    if payload.visibility == Visibility.TEAM and payload.team_id and user.team_id == payload.team_id:
        return True
    return False


def _to_detail(payload: SavedPayload) -> PayloadDetail:
    return PayloadDetail(
        payload_name=payload.payload_name,
        content=json.loads(payload.content),
        owner_id=payload.owner_id,
        visibility=payload.visibility,
        team_id=payload.team_id,
        schema_name=payload.schema_name,
        updated_at=payload.updated_at.isoformat(),
    )


def _summary(payload: SavedPayload, user_names: dict[str, str]) -> PayloadSummary:
    return PayloadSummary(
        payload_name=payload.payload_name,
        owner_id=payload.owner_id,
        owner_name=user_names.get(payload.owner_id, payload.owner_id),
        visibility=payload.visibility,
        team_id=payload.team_id,
        schema_name=payload.schema_name,
        updated_at=payload.updated_at.isoformat(),
    )


@router.get("", response_model=PayloadListResponse)
def list_payloads(user: User = Depends(get_current_user)) -> PayloadListResponse:
    store = get_metadata_store()
    user_names: dict[str, str] = {u.id: u.name for u in store.list_users()}
    accessible = [p for p in store.list_payloads() if _can_read(p, user)]
    return PayloadListResponse(payloads=[_summary(p, user_names) for p in accessible])


@router.post("", response_model=PayloadDetail)
def save_payload(body: PayloadSaveRequest, user: User = Depends(get_current_user)) -> PayloadDetail:
    if body.schema_name:
        _check_vis_cap(body.visibility, body.schema_name)

    store = get_metadata_store()
    existing = store.get_payload(body.payload_name)
    now = _now()

    if existing:
        if existing.owner_id != user.id:
            raise ForbiddenError("A payload with that name already exists and belongs to another user")
        existing.content = json.dumps(body.content)
        existing.visibility = body.visibility
        existing.team_id = body.team_id
        existing.schema_name = body.schema_name
        existing.updated_at = now
        store.update_payload(existing)
        return _to_detail(existing)

    saved = store.create_payload(SavedPayload(
        payload_id=new_payload_id(),
        payload_name=body.payload_name,
        owner_id=user.id,
        visibility=body.visibility,
        team_id=body.team_id,
        content=json.dumps(body.content),
        schema_name=body.schema_name,
        created_at=now,
        updated_at=now,
    ))
    return _to_detail(saved)


@router.get("/{payload_name}", response_model=PayloadDetail)
def get_payload(payload_name: str, user: User = Depends(get_current_user)) -> PayloadDetail:
    store = get_metadata_store()
    payload = store.get_payload(payload_name)
    if not payload or not _can_read(payload, user):
        raise TemplateNotFoundError(payload_name)
    return _to_detail(payload)


@router.put("/{payload_name}", response_model=PayloadDetail)
def update_payload(
    payload_name: str,
    body: PayloadUpdateRequest,
    user: User = Depends(get_current_user),
) -> PayloadDetail:
    store = get_metadata_store()
    payload = store.get_payload(payload_name)
    if not payload or not _can_read(payload, user):
        raise TemplateNotFoundError(payload_name)
    if payload.owner_id != user.id:
        raise ForbiddenError("You do not own this payload")

    # Determine effective schema for cap check
    effective_schema = body.schema_name if body.schema_name is not None else payload.schema_name
    new_vis = body.visibility if body.visibility is not None else payload.visibility
    if effective_schema:
        _check_vis_cap(new_vis, effective_schema)

    if body.content is not None:
        payload.content = json.dumps(body.content)
    if body.visibility is not None:
        payload.visibility = body.visibility
    if body.team_id is not None:
        payload.team_id = body.team_id
    if body.schema_name is not None:
        payload.schema_name = body.schema_name
    payload.updated_at = _now()
    store.update_payload(payload)
    return _to_detail(payload)


@router.delete("/{payload_name}", response_model=PayloadDeleteResponse)
def delete_payload(
    payload_name: str,
    user: User = Depends(get_current_user),
) -> PayloadDeleteResponse:
    store = get_metadata_store()
    payload = store.get_payload(payload_name)
    if not payload or not _can_read(payload, user):
        raise TemplateNotFoundError(payload_name)
    if payload.owner_id != user.id:
        raise ForbiddenError("You do not own this payload")
    store.delete_payload(payload_name)
    return PayloadDeleteResponse(success=True, payload_name=payload_name, message=f"Payload '{payload_name}' deleted")
