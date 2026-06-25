VALID_PRODUCT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["sku"],
    "properties": {"sku": {"type": "string"}},
}


def test_list_schemas_includes_user(client) -> None:
    response = client.get("/schemas")
    assert response.status_code == 200
    names = response.json()["schemas"]
    assert "user" in names
    assert "user_profile" in names


def test_upload_schema_success(client) -> None:
    response = client.post(
        "/schemas/upload",
        json={"schema_name": "product", "schema": VALID_PRODUCT_SCHEMA},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["schema_name"] == "product"


def test_upload_schema_invalid_definition(client) -> None:
    response = client.post(
        "/schemas/upload",
        json={"schema_name": "bad", "schema": {"type": "not-a-real-type"}},
    )
    assert response.status_code == 422


def test_upload_then_list_and_validate(client) -> None:
    client.post(
        "/schemas/upload",
        json={"schema_name": "product", "schema": VALID_PRODUCT_SCHEMA},
    )
    list_response = client.get("/schemas")
    assert "product" in list_response.json()["schemas"]

    validate_response = client.post(
        "/validate/single",
        json={"schema_name": "product", "payload": {"sku": "ABC-123"}},
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["valid"] is True


def test_upload_overwrites_existing_schema(client) -> None:
    strict_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["sku", "price"],
        "properties": {
            "sku": {"type": "string"},
            "price": {"type": "number"},
        },
    }
    client.post("/schemas/upload", json={"schema_name": "product", "schema": VALID_PRODUCT_SCHEMA})
    client.post("/schemas/upload", json={"schema_name": "product", "schema": strict_schema})

    response = client.post(
        "/validate/single",
        json={"schema_name": "product", "payload": {"sku": "X"}},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_upload_schema_name_with_json_extension_rejected(client) -> None:
    response = client.post(
        "/schemas/upload",
        json={"schema_name": "widget.json", "schema": VALID_PRODUCT_SCHEMA},
    )
    assert response.status_code == 422


def test_upload_schema_path_traversal_rejected(client) -> None:
    response = client.post(
        "/schemas/upload",
        json={"schema_name": "../evil", "schema": VALID_PRODUCT_SCHEMA},
    )
    assert response.status_code in (400, 422, 404)


def test_upload_empty_schema_rejected(client) -> None:
    response = client.post(
        "/schemas/upload",
        json={"schema_name": "empty", "schema": {}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_list_schemas_returns_sorted(client) -> None:
    names = client.get("/schemas").json()["schemas"]
    assert names == sorted(names)
