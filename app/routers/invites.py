import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends

import app.config
from app.dependencies.auth import get_current_user, require_admin
from app.exceptions.errors import BadRequestError, ForbiddenError, UnauthorizedError
from app.models.domain import Invite, User, Visibility
from app.models.schemas import InviteResponse
from app.storage.metadata_store import get_metadata_store

router = APIRouter(prefix="/invites", tags=["invites"])

INVITE_EXPIRY_DAYS = 7


def _invite_to_response(invite: Invite, include_link: bool = False) -> InviteResponse:
    return InviteResponse(
        token=invite.token,
        team_id=invite.team_id,
        invited_by=invite.invited_by,
        created_at=invite.created_at.isoformat(),
        expires_at=invite.expires_at.isoformat(),
        link=f"{app.config.FRONTEND_URL}/invites/{invite.token}" if include_link else None,
    )


def _is_expired(invite: Invite) -> bool:
    return invite.expires_at.replace(tzinfo=UTC) < datetime.now(UTC)


@router.post("", response_model=InviteResponse)
def create_invite(admin: User = Depends(require_admin)) -> InviteResponse:
    if not admin.team_id:
        raise BadRequestError("Generate a team code first before creating invite links.")
    store = get_metadata_store()
    # Sync any TEAM templates that have a stale team_id so invitees can see them immediately
    for t in store.list_templates():
        if t.owner_id == admin.id and t.visibility == Visibility.TEAM and t.team_id != admin.team_id:
            t.team_id = admin.team_id
            store.update_template(t)
    now = datetime.now(UTC)
    invite = Invite(
        token=str(uuid.uuid4()),
        team_id=admin.team_id,
        invited_by=admin.id,
        created_at=now,
        expires_at=now + timedelta(days=INVITE_EXPIRY_DAYS),
    )
    store.create_invite(invite)
    return _invite_to_response(invite, include_link=True)


@router.get("", response_model=list[InviteResponse])
def list_invites(admin: User = Depends(require_admin)) -> list[InviteResponse]:
    if not admin.team_id:
        return []
    invites = get_metadata_store().list_invites_for_team(admin.team_id)
    return [_invite_to_response(i, include_link=True) for i in invites if not _is_expired(i)]


@router.get("/{token}", response_model=InviteResponse)
def get_invite(token: str) -> InviteResponse:
    invite = get_metadata_store().get_invite(token)
    if invite is None:
        raise UnauthorizedError("Invite link not found.")
    if _is_expired(invite):
        raise BadRequestError("This invite link has expired.")
    return _invite_to_response(invite)


@router.post("/{token}/accept", response_model=InviteResponse)
def accept_invite(token: str, user: User = Depends(get_current_user)) -> InviteResponse:
    from app.models.domain import Role
    store = get_metadata_store()
    invite = store.get_invite(token)
    if invite is None:
        raise UnauthorizedError("Invite link not found.")
    if _is_expired(invite):
        raise BadRequestError("This invite link has expired.")
    if user.team_id != invite.team_id:
        user.team_id = invite.team_id
        user.role = Role.VIEWER
        store.update_user(user)
    return _invite_to_response(invite)


@router.delete("/{token}")
def revoke_invite(token: str, admin: User = Depends(require_admin)) -> dict:
    store = get_metadata_store()
    invite = store.get_invite(token)
    if invite is None:
        raise UnauthorizedError("Invite not found.")
    if admin.team_id and invite.team_id != admin.team_id:
        raise ForbiddenError("You can only revoke invites for your own team.")
    store.delete_invite(token)
    return {"success": True}
