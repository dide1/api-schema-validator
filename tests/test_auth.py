def test_auth_config(client) -> None:
    response = client.get("/auth/config")
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_auth_me_without_auth_disabled(client) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_jwt_create_and_decode(auth_client) -> None:
    from app.services.auth_service import decode_access_token

    _client, tokens = auth_client
    payload = decode_access_token(tokens["admin"])
    assert payload["email"] == "admin@example.com"
    assert payload["role"] == "admin"


def test_auth_me_with_token(auth_client) -> None:
    client, tokens = auth_client
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['editor']}"})
    assert response.status_code == 200
    assert response.json()["role"] == "editor"


def test_missing_token_returns_401(auth_client) -> None:
    client, _tokens = auth_client
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_invalid_token_returns_401(auth_client) -> None:
    client, _tokens = auth_client
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_admin_list_users(auth_client) -> None:
    client, tokens = auth_client
    response = client.get("/auth/users", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_viewer_cannot_list_users(auth_client) -> None:
    client, tokens = auth_client
    response = client.get("/auth/users", headers={"Authorization": f"Bearer {tokens['viewer']}"})
    assert response.status_code == 403


def test_team_member_can_list_teammates(auth_client) -> None:
    client, tokens = auth_client
    response = client.get("/auth/team/members", headers={"Authorization": f"Bearer {tokens['editor']}"})
    assert response.status_code == 200
    data = response.json()
    assert data["team_id"] == "team-1"
    emails = {m["email"] for m in data["members"]}
    assert "editor@example.com" in emails
    assert "viewer@example.com" in emails
    # admin has no team_id — must not appear
    assert "admin@example.com" not in emails


def test_viewer_can_list_teammates(auth_client) -> None:
    client, tokens = auth_client
    response = client.get("/auth/team/members", headers={"Authorization": f"Bearer {tokens['viewer']}"})
    assert response.status_code == 200
    assert len(response.json()["members"]) == 2


def test_user_without_team_gets_400(auth_client) -> None:
    client, tokens = auth_client
    response = client.get("/auth/team/members", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert response.status_code == 400


def test_team_members_requires_auth(auth_client) -> None:
    client, _tokens = auth_client
    response = client.get("/auth/team/members")
    assert response.status_code == 401


def test_admin_update_user_role(auth_client) -> None:
    from app.models.domain import Role
    from app.storage.metadata_store import get_metadata_store

    client, tokens = auth_client
    store = get_metadata_store()
    viewer = next(u for u in store.list_users() if u.role == Role.VIEWER)
    response = client.put(
        f"/auth/users/{viewer.id}",
        json={"role": "editor"},
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "editor"
