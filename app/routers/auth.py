from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import RedirectResponse

from urllib.parse import quote

import app.config
from app.dependencies.auth import get_current_user, require_admin
from app.exceptions.errors import BadRequestError, ForbiddenError, UnauthorizedError
from app.models.domain import Role, User, Visibility
from app.logging_config import get_logger
from app.models.schemas import UserResponse, UserUpdateRequest

logger = get_logger(__name__)
from app.services import auth_service
from app.storage.metadata_store import MetadataStore, get_metadata_store


def _sync_admin_team(admin_id: str, new_team: str, old_team: str | None, store: MetadataStore) -> None:
    """Sync all TEAM-visibility templates owned by admin to new_team_id, and cascade rename to members/invites."""
    for t in store.list_templates():
        if t.owner_id == admin_id and t.visibility == Visibility.TEAM and t.team_id != new_team:
            t.team_id = new_team
            store.update_template(t)
    if old_team and old_team != new_team:
        for u in store.list_users():
            if u.team_id == old_team and u.id != admin_id:
                u.team_id = new_team
                store.update_user(u)
        for inv in store.list_invites_for_team(old_team):
            inv.team_id = new_team
            store.update_invite(inv)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
def auth_config() -> dict[str, bool]:
    return {"enabled": app.config.AUTH_ENABLED}


@router.get("/login/{provider}")
async def login(provider: str, request: Request):
    if not app.config.AUTH_ENABLED:
        return RedirectResponse(url=f"{app.config.FRONTEND_URL}/?auth=disabled")
    if provider not in ("google", "github"):
        raise UnauthorizedError(f"Unsupported provider: {provider}")
    client = auth_service.oauth.create_client(provider)
    if client is None:
        raise UnauthorizedError(f"OAuth provider '{provider}' is not configured")
    redirect_uri = auth_service.oauth_redirect_uri(provider, str(request.base_url))
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
async def callback(provider: str, request: Request):
    if not app.config.AUTH_ENABLED:
        return RedirectResponse(url=f"{app.config.FRONTEND_URL}/?auth=disabled")
    try:
        _user, token = await auth_service.handle_oauth_callback(provider, request)
    except Exception as exc:
        error = quote(str(exc))
        return RedirectResponse(url=f"{app.config.FRONTEND_URL}/auth/callback?error={error}")
    return RedirectResponse(
        url=f"{app.config.FRONTEND_URL}/auth/callback?token={quote(token, safe='')}"
    )


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value,
        team_id=user.team_id,
    )


@router.delete("/me")
def delete_me(user: User = Depends(get_current_user)) -> dict:
    store = get_metadata_store()
    store.delete_user(user.id)
    return {"success": True}


@router.put("/me", response_model=UserResponse)
def update_me(
    body: UserUpdateRequest,
    user: User = Depends(get_current_user),
) -> UserResponse:
    store = get_metadata_store()
    if body.team_id is not None:
        if user.role != Role.ADMIN:
            raise ForbiddenError("Team membership is managed by invite only. Ask your admin to send you an invite link.")
        new_team = body.team_id or None
        old_team = user.team_id
        user.team_id = new_team
        if new_team:
            _sync_admin_team(user.id, new_team, old_team, store)
        if not new_team:
            user.role = Role.ADMIN

    updated = store.update_user(user)
    return UserResponse(
        id=updated.id,
        email=updated.email,
        name=updated.name,
        role=updated.role.value,
        team_id=updated.team_id,
    )


@router.get("/users", response_model=list[UserResponse])
def list_users(admin: User = Depends(require_admin)) -> list[UserResponse]:
    store = get_metadata_store()
    all_users = store.list_users()
    if admin.team_id:
        visible = [u for u in all_users if u.team_id == admin.team_id or u.team_id is None]
    else:
        visible = all_users
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role.value,
            team_id=u.team_id,
        )
        for u in visible
    ]


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    body: UserUpdateRequest,
    admin: User = Depends(require_admin),
) -> UserResponse:
    from app.models.domain import Role

    store = get_metadata_store()
    target = store.get_user_by_id(user_id)
    if target is None:
        raise UnauthorizedError("User not found")

    if admin.team_id and target.team_id and target.team_id != admin.team_id:
        raise ForbiddenError("You can only manage users in your team")

    if user_id == admin.id and body.role is not None and body.role != "admin":
        raise ForbiddenError("You cannot change your own role")

    if body.role is not None:
        target.role = Role(body.role)
    if body.team_id is not None:
        new_team = body.team_id or None
        old_team = target.team_id
        if new_team and user_id != admin.id:
            all_users = store.list_users()
            team_exists = any(u.team_id == new_team and u.id != target.id for u in all_users)
            if not team_exists:
                raise BadRequestError(f"Team '{new_team}' does not exist.")
        target.team_id = new_team
        if user_id == admin.id and new_team:
            _sync_admin_team(admin.id, new_team, old_team, store)
        if not new_team:
            target.role = Role.ADMIN
    updated = store.update_user(target)
    return UserResponse(
        id=updated.id,
        email=updated.email,
        name=updated.name,
        role=updated.role.value,
        team_id=updated.team_id,
    )
