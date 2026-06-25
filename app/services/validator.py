from typing import Any

from jsonschema.exceptions import SchemaError

from app.models.schemas import ValidationErrorDetail
from app.models.domain import User
from app.services.template_service import template_service


def load_schema(schema_name: str, user: User | None = None) -> dict[str, Any]:
    return template_service.load_schema(schema_name, user)


def validate_payload(
    schema_name: str, payload: dict[str, Any], user: User | None = None
) -> tuple[bool, list[ValidationErrorDetail]]:
    return template_service.validate_payload(schema_name, payload, user)


def list_schemas(user: User | None = None) -> list[str]:
    return template_service.list_schema_names(user)


def save_schema(
    schema_name: str,
    schema: dict[str, Any],
    user: User | None = None,
    visibility=None,
    team_id: str | None = None,
):
    return template_service.save_schema(schema_name, schema, user, visibility, team_id)


def get_schema_with_metadata(schema_name: str, user: User | None = None):
    return template_service.get_template_with_schema(schema_name, user)


def update_schema(schema_name: str, schema, user=None, visibility=None, team_id=None):
    return template_service.update_schema(schema_name, schema, user, visibility, team_id)


def delete_schema(schema_name: str, user: User | None = None) -> None:
    return template_service.delete_schema(schema_name, user)


def verify_schema(schema: dict[str, Any]) -> tuple[bool, str | None]:
    from app.services.template_service import verify_schema_definition

    return verify_schema_definition(schema)


__all__ = [
    "SchemaError",
    "load_schema",
    "validate_payload",
    "list_schemas",
    "save_schema",
    "get_schema_with_metadata",
    "update_schema",
    "delete_schema",
    "verify_schema",
]
