import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import BUNDLED_SCHEMAS_DIR, IS_LAMBDA, S3_BUCKET, SCHEMA_SEARCH_DIRS, WRITABLE_SCHEMAS_DIR
from app.exceptions.errors import ValidationServiceError
from app.logging_config import get_logger

logger = get_logger(__name__)


class SchemaStore(ABC):
    @abstractmethod
    def get(self, schema_name: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def put(self, schema_name: str, schema: dict[str, Any]) -> str:
        """Store schema and return storage key/path."""
        pass

    @abstractmethod
    def delete(self, schema_name: str) -> None:
        pass

    @abstractmethod
    def list_names(self) -> list[str]:
        pass


def _safe_name(schema_name: str) -> str:
    return schema_name.removesuffix(".json")


class FilesystemSchemaStore(SchemaStore):
    def __init__(self, read_dirs: list[Path] | None = None, write_dir: Path | None = None) -> None:
        self.read_dirs = read_dirs or SCHEMA_SEARCH_DIRS
        self.write_dir = write_dir or WRITABLE_SCHEMAS_DIR

    def _resolve_path(self, schema_name: str) -> Path | None:
        filename = f"{_safe_name(schema_name)}.json"
        for directory in self.read_dirs:
            path = directory / filename
            if path.is_file():
                return path
        return None

    def _writable_path(self, schema_name: str) -> Path:
        return self.write_dir / f"{_safe_name(schema_name)}.json"

    def _ensure_writable_dir(self) -> None:
        if self.write_dir.exists():
            return
        try:
            self.write_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValidationServiceError(f"Failed to create schemas directory: {exc}") from exc

    def get(self, schema_name: str) -> dict[str, Any] | None:
        path = self._resolve_path(schema_name)
        if path is None:
            return None
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise ValidationServiceError(f"Invalid JSON in schema file '{schema_name}': {exc}") from exc
        except OSError as exc:
            raise ValidationServiceError(f"Failed to read schema '{schema_name}': {exc}") from exc

    def put(self, schema_name: str, schema: dict[str, Any]) -> str:
        self._ensure_writable_dir()
        path = self._writable_path(schema_name)
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2)
                f.write("\n")
        except OSError as exc:
            raise ValidationServiceError(f"Failed to write schema '{schema_name}': {exc}") from exc
        return str(path)

    def delete(self, schema_name: str) -> None:
        path = self._writable_path(schema_name)
        if not path.is_file():
            bundled = BUNDLED_SCHEMAS_DIR / f"{_safe_name(schema_name)}.json"
            if bundled.is_file() and path != bundled:
                raise ValidationServiceError(f"Cannot delete bundled schema '{schema_name}'")
            return
        try:
            path.unlink()
        except OSError as exc:
            raise ValidationServiceError(f"Failed to delete schema '{schema_name}': {exc}") from exc

    def list_names(self) -> list[str]:
        names: set[str] = set()
        for directory in self.read_dirs:
            if not directory.exists():
                if directory is WRITABLE_SCHEMAS_DIR and IS_LAMBDA:
                    self._ensure_writable_dir()
                if not directory.exists():
                    continue
            try:
                names.update(p.stem for p in directory.glob("*.json") if p.is_file())
            except OSError as exc:
                raise ValidationServiceError(f"Failed to list schemas: {exc}") from exc
        return sorted(names)


class S3SchemaStore(SchemaStore):
    def __init__(self, bucket: str | None = None, bundled_dir: Path | None = None) -> None:
        self.bucket = bucket or S3_BUCKET
        self.bundled_dir = bundled_dir or BUNDLED_SCHEMAS_DIR
        self.client = boto3.client("s3")

    def _key(self, schema_name: str) -> str:
        return f"schemas/{_safe_name(schema_name)}.json"

    def get(self, schema_name: str) -> dict[str, Any] | None:
        key = self._key(schema_name)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            if error_code in ("NoSuchKey", "404"):
                bundled_path = self.bundled_dir / f"{_safe_name(schema_name)}.json"
                if bundled_path.is_file():
                    logger.debug(
                        "Schema not in S3, serving from bundled copy",
                        extra={"schema_name": schema_name, "s3_key": key},
                    )
                    with bundled_path.open(encoding="utf-8") as f:
                        return json.load(f)
                return None
            logger.error(
                "S3 get_object failed",
                extra={"schema_name": schema_name, "s3_key": key, "error_code": error_code, "error": str(exc)},
                exc_info=True,
            )
            raise ValidationServiceError(f"Failed to read schema from S3: {exc}") from exc

    def put(self, schema_name: str, schema: dict[str, Any]) -> str:
        key = self._key(schema_name)
        body = json.dumps(schema, indent=2) + "\n"
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body.encode("utf-8"),
                ContentType="application/json",
            )
        except ClientError as exc:
            logger.error(
                "S3 put_object failed",
                extra={"schema_name": schema_name, "s3_key": key, "error": str(exc)},
                exc_info=True,
            )
            raise ValidationServiceError(f"Failed to write schema to S3: {exc}") from exc
        logger.debug("Schema written to S3", extra={"schema_name": schema_name, "s3_key": key})
        return key

    def delete(self, schema_name: str) -> None:
        key = self._key(schema_name)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            logger.error(
                "S3 delete_object failed",
                extra={"schema_name": schema_name, "s3_key": key, "error": str(exc)},
                exc_info=True,
            )
            raise ValidationServiceError(f"Failed to delete schema from S3: {exc}") from exc
        logger.debug("Schema deleted from S3", extra={"schema_name": schema_name, "s3_key": key})

    def list_names(self) -> list[str]:
        names: set[str] = set()
        if self.bundled_dir.exists():
            names.update(p.stem for p in self.bundled_dir.glob("*.json") if p.is_file())
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix="schemas/"):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith(".json"):
                        names.add(Path(key).stem)
        except ClientError as exc:
            raise ValidationServiceError(f"Failed to list schemas from S3: {exc}") from exc
        return sorted(names)


def get_schema_store() -> SchemaStore:
    from app.config import STORAGE_BACKEND

    if STORAGE_BACKEND == "aws":
        logger.info("Schema store: S3", extra={"bucket": S3_BUCKET})
        return S3SchemaStore()
    logger.info("Schema store: filesystem", extra={"write_dir": str(WRITABLE_SCHEMAS_DIR)})
    return FilesystemSchemaStore()
