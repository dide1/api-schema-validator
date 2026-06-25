import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

IS_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

REPO_PATH = Path(os.getenv("REPO_PATH", ".")).resolve()

if IS_LAMBDA:
    BUNDLED_SCHEMAS_DIR = Path(os.getenv("BUNDLED_SCHEMAS_DIR", "/var/task/schemas"))
    WRITABLE_SCHEMAS_DIR = Path(os.getenv("WRITABLE_SCHEMAS_DIR", "/tmp/schemas"))
    SCHEMAS_DIR = BUNDLED_SCHEMAS_DIR
    SCHEMA_SEARCH_DIRS: list[Path] = [WRITABLE_SCHEMAS_DIR, BUNDLED_SCHEMAS_DIR]
else:
    SCHEMAS_DIR = Path(os.getenv("SCHEMAS_DIR", "./schemas")).resolve()
    BUNDLED_SCHEMAS_DIR = SCHEMAS_DIR
    WRITABLE_SCHEMAS_DIR = SCHEMAS_DIR
    SCHEMA_SEARCH_DIRS = [SCHEMAS_DIR]

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "aws" if IS_LAMBDA else "filesystem")
METADATA_DB_PATH = Path(os.getenv("METADATA_DB_PATH", str(SCHEMAS_DIR.parent / "metadata.db")))

S3_BUCKET = os.getenv("S3_BUCKET", "")
DYNAMODB_USERS_TABLE = os.getenv("DYNAMODB_USERS_TABLE", "")
DYNAMODB_TEMPLATES_TABLE = os.getenv("DYNAMODB_TEMPLATES_TABLE", "")
DYNAMODB_TEAMS_TABLE = os.getenv("DYNAMODB_TEAMS_TABLE", "")
DYNAMODB_INVITES_TABLE = os.getenv("DYNAMODB_INVITES_TABLE", "")
DYNAMODB_PAYLOADS_TABLE = os.getenv("DYNAMODB_PAYLOADS_TABLE", "")

AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
JWT_ALGORITHM = "HS256"

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")

OAUTH_REDIRECT_BASE = os.getenv("OAUTH_REDIRECT_BASE", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
}

DEFAULT_ORG_ID = os.getenv("DEFAULT_ORG_ID", "default")

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", FRONTEND_URL).split(",")
    if origin.strip()
]

