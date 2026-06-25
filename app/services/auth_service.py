from datetime import UTC, datetime, timedelta
from typing import Any

from authlib.integrations.starlette_client import OAuth
from jose import JWTError, jwt
from starlette.requests import Request

from app.config import (
    ADMIN_EMAILS,
    AUTH_ENABLED,
    FRONTEND_URL,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    JWT_SECRET,
    OAUTH_REDIRECT_BASE,
)
from app.exceptions.errors import UnauthorizedError
from app.logging_config import get_logger
from app.models.domain import Role, User
from app.storage.metadata_store import get_metadata_store, new_user_id

logger = get_logger(__name__)

oauth = OAuth()

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET:
    oauth.register(
        name="github",
        client_id=GITHUB_CLIENT_ID,
        client_secret=GITHUB_CLIENT_SECRET,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )


def create_access_token(user: User) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role.value,
        "team_id": user.team_id,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        logger.warning("Token decode failed — invalid or expired JWT", extra={"error": str(exc)})
        raise UnauthorizedError("Invalid or expired token") from exc


def get_user_from_token(token: str) -> User:
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        logger.warning("Token missing 'sub' claim")
        raise UnauthorizedError("Invalid token payload")
    store = get_metadata_store()
    user = store.get_user_by_id(user_id)
    if user is None:
        logger.warning("Token references unknown user", extra={"user_id": user_id})
        raise UnauthorizedError("User not found")
    logger.debug("Token validated", extra={"user_id": user.id, "role": user.role})
    return user


def _resolve_role(email: str, existing: User | None) -> Role:
    if existing:
        return existing.role
    return Role.ADMIN


async def handle_oauth_callback(provider: str, request: Request) -> tuple[User, str]:
    if provider not in ("google", "github"):
        logger.warning("OAuth callback with unsupported provider", extra={"provider": provider})
        raise UnauthorizedError(f"Unsupported provider: {provider}")

    client = oauth.create_client(provider)
    if client is None:
        logger.error(
            "OAuth provider not configured",
            extra={"provider": provider},
        )
        raise UnauthorizedError(f"OAuth provider '{provider}' is not configured")

    logger.debug("Exchanging OAuth code for token", extra={"provider": provider})
    try:
        token = await client.authorize_access_token(request)
    except Exception as exc:
        logger.error(
            "OAuth token exchange failed",
            extra={"provider": provider, "error_type": type(exc).__name__, "error": str(exc)},
            exc_info=True,
        )
        raise UnauthorizedError("OAuth authentication failed") from exc

    if provider == "google":
        userinfo = token.get("userinfo")
        if not userinfo:
            userinfo = await client.userinfo(token=token)
        email = userinfo["email"]
        name = userinfo.get("name", email)
        oauth_sub = userinfo["sub"]
    else:
        resp = await client.get("user", token=token)
        profile = resp.json()
        email = profile.get("email")
        if not email:
            emails_resp = await client.get("user/emails", token=token)
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary")), emails[0] if emails else None)
            email = primary["email"] if primary else f"{profile['id']}@users.noreply.github.com"
        name = profile.get("name") or profile.get("login", email)
        oauth_sub = str(profile["id"])

    store = get_metadata_store()
    existing = store.get_user_by_oauth(provider, oauth_sub)
    role = _resolve_role(email, existing)

    if existing:
        existing.email = email
        existing.name = name
        existing.oauth_provider = provider
        existing.oauth_sub = oauth_sub
        user = store.update_user(existing)
        logger.info(
            "AUDIT user_login",
            extra={"provider": provider, "user_id": user.id, "role": user.role, "is_new": False},
        )
    else:
        user = User(
            id=new_user_id(),
            email=email,
            name=name,
            role=role,
            oauth_provider=provider,
            oauth_sub=oauth_sub,
            created_at=datetime.now(UTC),
        )
        user = store.create_user(user)
        logger.info(
            "AUDIT user_registered",
            extra={"provider": provider, "user_id": user.id, "role": user.role, "is_new": True},
        )

    access_token = create_access_token(user)
    return user, access_token


def oauth_redirect_uri(provider: str, request_base_url: str) -> str:
    base = request_base_url.rstrip("/")
    return f"{base}/auth/callback/{provider}"


def is_auth_enabled() -> bool:
    return AUTH_ENABLED
