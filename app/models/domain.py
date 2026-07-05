from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class Visibility(StrEnum):
    PRIVATE = "private"
    TEAM = "team"
    PUBLIC = "public"


@dataclass
class User:
    id: str
    email: str
    name: str
    role: Role
    team_id: str | None = None
    oauth_provider: str | None = None
    oauth_sub: str | None = None
    created_at: datetime | None = None


@dataclass
class Team:
    id: str
    name: str


@dataclass
class Invite:
    token: str
    team_id: str
    invited_by: str
    created_at: datetime
    expires_at: datetime


@dataclass
class Template:
    template_id: str
    schema_name: str
    owner_id: str
    visibility: Visibility
    team_id: str | None
    created_at: datetime
    updated_at: datetime
    s3_key: str | None = None


@dataclass
class SavedPayload:
    payload_id: str
    payload_name: str
    owner_id: str
    visibility: Visibility
    team_id: str | None
    content: str  # JSON-serialised dict
    created_at: datetime
    updated_at: datetime
    schema_name: str | None = None
