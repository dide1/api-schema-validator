from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import app.config
from app.exceptions.errors import ForbiddenError, UnauthorizedError
from app.models.domain import Role, User
from app.services.auth_service import get_user_from_token

_bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    if not app.config.AUTH_ENABLED:
        return None
    if credentials is None:
        return None
    return get_user_from_token(credentials.credentials)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if not app.config.AUTH_ENABLED:
        return User(
            id="anonymous",
            email="anonymous@local",
            name="Anonymous",
            role=Role.ADMIN,
        )
    if credentials is None:
        raise UnauthorizedError("Authentication required")
    return get_user_from_token(credentials.credentials)


def require_role(*roles: Role):
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not app.config.AUTH_ENABLED:
            return user
        if user.role == Role.ADMIN:
            return user
        if user.role not in roles:
            raise ForbiddenError(f"Requires one of roles: {', '.join(r.value for r in roles)}")
        return user

    return dependency


def require_editor(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not app.config.AUTH_ENABLED:
        return user
    if user.role in (Role.ADMIN, Role.EDITOR):
        return user
    raise ForbiddenError("Editor role required")


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not app.config.AUTH_ENABLED:
        return user
    if user.role == Role.ADMIN:
        return user
    raise ForbiddenError("Admin role required")
