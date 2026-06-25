VALID_PRODUCT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["sku"],
    "properties": {"sku": {"type": "string"}},
}


def test_get_schema(client) -> None:
    response = client.get("/schemas/user")
    assert response.status_code == 200
    data = response.json()
    assert data["schema_name"] == "user"
    assert "email" in data["schema"]["properties"]


def test_get_schema_not_found(client) -> None:
    response = client.get("/schemas/missing")
    assert response.status_code == 404


def test_update_schema(client) -> None:
    client.post(
        "/schemas/upload",
        json={"schema_name": "product", "schema": VALID_PRODUCT_SCHEMA},
    )
    updated = {
        **VALID_PRODUCT_SCHEMA,
        "required": ["sku", "price"],
        "properties": {"sku": {"type": "string"}, "price": {"type": "number"}},
    }
    response = client.put("/schemas/product", json={"schema": updated})
    assert response.status_code == 200

    get_response = client.get("/schemas/product")
    assert "price" in get_response.json()["schema"]["properties"]


def test_delete_schema(client) -> None:
    client.post(
        "/schemas/upload",
        json={"schema_name": "product", "schema": VALID_PRODUCT_SCHEMA},
    )
    response = client.delete("/schemas/product")
    assert response.status_code == 200
    assert client.get("/schemas/product").status_code == 404


def test_verify_schema_valid(client) -> None:
    response = client.post("/schemas/verify", json={"schema": VALID_PRODUCT_SCHEMA})
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_verify_schema_invalid(client) -> None:
    response = client.post(
        "/schemas/verify",
        json={"schema": {"type": "not-a-real-type"}},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_list_schemas_includes_templates(client) -> None:
    response = client.get("/schemas")
    assert response.status_code == 200
    data = response.json()
    assert "user" in data["schemas"]
    assert len(data["templates"]) >= 2
