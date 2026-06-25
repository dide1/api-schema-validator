VALID_PRODUCT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["sku"],
    "properties": {"sku": {"type": "string"}},
}


def _auth(headers: dict[str, str], token: str) -> dict[str, str]:
    return {**headers, "Authorization": f"Bearer {token}"}


def test_viewer_cannot_upload(auth_client) -> None:
    client, tokens = auth_client
    response = client.post(
        "/schemas/upload",
        json={"schema_name": "product", "schema": VALID_PRODUCT_SCHEMA},
        headers=_auth({}, tokens["viewer"]),
    )
    assert response.status_code == 403


def test_editor_can_upload_private(auth_client) -> None:
    client, tokens = auth_client
    response = client.post(
        "/schemas/upload",
        json={"schema_name": "product", "schema": VALID_PRODUCT_SCHEMA, "visibility": "private"},
        headers=_auth({}, tokens["editor"]),
    )
    assert response.status_code == 200


def test_private_schema_hidden_from_other_users(auth_client) -> None:
    client, tokens = auth_client
    client.post(
        "/schemas/upload",
        json={"schema_name": "secret", "schema": VALID_PRODUCT_SCHEMA, "visibility": "private"},
        headers=_auth({}, tokens["editor"]),
    )

    editor_list = client.get("/schemas", headers=_auth({}, tokens["editor"])).json()["schemas"]
    viewer_list = client.get("/schemas", headers=_auth({}, tokens["viewer"])).json()["schemas"]
    admin_list = client.get("/schemas", headers=_auth({}, tokens["admin"])).json()["schemas"]

    assert "secret" in editor_list
    assert "secret" not in viewer_list
    assert "secret" in admin_list


def test_public_schema_visible_to_viewer(auth_client) -> None:
    client, tokens = auth_client
    client.post(
        "/schemas/upload",
        json={"schema_name": "shared", "schema": VALID_PRODUCT_SCHEMA, "visibility": "public"},
        headers=_auth({}, tokens["editor"]),
    )
    viewer_list = client.get("/schemas", headers=_auth({}, tokens["viewer"])).json()["schemas"]
    assert "shared" in viewer_list


def test_viewer_can_validate_public_schema(auth_client) -> None:
    client, tokens = auth_client
    response = client.post(
        "/validate/single",
        json={"schema_name": "user", "payload": {"id": 1, "email": "a@b.com", "name": "A"}},
        headers=_auth({}, tokens["viewer"]),
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_viewer_cannot_access_private_schema(auth_client) -> None:
    client, tokens = auth_client
    client.post(
        "/schemas/upload",
        json={"schema_name": "hidden", "schema": VALID_PRODUCT_SCHEMA, "visibility": "private"},
        headers=_auth({}, tokens["editor"]),
    )
    response = client.get("/schemas/hidden", headers=_auth({}, tokens["viewer"]))
    assert response.status_code == 403


def test_editor_can_delete_own_schema(auth_client) -> None:
    client, tokens = auth_client
    client.post(
        "/schemas/upload",
        json={"schema_name": "mine", "schema": VALID_PRODUCT_SCHEMA, "visibility": "private"},
        headers=_auth({}, tokens["editor"]),
    )
    response = client.delete("/schemas/mine", headers=_auth({}, tokens["editor"]))
    assert response.status_code == 200


def test_editor_cannot_delete_other_private_schema(auth_client) -> None:
    client, tokens = auth_client
    from app.models.domain import Role, User
    from app.services.auth_service import create_access_token
    from app.storage.metadata_store import get_metadata_store, new_user_id

    store = get_metadata_store()
    other = User(
        id=new_user_id(),
        email="other@example.com",
        name="Other Editor",
        role=Role.EDITOR,
        oauth_provider="test",
        oauth_sub="other-sub",
    )
    store.create_user(other)
    other_token = create_access_token(other)

    client.post(
        "/schemas/upload",
        json={"schema_name": "others", "schema": VALID_PRODUCT_SCHEMA, "visibility": "private"},
        headers=_auth({}, other_token),
    )
    response = client.delete("/schemas/others", headers=_auth({}, tokens["editor"]))
    assert response.status_code == 403
