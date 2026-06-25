import importlib
import shutil
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_SOURCE = PROJECT_ROOT / "schemas"


@pytest.fixture
def schemas_dir(tmp_path: Path) -> Path:
    dest = tmp_path / "schemas"
    shutil.copytree(SCHEMAS_SOURCE, dest)
    return dest


@pytest.fixture
def metadata_db(tmp_path: Path) -> Path:
    return tmp_path / "metadata.db"


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    readme = repo / "README.md"
    readme.write_text("# test repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


def _reload_modules() -> None:
    import app.config
    import app.dependencies.auth
    import app.main
    import app.routers.auth
    import app.routers.validate
    import app.services.auth_service
    import app.services.git_service
    import app.services.template_service
    import app.services.validator
    import app.storage.metadata_store
    import app.storage.schema_store

    app.storage.metadata_store._metadata_store = None
    importlib.reload(app.config)
    importlib.reload(app.storage.schema_store)
    importlib.reload(app.storage.metadata_store)
    importlib.reload(app.services.template_service)
    importlib.reload(app.services.validator)
    importlib.reload(app.services.auth_service)
    importlib.reload(app.services.git_service)
    importlib.reload(app.dependencies.auth)
    importlib.reload(app.routers.auth)
    importlib.reload(app.routers.validate)
    importlib.reload(app.main)


@pytest.fixture
def client(
    schemas_dir: Path,
    metadata_db: Path,
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.setenv("SCHEMAS_DIR", str(schemas_dir))
    monkeypatch.setenv("REPO_PATH", str(git_repo))
    monkeypatch.setenv("METADATA_DB_PATH", str(metadata_db))
    monkeypatch.setenv("STORAGE_BACKEND", "filesystem")
    monkeypatch.setenv("AUTH_ENABLED", "false")

    _reload_modules()
    import app.main

    with TestClient(app.main.app) as test_client:
        yield test_client


@pytest.fixture
def auth_client(
    schemas_dir: Path,
    metadata_db: Path,
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, dict[str, str]], None, None]:
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.setenv("SCHEMAS_DIR", str(schemas_dir))
    monkeypatch.setenv("REPO_PATH", str(git_repo))
    monkeypatch.setenv("METADATA_DB_PATH", str(metadata_db))
    monkeypatch.setenv("STORAGE_BACKEND", "filesystem")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")

    _reload_modules()

    from app.models.domain import Role, User
    from app.services.auth_service import create_access_token
    from app.storage.metadata_store import get_metadata_store, new_user_id
    import app.main
    import app.services.template_service as ts

    store = get_metadata_store()
    admin = User(
        id=new_user_id(),
        email="admin@example.com",
        name="Admin User",
        role=Role.ADMIN,
        oauth_provider="test",
        oauth_sub="admin-sub",
    )
    store.create_user(admin)
    editor = User(
        id=new_user_id(),
        email="editor@example.com",
        name="Editor User",
        role=Role.EDITOR,
        team_id="team-1",
        oauth_provider="test",
        oauth_sub="editor-sub",
    )
    store.create_user(editor)
    viewer = User(
        id=new_user_id(),
        email="viewer@example.com",
        name="Viewer User",
        role=Role.VIEWER,
        team_id="team-1",
        oauth_provider="test",
        oauth_sub="viewer-sub",
    )
    store.create_user(viewer)

    ts.template_service.seed_bundled_templates()

    tokens = {
        "admin": create_access_token(admin),
        "editor": create_access_token(editor),
        "viewer": create_access_token(viewer),
    }

    with TestClient(app.main.app) as test_client:
        yield test_client, tokens
