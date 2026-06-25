VALID_USER_PAYLOAD = {
    "id": 1,
    "email": "jane@example.com",
    "name": "Jane Doe",
}

INVALID_USER_PAYLOAD = {
    "id": "bad",
    "email": "not-an-email",
    "name": "",
}


def test_validate_single_valid(client) -> None:
    response = client.post(
        "/validate/single",
        json={"schema_name": "user", "payload": VALID_USER_PAYLOAD},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []


def test_validate_single_invalid(client) -> None:
    response = client.post(
        "/validate/single",
        json={"schema_name": "user", "payload": INVALID_USER_PAYLOAD},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0
    assert all("path" in err and "message" in err for err in data["errors"])


def test_validate_single_unknown_schema(client) -> None:
    response = client.post(
        "/validate/single",
        json={"schema_name": "does_not_exist", "payload": {"x": 1}},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_validate_batch_mixed(client) -> None:
    response = client.post(
        "/validate/batch",
        json={
            "items": [
                {"schema_name": "user", "payload": VALID_USER_PAYLOAD},
                {"schema_name": "user", "payload": INVALID_USER_PAYLOAD},
            ]
        },
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert results[0]["index"] == 0
    assert results[0]["valid"] is True
    assert results[1]["index"] == 1
    assert results[1]["valid"] is False


def test_validate_batch_empty_rejected(client) -> None:
    response = client.post("/validate/batch", json={"items": []})
    assert response.status_code == 422


def test_validate_batch_unknown_schema_in_one_item(client) -> None:
    response = client.post(
        "/validate/batch",
        json={
            "items": [
                {"schema_name": "user", "payload": VALID_USER_PAYLOAD},
                {"schema_name": "no_such_schema", "payload": {"x": 1}},
            ]
        },
    )
    assert response.status_code == 404


def test_validate_single_extra_fields_rejected(client) -> None:
    payload = {**VALID_USER_PAYLOAD, "unexpected_field": "oops"}
    response = client.post(
        "/validate/single",
        json={"schema_name": "user", "payload": payload},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert any("unexpected_field" in err["message"] for err in data["errors"])


def test_validate_single_missing_required_fields(client) -> None:
    response = client.post(
        "/validate/single",
        json={"schema_name": "user", "payload": {"name": "No ID or email"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    missing = {err["path"] for err in data["errors"]}
    assert "(root)" in missing


def test_validate_single_null_field_value(client) -> None:
    payload = {**VALID_USER_PAYLOAD, "name": None}
    response = client.post(
        "/validate/single",
        json={"schema_name": "user", "payload": payload},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_validate_single_schema_name_with_json_extension(client) -> None:
    response = client.post(
        "/validate/single",
        json={"schema_name": "user.json", "payload": VALID_USER_PAYLOAD},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_validate_single_path_traversal_schema_name(client) -> None:
    response = client.post(
        "/validate/single",
        json={"schema_name": "../etc/passwd", "payload": {}},
    )
    assert response.status_code == 404


def test_validate_error_path_format(client) -> None:
    payload = {**VALID_USER_PAYLOAD, "id": "not-an-int"}
    response = client.post(
        "/validate/single",
        json={"schema_name": "user", "payload": payload},
    )
    data = response.json()
    assert data["valid"] is False
    error = data["errors"][0]
    assert "path" in error
    assert "message" in error
    assert "validator" in error
