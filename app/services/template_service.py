import uuid
from datetime import UTC, datetime
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

import app.config
from app.exceptions.errors import ForbiddenError, SchemaNotFoundError, TemplateNotFoundError, ValidationServiceError
from app.logging_config import get_logger
from app.models.domain import Role, Template, User, Visibility
from app.models.schemas import ValidationErrorDetail
from app.storage.metadata_store import get_metadata_store, new_template_id
from app.storage.schema_store import SchemaStore, get_schema_store

logger = get_logger(__name__)

SYSTEM_OWNER_ID = "system"


def _now() -> datetime:
    return datetime.now(UTC)


def _user_context(user: User | None) -> dict[str, Any]:
    if user is None:
        return {"actor_id": "anonymous", "actor_email": "-"}
    return {"actor_id": user.id, "actor_email": user.email}


def can_view_template(user: User | None, template: Template | None) -> bool:
    if not app.config.AUTH_ENABLED or user is None:
        return True
    if template is None:
        return user.role == Role.ADMIN
    if user.role == Role.ADMIN:
        return True
    if template.owner_id == user.id:
        return True
    if template.visibility == Visibility.PUBLIC:
        return True
    if template.visibility == Visibility.TEAM and template.team_id and user.team_id == template.team_id:
        return True
    return False


def can_modify_template(user: User | None, template: Template) -> bool:
    if not app.config.AUTH_ENABLED or user is None:
        return True
    if user.role == Role.ADMIN:
        return True
    return template.owner_id == user.id


def can_upload(user: User | None) -> bool:
    if not app.config.AUTH_ENABLED or user is None:
        return True
    return user is not None


def check_schema_valid(schema: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)


def verify_schema_definition(schema: dict[str, Any]) -> tuple[bool, str | None]:
    try:
        check_schema_valid(schema)
        return True, None
    except SchemaError as exc:
        return False, str(exc.message)


class TemplateService:
    def __init__(
        self,
        schema_store: SchemaStore | None = None,
        metadata_store=None,
    ) -> None:
        self.schema_store = schema_store or get_schema_store()
        self.metadata_store = metadata_store or get_metadata_store()

    def load_schema(self, schema_name: str, user: User | None = None) -> dict[str, Any]:
        safe_name = schema_name.removesuffix(".json")
        logger.debug("Loading schema", extra={"schema_name": safe_name, **_user_context(user)})

        if app.config.AUTH_ENABLED:
            template = self.metadata_store.get_template(safe_name)
            if template is None:
                schema = self.schema_store.get(safe_name)
                if schema is None:
                    logger.warning("Schema not found in store", extra={"schema_name": safe_name})
                    raise SchemaNotFoundError(safe_name)
                if not can_view_template(user, None) and user and user.role != Role.ADMIN:
                    logger.warning(
                        "Access denied — schema has no metadata record",
                        extra={"schema_name": safe_name, **_user_context(user)},
                    )
                    raise SchemaNotFoundError(safe_name)
                return schema
            if not can_view_template(user, template):
                logger.warning(
                    "Access denied — insufficient visibility",
                    extra={
                        "schema_name": safe_name,
                        "visibility": template.visibility,
                        "owner_id": template.owner_id,
                        **_user_context(user),
                    },
                )
                raise ForbiddenError(f"You do not have access to schema '{safe_name}'")
        else:
            template = None

        schema = self.schema_store.get(safe_name)
        if schema is None:
            logger.warning("Schema file missing from store", extra={"schema_name": safe_name})
            raise SchemaNotFoundError(safe_name)

        logger.debug("Schema loaded successfully", extra={"schema_name": safe_name})
        return schema

    def validate_payload(
        self, schema_name: str, payload: dict[str, Any], user: User | None = None
    ) -> tuple[bool, list[ValidationErrorDetail]]:
        logger.debug(
            "Validating payload",
            extra={"schema_name": schema_name, **_user_context(user)},
        )
        try:
            schema = self.load_schema(schema_name, user)
            check_schema_valid(schema)
            validator = Draft202012Validator(schema, format_checker=FormatChecker())
            errors: list[ValidationErrorDetail] = []
            for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
                path = ".".join(str(p) for p in err.absolute_path) if err.absolute_path else "(root)"
                errors.append(
                    ValidationErrorDetail(path=path, message=err.message, validator=err.validator)
                )
        except (SchemaNotFoundError, ForbiddenError):
            raise
        except SchemaError:
            raise
        except Exception as exc:
            logger.error(
                "Unexpected error during payload validation",
                extra={"schema_name": schema_name, "error_type": type(exc).__name__, **_user_context(user)},
                exc_info=True,
            )
            raise ValidationServiceError(f"Validation failed unexpectedly: {exc}") from exc

        is_valid = len(errors) == 0
        result_label = "valid" if is_valid else f"{len(errors)} error(s)"
        logger.info(
            f"Payload validated against '{schema_name}' — {result_label}",
            extra={
                "schema_name": schema_name,
                "valid": is_valid,
                "error_count": len(errors),
                **_user_context(user),
            },
        )
        return is_valid, errors

    def list_accessible_templates(self, user: User | None = None) -> list[Template]:
        if not app.config.AUTH_ENABLED:
            names = self.schema_store.list_names()
            now = _now()
            return [
                Template(
                    template_id=str(uuid.uuid4()),
                    schema_name=name,
                    owner_id=SYSTEM_OWNER_ID,
                    visibility=Visibility.PUBLIC,
                    team_id=None,
                    created_at=now,
                    updated_at=now,
                )
                for name in names
            ]

        templates = self.metadata_store.list_templates()
        if user is None:
            return []
        visible = templates if user.role == Role.ADMIN else [t for t in templates if can_view_template(user, t)]
        return sorted(visible, key=lambda t: t.updated_at or t.created_at, reverse=True)

    def list_schema_names(self, user: User | None = None) -> list[str]:
        return [t.schema_name for t in self.list_accessible_templates(user)]

    def get_template_with_schema(
        self, schema_name: str, user: User | None = None
    ) -> tuple[Template | None, dict[str, Any]]:
        safe_name = schema_name.removesuffix(".json")
        template = self.metadata_store.get_template(safe_name) if app.config.AUTH_ENABLED else None
        if app.config.AUTH_ENABLED and template and not can_view_template(user, template):
            logger.warning(
                "Access denied on schema detail fetch",
                extra={"schema_name": safe_name, **_user_context(user)},
            )
            raise ForbiddenError(f"You do not have access to schema '{safe_name}'")
        schema = self.load_schema(safe_name, user)
        return template, schema

    def save_schema(
        self,
        schema_name: str,
        schema: dict[str, Any],
        user: User | None = None,
        visibility: Visibility = Visibility.PRIVATE,
        team_id: str | None = None,
    ) -> Template:
        if not can_upload(user):
            logger.warning("Schema upload denied — user not permitted", extra=_user_context(user))
            raise ForbiddenError("You do not have permission to upload schemas")

        safe_name = schema_name.removesuffix(".json")
        logger.debug("Saving schema", extra={"schema_name": safe_name, **_user_context(user)})

        try:
            check_schema_valid(schema)
            storage_key = self.schema_store.put(safe_name, schema)
        except SchemaError:
            raise
        except Exception as exc:
            logger.error(
                "Failed to persist schema to storage",
                extra={"schema_name": safe_name, "error_type": type(exc).__name__, **_user_context(user)},
                exc_info=True,
            )
            raise ValidationServiceError(f"Failed to save schema '{safe_name}': {exc}") from exc

        now = _now()

        if not app.config.AUTH_ENABLED:
            logger.info(
                "AUDIT schema_created",
                extra={"schema_name": safe_name, "storage_key": storage_key, **_user_context(user)},
            )
            return Template(
                template_id=new_template_id(),
                schema_name=safe_name,
                owner_id=SYSTEM_OWNER_ID,
                visibility=Visibility.PUBLIC,
                team_id=None,
                created_at=now,
                updated_at=now,
                s3_key=storage_key,
            )

        is_viewer = user is not None and user.role == Role.VIEWER
        if is_viewer:
            visibility = Visibility.PRIVATE
            team_id = None

        existing = self.metadata_store.get_template(safe_name)
        owner_id = user.id if user else SYSTEM_OWNER_ID
        if existing:
            if not can_modify_template(user, existing):
                logger.warning(
                    "Schema update denied — not owner or admin",
                    extra={"schema_name": safe_name, "owner_id": existing.owner_id, **_user_context(user)},
                )
                raise ForbiddenError(f"You do not have permission to update schema '{safe_name}'")
            existing.updated_at = now
            existing.s3_key = storage_key
            if user and user.role in (Role.ADMIN, Role.EDITOR):
                existing.visibility = visibility
                existing.team_id = team_id if visibility == Visibility.TEAM else None
            result = self.metadata_store.update_template(existing)
            logger.info(
                f"AUDIT schema '{safe_name}' updated by {user.email if user else 'system'} (visibility={existing.visibility.value})",
                extra={
                    "schema_name": safe_name,
                    "visibility": existing.visibility,
                    "storage_key": storage_key,
                    **_user_context(user),
                },
            )
            return result

        if visibility == Visibility.TEAM and not team_id and user:
            team_id = user.team_id

        template = Template(
            template_id=new_template_id(),
            schema_name=safe_name,
            owner_id=owner_id,
            visibility=visibility,
            team_id=team_id if visibility == Visibility.TEAM else None,
            created_at=now,
            updated_at=now,
            s3_key=storage_key,
        )
        result = self.metadata_store.create_template(template)
        logger.info(
            f"AUDIT schema '{safe_name}' created by {user.email if user else 'system'} (visibility={visibility.value})",
            extra={
                "schema_name": safe_name,
                "owner_id": owner_id,
                "visibility": visibility,
                "storage_key": storage_key,
                **_user_context(user),
            },
        )
        return result

    def update_schema(
        self,
        schema_name: str,
        schema: dict[str, Any] | None,
        user: User | None = None,
        visibility: Visibility | None = None,
        team_id: str | None = None,
    ) -> Template:
        safe_name = schema_name.removesuffix(".json")
        logger.debug("Updating schema", extra={"schema_name": safe_name, **_user_context(user)})

        if app.config.AUTH_ENABLED:
            template = self.metadata_store.get_template(safe_name)
            if template is None:
                raise TemplateNotFoundError(safe_name)
            if not can_modify_template(user, template):
                logger.warning(
                    "Schema update denied — not owner or admin",
                    extra={"schema_name": safe_name, "owner_id": template.owner_id, **_user_context(user)},
                )
                raise ForbiddenError(f"You do not have permission to update schema '{safe_name}'")
        else:
            template = None

        if schema is not None:
            try:
                check_schema_valid(schema)
                storage_key = self.schema_store.put(safe_name, schema)
            except SchemaError:
                raise
            except Exception as exc:
                logger.error(
                    "Failed to write updated schema to storage",
                    extra={"schema_name": safe_name, "error_type": type(exc).__name__, **_user_context(user)},
                    exc_info=True,
                )
                raise ValidationServiceError(f"Failed to update schema '{safe_name}': {exc}") from exc
        else:
            if self.schema_store.get(safe_name) is None:
                raise SchemaNotFoundError(safe_name)
            storage_key = template.s3_key if template else None

        if not app.config.AUTH_ENABLED:
            now = _now()
            logger.info(
                "AUDIT schema_updated",
                extra={"schema_name": safe_name, "storage_key": storage_key, **_user_context(user)},
            )
            return Template(
                template_id=new_template_id(),
                schema_name=safe_name,
                owner_id=SYSTEM_OWNER_ID,
                visibility=Visibility.PUBLIC,
                team_id=None,
                created_at=now,
                updated_at=now,
                s3_key=storage_key,
            )

        assert template is not None
        if schema is not None:
            template.s3_key = storage_key
        if visibility is not None and user and user.role in (Role.ADMIN, Role.EDITOR):
            template.visibility = visibility
            if visibility == Visibility.TEAM:
                if team_id is not None:
                    template.team_id = team_id
            else:
                template.team_id = None
        template.updated_at = _now()
        result = self.metadata_store.update_template(template)
        logger.info(
            f"AUDIT schema '{safe_name}' updated by {user.email if user else 'system'} (visibility={template.visibility.value})",
            extra={
                "schema_name": safe_name,
                "visibility": template.visibility,
                "storage_key": storage_key,
                **_user_context(user),
            },
        )
        return result

    def delete_schema(self, schema_name: str, user: User | None = None) -> None:
        safe_name = schema_name.removesuffix(".json")
        logger.debug("Deleting schema", extra={"schema_name": safe_name, **_user_context(user)})

        if app.config.AUTH_ENABLED:
            template = self.metadata_store.get_template(safe_name)
            if template is None:
                raise TemplateNotFoundError(safe_name)
            if not can_modify_template(user, template):
                logger.warning(
                    "Schema delete denied — not owner or admin",
                    extra={"schema_name": safe_name, "owner_id": template.owner_id, **_user_context(user)},
                )
                raise ForbiddenError(f"You do not have permission to delete schema '{safe_name}'")
            try:
                self.schema_store.delete(safe_name)
                self.metadata_store.delete_template(safe_name)
            except Exception as exc:
                logger.error(
                    "Failed to delete schema from storage",
                    extra={"schema_name": safe_name, "error_type": type(exc).__name__, **_user_context(user)},
                    exc_info=True,
                )
                raise
        else:
            if self.schema_store.get(safe_name) is None:
                raise SchemaNotFoundError(safe_name)
            try:
                self.schema_store.delete(safe_name)
            except Exception as exc:
                logger.error(
                    "Failed to delete schema file",
                    extra={"schema_name": safe_name, "error_type": type(exc).__name__},
                    exc_info=True,
                )
                raise

        logger.info(
            f"AUDIT schema '{safe_name}' deleted by {user.email if user else 'system'}",
            extra={"schema_name": safe_name, **_user_context(user)},
        )

    def seed_bundled_templates(self) -> None:
        if not app.config.AUTH_ENABLED:
            return
        now = _now()
        seeded = 0
        for name in self.schema_store.list_names():
            if self.metadata_store.get_template(name) is None:
                self.metadata_store.create_template(
                    Template(
                        template_id=new_template_id(),
                        schema_name=name,
                        owner_id=SYSTEM_OWNER_ID,
                        visibility=Visibility.PUBLIC,
                        team_id=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                seeded += 1
        if seeded:
            logger.info("Seeded bundled templates", extra={"count": seeded})


template_service = TemplateService()
