import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import (
    DYNAMODB_INVITES_TABLE,
    DYNAMODB_PAYLOADS_TABLE,
    DYNAMODB_TEMPLATES_TABLE,
    DYNAMODB_USERS_TABLE,
    METADATA_DB_PATH,
    STORAGE_BACKEND,
)
from app.logging_config import get_logger
from app.models.domain import Invite, Role, SavedPayload, Template, User, Visibility

logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _dt_to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _iso_to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class MetadataStore(ABC):
    @abstractmethod
    def init(self) -> None:
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> User | None:
        pass

    @abstractmethod
    def get_user_by_oauth(self, provider: str, oauth_sub: str) -> User | None:
        pass

    @abstractmethod
    def create_user(self, user: User) -> User:
        pass

    @abstractmethod
    def update_user(self, user: User) -> User:
        pass

    @abstractmethod
    def list_users(self) -> list[User]:
        pass

    @abstractmethod
    def get_template(self, schema_name: str) -> Template | None:
        pass

    @abstractmethod
    def list_templates(self) -> list[Template]:
        pass

    @abstractmethod
    def create_template(self, template: Template) -> Template:
        pass

    @abstractmethod
    def update_template(self, template: Template) -> Template:
        pass

    @abstractmethod
    def delete_template(self, schema_name: str) -> None:
        pass

    @abstractmethod
    def create_invite(self, invite: Invite) -> Invite:
        pass

    @abstractmethod
    def get_invite(self, token: str) -> Invite | None:
        pass

    @abstractmethod
    def update_invite(self, invite: Invite) -> Invite:
        pass

    @abstractmethod
    def list_invites_for_team(self, team_id: str) -> list[Invite]:
        pass

    @abstractmethod
    def delete_invite(self, token: str) -> None:
        pass

    @abstractmethod
    def delete_user(self, user_id: str) -> None:
        pass

    @abstractmethod
    def get_payload(self, payload_name: str) -> SavedPayload | None:
        pass

    @abstractmethod
    def list_payloads(self) -> list[SavedPayload]:
        pass

    @abstractmethod
    def create_payload(self, payload: SavedPayload) -> SavedPayload:
        pass

    @abstractmethod
    def update_payload(self, payload: SavedPayload) -> SavedPayload:
        pass

    @abstractmethod
    def delete_payload(self, payload_name: str) -> None:
        pass


class SQLiteMetadataStore(MetadataStore):
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or str(METADATA_DB_PATH)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        logger.info("Initialising SQLite metadata store", extra={"db_path": self.db_path})
        try:
            with self._connect() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        role TEXT NOT NULL,
                        team_id TEXT,
                        org_id TEXT,
                        oauth_provider TEXT,
                        oauth_sub TEXT,
                        created_at TEXT NOT NULL,
                        UNIQUE(oauth_provider, oauth_sub)
                    );
                    CREATE TABLE IF NOT EXISTS templates (
                        template_id TEXT PRIMARY KEY,
                        schema_name TEXT NOT NULL UNIQUE,
                        owner_id TEXT NOT NULL,
                        visibility TEXT NOT NULL,
                        team_id TEXT,
                        s3_key TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS invites (
                        token TEXT PRIMARY KEY,
                        team_id TEXT NOT NULL,
                        invited_by TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS payloads (
                        payload_id TEXT PRIMARY KEY,
                        payload_name TEXT NOT NULL UNIQUE,
                        owner_id TEXT NOT NULL,
                        visibility TEXT NOT NULL,
                        team_id TEXT,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )
                # Column additions are idempotent — ALTER TABLE fails if column exists, which is expected.
                try:
                    conn.execute("ALTER TABLE users ADD COLUMN org_id TEXT")
                    logger.debug("Applied migration: users.org_id")
                except Exception:
                    pass
                try:
                    conn.execute("ALTER TABLE payloads ADD COLUMN schema_name TEXT")
                    logger.debug("Applied migration: payloads.schema_name")
                except Exception:
                    pass
        except sqlite3.Error as exc:
            logger.error(
                "Failed to initialise SQLite database",
                extra={"db_path": self.db_path, "error": str(exc)},
                exc_info=True,
            )
            raise
        logger.info("SQLite metadata store ready", extra={"db_path": self.db_path})

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            role=Role(row["role"]),
            team_id=row["team_id"],
            oauth_provider=row["oauth_provider"],
            oauth_sub=row["oauth_sub"],
            created_at=_iso_to_dt(row["created_at"]),
        )

    def _row_to_template(self, row: sqlite3.Row) -> Template:
        return Template(
            template_id=row["template_id"],
            schema_name=row["schema_name"],
            owner_id=row["owner_id"],
            visibility=Visibility(row["visibility"]),
            team_id=row["team_id"],
            s3_key=row["s3_key"],
            created_at=_iso_to_dt(row["created_at"]),
            updated_at=_iso_to_dt(row["updated_at"]),
        )

    def get_user_by_id(self, user_id: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_user(row) if row else None

    def get_user_by_oauth(self, provider: str, oauth_sub: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE oauth_provider = ? AND oauth_sub = ?",
                (provider, oauth_sub),
            ).fetchone()
            return self._row_to_user(row) if row else None

    def create_user(self, user: User) -> User:
        created_at = user.created_at or _now()
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (id, email, name, role, team_id, oauth_provider, oauth_sub, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user.id,
                        user.email,
                        user.name,
                        user.role.value,
                        user.team_id,
                        user.oauth_provider,
                        user.oauth_sub,
                        _dt_to_iso(created_at),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            logger.error(
                "Failed to create user — constraint violation",
                extra={"user_id": user.id, "email": user.email, "error": str(exc)},
            )
            raise
        except sqlite3.Error as exc:
            logger.error(
                "SQLite error creating user",
                extra={"user_id": user.id, "error": str(exc)},
                exc_info=True,
            )
            raise
        logger.debug("User created in SQLite", extra={"user_id": user.id})
        user.created_at = created_at
        return user

    def update_user(self, user: User) -> User:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE users SET email = ?, name = ?, role = ?, team_id = ?
                    WHERE id = ?
                    """,
                    (user.email, user.name, user.role.value, user.team_id, user.id),
                )
        except sqlite3.Error as exc:
            logger.error(
                "SQLite error updating user",
                extra={"user_id": user.id, "error": str(exc)},
                exc_info=True,
            )
            raise
        logger.debug("User updated in SQLite", extra={"user_id": user.id})
        return user

    def list_users(self) -> list[User]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY email").fetchall()
            return [self._row_to_user(row) for row in rows]

    def get_template(self, schema_name: str) -> Template | None:
        safe_name = schema_name.removesuffix(".json")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM templates WHERE schema_name = ?", (safe_name,)
            ).fetchone()
            return self._row_to_template(row) if row else None

    def list_templates(self) -> list[Template]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM templates ORDER BY schema_name").fetchall()
            return [self._row_to_template(row) for row in rows]

    def create_template(self, template: Template) -> Template:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO templates
                (template_id, schema_name, owner_id, visibility, team_id, s3_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.template_id,
                    template.schema_name,
                    template.owner_id,
                    template.visibility.value,
                    template.team_id,
                    template.s3_key,
                    _dt_to_iso(template.created_at),
                    _dt_to_iso(template.updated_at),
                ),
            )
        return template

    def update_template(self, template: Template) -> Template:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE templates
                SET owner_id = ?, visibility = ?, team_id = ?, s3_key = ?, updated_at = ?
                WHERE schema_name = ?
                """,
                (
                    template.owner_id,
                    template.visibility.value,
                    template.team_id,
                    template.s3_key,
                    _dt_to_iso(template.updated_at),
                    template.schema_name,
                ),
            )
        return template

    def delete_template(self, schema_name: str) -> None:
        safe_name = schema_name.removesuffix(".json")
        with self._connect() as conn:
            conn.execute("DELETE FROM templates WHERE schema_name = ?", (safe_name,))

    def _row_to_invite(self, row: sqlite3.Row) -> Invite:
        return Invite(
            token=row["token"],
            team_id=row["team_id"],
            invited_by=row["invited_by"],
            created_at=_iso_to_dt(row["created_at"]),
            expires_at=_iso_to_dt(row["expires_at"]),
        )

    def create_invite(self, invite: Invite) -> Invite:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO invites (token, team_id, invited_by, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                (invite.token, invite.team_id, invite.invited_by, _dt_to_iso(invite.created_at), _dt_to_iso(invite.expires_at)),
            )
        return invite

    def get_invite(self, token: str) -> Invite | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM invites WHERE token = ?", (token,)).fetchone()
            return self._row_to_invite(row) if row else None

    def update_invite(self, invite: Invite) -> Invite:
        with self._connect() as conn:
            conn.execute(
                "UPDATE invites SET team_id = ?, invited_by = ?, expires_at = ? WHERE token = ?",
                (invite.team_id, invite.invited_by, _dt_to_iso(invite.expires_at), invite.token),
            )
        return invite

    def list_invites_for_team(self, team_id: str) -> list[Invite]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM invites WHERE team_id = ? ORDER BY created_at DESC",
                (team_id,),
            ).fetchall()
            return [self._row_to_invite(row) for row in rows]

    def delete_invite(self, token: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM invites WHERE token = ?", (token,))

    def delete_user(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def _row_to_payload(self, row: sqlite3.Row) -> SavedPayload:
        return SavedPayload(
            payload_id=row["payload_id"],
            payload_name=row["payload_name"],
            owner_id=row["owner_id"],
            visibility=Visibility(row["visibility"]),
            team_id=row["team_id"],
            content=row["content"],
            created_at=_iso_to_dt(row["created_at"]),
            updated_at=_iso_to_dt(row["updated_at"]),
            schema_name=row["schema_name"] if "schema_name" in row.keys() else None,
        )

    def get_payload(self, payload_name: str) -> SavedPayload | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM payloads WHERE payload_name = ?", (payload_name,)
            ).fetchone()
            return self._row_to_payload(row) if row else None

    def list_payloads(self) -> list[SavedPayload]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM payloads ORDER BY payload_name").fetchall()
            return [self._row_to_payload(row) for row in rows]

    def create_payload(self, payload: SavedPayload) -> SavedPayload:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO payloads
                (payload_id, payload_name, owner_id, visibility, team_id, content, schema_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.payload_id,
                    payload.payload_name,
                    payload.owner_id,
                    payload.visibility.value,
                    payload.team_id,
                    payload.content,
                    payload.schema_name,
                    _dt_to_iso(payload.created_at),
                    _dt_to_iso(payload.updated_at),
                ),
            )
        return payload

    def update_payload(self, payload: SavedPayload) -> SavedPayload:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE payloads
                SET visibility = ?, team_id = ?, content = ?, schema_name = ?, updated_at = ?
                WHERE payload_name = ?
                """,
                (
                    payload.visibility.value,
                    payload.team_id,
                    payload.content,
                    payload.schema_name,
                    _dt_to_iso(payload.updated_at),
                    payload.payload_name,
                ),
            )
        return payload

    def delete_payload(self, payload_name: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM payloads WHERE payload_name = ?", (payload_name,))


class DynamoDBMetadataStore(MetadataStore):
    def __init__(
        self,
        users_table: str | None = None,
        templates_table: str | None = None,
        invites_table: str | None = None,
        payloads_table: str | None = None,
    ) -> None:
        self.users_table = users_table or DYNAMODB_USERS_TABLE
        self.templates_table = templates_table or DYNAMODB_TEMPLATES_TABLE
        self.invites_table = invites_table or DYNAMODB_INVITES_TABLE
        self.payloads_table = payloads_table or DYNAMODB_PAYLOADS_TABLE
        self.client = boto3.resource("dynamodb")
        self.users = self.client.Table(self.users_table)
        self.templates = self.client.Table(self.templates_table)
        self.invites = self.client.Table(self.invites_table)
        self.payloads = self.client.Table(self.payloads_table)
        logger.info(
            "DynamoDB metadata store initialised",
            extra={
                "users_table": self.users_table,
                "templates_table": self.templates_table,
                "invites_table": self.invites_table,
                "payloads_table": self.payloads_table,
            },
        )

    def init(self) -> None:
        pass

    def _item_to_user(self, item: dict[str, Any]) -> User:
        return User(
            id=item["id"],
            email=item["email"],
            name=item["name"],
            role=Role(item["role"]),
            team_id=item.get("team_id") or None,
            oauth_provider=item.get("oauth_provider"),
            oauth_sub=item.get("oauth_sub"),
            created_at=_iso_to_dt(item["created_at"]),
        )

    def _user_to_item(self, user: User) -> dict[str, Any]:
        created_at = user.created_at or _now()
        item: dict[str, Any] = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            "created_at": _dt_to_iso(created_at),
        }
        if user.oauth_provider and user.oauth_sub:
            item["oauth_provider"] = user.oauth_provider
            item["oauth_sub"] = user.oauth_sub
        if user.team_id:
            item["team_id"] = user.team_id
        return item

    def _item_to_template(self, item: dict[str, Any]) -> Template:
        return Template(
            template_id=item["template_id"],
            schema_name=item["schema_name"],
            owner_id=item["owner_id"],
            visibility=Visibility(item["visibility"]),
            team_id=item.get("team_id"),
            s3_key=item.get("s3_key"),
            created_at=_iso_to_dt(item["created_at"]),
            updated_at=_iso_to_dt(item["updated_at"]),
        )

    def get_user_by_id(self, user_id: str) -> User | None:
        try:
            response = self.users.get_item(Key={"id": user_id})
            item = response.get("Item")
            return self._item_to_user(item) if item else None
        except ClientError as exc:
            logger.error(
                "DynamoDB get_user_by_id failed",
                extra={"user_id": user_id, "error": str(exc)},
                exc_info=True,
            )
            raise RuntimeError(f"DynamoDB get user failed: {exc}") from exc

    def get_user_by_oauth(self, provider: str, oauth_sub: str) -> User | None:
        try:
            response = self.users.query(
                IndexName="oauth-index",
                KeyConditionExpression="oauth_provider = :p AND oauth_sub = :s",
                ExpressionAttributeValues={":p": provider, ":s": oauth_sub},
            )
            items = response.get("Items", [])
            return self._item_to_user(items[0]) if items else None
        except ClientError as exc:
            # GSI may not exist yet — fall back to a full scan and log so the misconfiguration is visible.
            logger.warning(
                "DynamoDB oauth-index query failed, falling back to full scan — check GSI configuration",
                extra={"provider": provider, "error": str(exc)},
            )
            response = self.users.scan(
                FilterExpression="oauth_provider = :p AND oauth_sub = :s",
                ExpressionAttributeValues={":p": provider, ":s": oauth_sub},
            )
            items = response.get("Items", [])
            return self._item_to_user(items[0]) if items else None

    def create_user(self, user: User) -> User:
        created_at = user.created_at or _now()
        item = self._user_to_item(user)
        self.users.put_item(Item=item)
        user.created_at = created_at
        return user

    def update_user(self, user: User) -> User:
        self.users.put_item(Item=self._user_to_item(user))
        return user

    def list_users(self) -> list[User]:
        response = self.users.scan()
        return [self._item_to_user(item) for item in response.get("Items", [])]

    def get_template(self, schema_name: str) -> Template | None:
        safe_name = schema_name.removesuffix(".json")
        try:
            response = self.templates.query(
                IndexName="schema-name-index",
                KeyConditionExpression="schema_name = :n",
                ExpressionAttributeValues={":n": safe_name},
            )
            items = response.get("Items", [])
            if items:
                return self._item_to_template(items[0])
        except ClientError as exc:
            # GSI may not exist yet — fall back to scan and log so the misconfiguration is visible.
            logger.warning(
                "DynamoDB schema-name-index query failed, falling back to full scan — check GSI configuration",
                extra={"schema_name": safe_name, "error": str(exc)},
            )
        response = self.templates.scan(
            FilterExpression="schema_name = :n",
            ExpressionAttributeValues={":n": safe_name},
        )
        items = response.get("Items", [])
        return self._item_to_template(items[0]) if items else None

    def list_templates(self) -> list[Template]:
        response = self.templates.scan()
        return [self._item_to_template(item) for item in response.get("Items", [])]

    def create_template(self, template: Template) -> Template:
        item: dict[str, Any] = {
            "template_id": template.template_id,
            "schema_name": template.schema_name,
            "owner_id": template.owner_id,
            "visibility": template.visibility.value,
            "created_at": _dt_to_iso(template.created_at),
            "updated_at": _dt_to_iso(template.updated_at),
        }
        if template.team_id:
            item["team_id"] = template.team_id
        if template.s3_key:
            item["s3_key"] = template.s3_key
        self.templates.put_item(Item=item)
        return template

    def update_template(self, template: Template) -> Template:
        return self.create_template(template)

    def delete_template(self, schema_name: str) -> None:
        template = self.get_template(schema_name)
        if template:
            self.templates.delete_item(Key={"template_id": template.template_id})

    def _item_to_invite(self, item: dict[str, Any]) -> Invite:
        return Invite(
            token=item["token"],
            team_id=item["team_id"],
            invited_by=item["invited_by"],
            created_at=_iso_to_dt(item["created_at"]),
            expires_at=_iso_to_dt(item["expires_at"]),
        )

    def create_invite(self, invite: Invite) -> Invite:
        self.invites.put_item(Item={
            "token": invite.token,
            "team_id": invite.team_id,
            "invited_by": invite.invited_by,
            "created_at": _dt_to_iso(invite.created_at),
            "expires_at": _dt_to_iso(invite.expires_at),
        })
        return invite

    def get_invite(self, token: str) -> Invite | None:
        response = self.invites.get_item(Key={"token": token})
        item = response.get("Item")
        return self._item_to_invite(item) if item else None

    def update_invite(self, invite: Invite) -> Invite:
        self.invites.update_item(
            Key={"token": invite.token},
            UpdateExpression="SET team_id = :t, invited_by = :b, expires_at = :e",
            ExpressionAttributeValues={
                ":t": invite.team_id,
                ":b": invite.invited_by,
                ":e": _dt_to_iso(invite.expires_at),
            },
        )
        return invite

    def list_invites_for_team(self, team_id: str) -> list[Invite]:
        response = self.invites.scan(
            FilterExpression="team_id = :t",
            ExpressionAttributeValues={":t": team_id},
        )
        items = sorted(response.get("Items", []), key=lambda x: x["created_at"], reverse=True)
        return [self._item_to_invite(item) for item in items]

    def delete_invite(self, token: str) -> None:
        self.invites.delete_item(Key={"token": token})

    def delete_user(self, user_id: str) -> None:
        self.users.delete_item(Key={"id": user_id})

    def _item_to_payload(self, item: dict[str, Any]) -> SavedPayload:
        return SavedPayload(
            payload_id=item["payload_id"],
            payload_name=item["payload_name"],
            owner_id=item["owner_id"],
            visibility=Visibility(item["visibility"]),
            team_id=item.get("team_id"),
            content=item["content"],
            created_at=_iso_to_dt(item["created_at"]),
            updated_at=_iso_to_dt(item["updated_at"]),
            schema_name=item.get("schema_name"),
        )

    def get_payload(self, payload_name: str) -> SavedPayload | None:
        response = self.payloads.scan(
            FilterExpression="payload_name = :n",
            ExpressionAttributeValues={":n": payload_name},
        )
        items = response.get("Items", [])
        return self._item_to_payload(items[0]) if items else None

    def list_payloads(self) -> list[SavedPayload]:
        response = self.payloads.scan()
        return [self._item_to_payload(item) for item in response.get("Items", [])]

    def create_payload(self, payload: SavedPayload) -> SavedPayload:
        item: dict[str, Any] = {
            "payload_id": payload.payload_id,
            "payload_name": payload.payload_name,
            "owner_id": payload.owner_id,
            "visibility": payload.visibility.value,
            "content": payload.content,
            "created_at": _dt_to_iso(payload.created_at),
            "updated_at": _dt_to_iso(payload.updated_at),
        }
        if payload.team_id:
            item["team_id"] = payload.team_id
        if payload.schema_name:
            item["schema_name"] = payload.schema_name
        self.payloads.put_item(Item=item)
        return payload

    def update_payload(self, payload: SavedPayload) -> SavedPayload:
        existing = self.get_payload(payload.payload_name)
        if existing:
            payload.payload_id = existing.payload_id
        return self.create_payload(payload)

    def delete_payload(self, payload_name: str) -> None:
        existing = self.get_payload(payload_name)
        if existing:
            self.payloads.delete_item(Key={"payload_id": existing.payload_id})


_metadata_store: MetadataStore | None = None


def get_metadata_store() -> MetadataStore:
    global _metadata_store
    if _metadata_store is None:
        if STORAGE_BACKEND == "aws":
            _metadata_store = DynamoDBMetadataStore()
        else:
            store = SQLiteMetadataStore()
            store.init()
            _metadata_store = store
    return _metadata_store


def new_user_id() -> str:
    return str(uuid.uuid4())


def new_template_id() -> str:
    return str(uuid.uuid4())


def new_payload_id() -> str:
    return str(uuid.uuid4())
