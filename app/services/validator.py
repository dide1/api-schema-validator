import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema import FormatChecker

from app.config import SCHEMAS_DIR
from app.exceptions.errors import SchemaNotFoundError, ValidationServiceError
from app.models.schemas import ValidationErrorDetail


def _schema_path(schema_name: str) -> Path:
    safe_name = schema_name.removesuffix(".json")
    return SCHEMAS_DIR / f"{safe_name}.json"


def load_schema(schema_name: str) -> dict[str, Any]:
    path = _schema_path(schema_name)
    if not path.is_file():
        raise SchemaNotFoundError(schema_name)

    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValidationServiceError(f"Invalid JSON in schema file '{schema_name}': {exc}") from exc
    except OSError as exc:
        raise ValidationServiceError(f"Failed to read schema '{schema_name}': {exc}") from exc


def validate_payload(schema_name: str, payload: dict[str, Any]) -> tuple[bool, list[ValidationErrorDetail]]:
    schema = load_schema(schema_name)

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise exc

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[ValidationErrorDetail] = []

    for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.absolute_path) if err.absolute_path else "(root)"
        errors.append(
            ValidationErrorDetail(
                path=path,
                message=err.message,
                validator=err.validator,
            )
        )

    return len(errors) == 0, errors


def list_schemas() -> list[str]:
    if not SCHEMAS_DIR.exists():
        try:
            SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValidationServiceError(f"Failed to create schemas directory: {exc}") from exc
        return []

    try:
        return sorted(p.stem for p in SCHEMAS_DIR.glob("*.json") if p.is_file())
    except OSError as exc:
        raise ValidationServiceError(f"Failed to list schemas: {exc}") from exc


def save_schema(schema_name: str, schema: dict[str, Any]) -> None:
    safe_name = schema_name.removesuffix(".json")

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError:
        raise

    if not SCHEMAS_DIR.exists():
        try:
            SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValidationServiceError(f"Failed to create schemas directory: {exc}") from exc

    path = _schema_path(safe_name)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
            f.write("\n")
    except OSError as exc:
        raise ValidationServiceError(f"Failed to write schema '{safe_name}': {exc}") from exc
