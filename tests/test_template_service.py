"""
Tests for TemplateService core logic:
  - Access control (can_view_template): ownership, public, and team-boundary isolation
  - Payload validation: happy path, root-level errors, nested $ref error paths
  - Schema persistence atomicity: invalid schema must not survive a failed save
"""
import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

import app.config
from app.models.domain import Role, Template, User, Visibility
from app.services.template_service import TemplateService, can_modify_template, can_view_template
from app.storage.schema_store import FilesystemSchemaStore
from jsonschema.exceptions import SchemaError


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(UTC)


def make_user(uid: str = "u1", role: Role = Role.EDITOR, team_id: str | None = None) -> User:
    return User(id=uid, email=f"{uid}@example.com", name=uid, role=role, team_id=team_id)


def make_template(
    owner: str = "u1",
    vis: Visibility = Visibility.PRIVATE,
    team_id: str | None = None,
) -> Template:
    return Template(
        template_id="t1",
        schema_name="test",
        owner_id=owner,
        visibility=vis,
        team_id=team_id,
        created_at=_now(),
        updated_at=_now(),
    )


SIMPLE_SCHEMA: dict = {
    "type": "object",
    "required": ["name"],
    "properties": {"name": {"type": "string"}},
}

# Schema with a $ref — the missing-field error occurs *inside* the subschema,
# so err.path (relative) is empty while err.absolute_path is ["address"].
NESTED_REF_SCHEMA: dict = {
    "type": "object",
    "$defs": {
        "Address": {
            "type": "object",
            "required": ["city"],
            "properties": {"city": {"type": "string"}},
        }
    },
    "required": ["address"],
    "properties": {"address": {"$ref": "#/$defs/Address"}},
}

# Structurally invalid per JSON Schema 2020-12 (bad type keyword value)
INVALID_SCHEMA: dict = {"type": "not-a-valid-type"}


@pytest.fixture
def service(tmp_path):
    """TemplateService backed by a temp filesystem store, auth disabled."""
    app.config.AUTH_ENABLED = False
    store = FilesystemSchemaStore(read_dirs=[tmp_path], write_dir=tmp_path)
    svc = TemplateService(schema_store=store, metadata_store=MagicMock())
    yield svc
    app.config.AUTH_ENABLED = False


def write_schema(tmp_path, name: str, schema: dict) -> None:
    (tmp_path / f"{name}.json").write_text(json.dumps(schema))


# ──────────────────────────────────────────────
# Access control
# ──────────────────────────────────────────────

class TestCanViewTemplate:
    def setup_method(self):
        app.config.AUTH_ENABLED = True

    def teardown_method(self):
        app.config.AUTH_ENABLED = False

    def test_owner_can_view_own_private_template(self):
        user = make_user("alice")
        tmpl = make_template(owner="alice", vis=Visibility.PRIVATE)
        assert can_view_template(user, tmpl) is True

    def test_non_owner_cannot_view_private_template(self):
        user = make_user("bob")
        tmpl = make_template(owner="alice", vis=Visibility.PRIVATE)
        assert can_view_template(user, tmpl) is False

    def test_public_template_is_visible_to_everyone(self):
        user = make_user("anyone")
        tmpl = make_template(owner="alice", vis=Visibility.PUBLIC)
        assert can_view_template(user, tmpl) is True

    def test_admin_can_view_any_template(self):
        admin = make_user("root", role=Role.ADMIN)
        tmpl = make_template(owner="alice", vis=Visibility.PRIVATE)
        assert can_view_template(admin, tmpl) is True

    def test_same_team_can_view_team_template(self):
        user = make_user("bob", team_id="alpha")
        tmpl = make_template(owner="alice", vis=Visibility.TEAM, team_id="alpha")
        assert can_view_template(user, tmpl) is True

    def test_different_team_cannot_view_team_template(self):
        """
        Cross-team isolation: a member of team-beta must NOT be able to read
        a TEAM-scoped schema belonging to team-alpha.

        This is the critical security invariant — team boundaries must be
        enforced by comparing user.team_id with template.team_id, not merely
        checking that the user has *some* team.
        """
        eve = make_user("eve", team_id="beta")
        tmpl = make_template(owner="alice", vis=Visibility.TEAM, team_id="alpha")
        assert can_view_template(eve, tmpl) is False, (
            "User on team-beta should not see a TEAM schema owned by team-alpha"
        )


# ──────────────────────────────────────────────
# Modify access control
# ──────────────────────────────────────────────

class TestCanModifyTemplate:
    def setup_method(self):
        app.config.AUTH_ENABLED = True

    def teardown_method(self):
        app.config.AUTH_ENABLED = False

    def test_owner_can_modify_own_template(self):
        user = make_user("alice")
        tmpl = make_template(owner="alice")
        assert can_modify_template(user, tmpl) is True

    def test_admin_can_modify_any_template(self):
        admin = make_user("root", role=Role.ADMIN)
        tmpl = make_template(owner="alice")
        assert can_modify_template(admin, tmpl) is True

    def test_editor_cannot_modify_others_template(self):
        """
        EDITOR role grants editing rights on the user's OWN schemas only.
        An editor must NOT be able to modify schemas owned by someone else.

        Allowing any editor to modify any template is a privilege escalation
        bug — the role check must be combined with ownership, not OR'd with it.
        """
        mallory = make_user("mallory", role=Role.EDITOR)
        tmpl = make_template(owner="alice", vis=Visibility.PUBLIC)
        assert can_modify_template(mallory, tmpl) is False, (
            "EDITOR role must not grant modify access to schemas owned by others"
        )

    def test_viewer_cannot_modify_any_template(self):
        viewer = make_user("viewer", role=Role.VIEWER)
        tmpl = make_template(owner="alice")
        assert can_modify_template(viewer, tmpl) is False


# ──────────────────────────────────────────────
# Payload validation
# ──────────────────────────────────────────────

class TestValidatePayload:
    def test_valid_payload_returns_no_errors(self, service, tmp_path):
        write_schema(tmp_path, "contact", SIMPLE_SCHEMA)
        valid, errors = service.validate_payload("contact", {"name": "Alice"})
        assert valid is True
        assert errors == []

    def test_missing_root_field_reports_root_path(self, service, tmp_path):
        write_schema(tmp_path, "contact", SIMPLE_SCHEMA)
        valid, errors = service.validate_payload("contact", {})
        assert valid is False
        assert len(errors) == 1
        assert errors[0].path == "(root)"

    def test_nested_ref_error_path_reflects_document_location(self, service, tmp_path):
        """
        When a schema uses $ref, jsonschema sets err.path relative to the
        resolved subschema (empty for a top-level required inside the ref) but
        err.absolute_path holds the full path from the document root.

        The ValidationErrorDetail.path must use err.absolute_path so callers
        can pinpoint where in the *document* the problem is.
        """
        write_schema(tmp_path, "order", NESTED_REF_SCHEMA)
        # 'address' is present but missing its required 'city' field
        valid, errors = service.validate_payload("order", {"address": {}})
        assert valid is False
        paths = [e.path for e in errors]
        assert any("address" in p for p in paths), (
            f"Expected an error path containing 'address' (the document location), "
            f"got {paths!r}. "
            f"Hint: the error-path condition should test err.absolute_path, not err.path."
        )


# ──────────────────────────────────────────────
# Schema persistence atomicity
# ──────────────────────────────────────────────

class TestSaveSchemaAtomicity:
    def test_valid_schema_is_persisted(self, service, tmp_path):
        service.save_schema("good", SIMPLE_SCHEMA)
        store = FilesystemSchemaStore(read_dirs=[tmp_path], write_dir=tmp_path)
        assert store.get("good") == SIMPLE_SCHEMA

    def test_invalid_schema_is_not_persisted(self, service, tmp_path):
        """
        save_schema must validate *before* writing.  If the schema is invalid,
        nothing must be written — the store must remain clean.

        Writing first and validating second leaks a corrupt file that
        subsequent load_schema calls will serve to clients.
        """
        with pytest.raises(SchemaError):
            service.save_schema("bad", INVALID_SCHEMA)

        store = FilesystemSchemaStore(read_dirs=[tmp_path], write_dir=tmp_path)
        assert store.get("bad") is None, (
            "Invalid schema was written to the store before validation ran. "
            "check_schema_valid() must be called BEFORE schema_store.put()."
        )
