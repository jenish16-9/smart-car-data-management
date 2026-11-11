from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


async def test_health(client):
    response = await client.get("http://test/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_register_user(client):
    response = await client.post(
        "/auth/register", json={"name": "Jane", "email": "Jane@Example.com", "password": "secret-pass-1"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert body["role"] == "user"
    assert "password" not in body and "password_hash" not in body


async def test_register_duplicate_email_conflicts(client):
    payload = {"name": "Jane", "email": "jane@example.com", "password": "secret-pass-1"}
    assert (await client.post("/auth/register", json=payload)).status_code == 201
    assert (await client.post("/auth/register", json=payload)).status_code == 409


async def test_register_cannot_choose_admin_role(client):
    payload = {"name": "Eve", "email": "eve@example.com", "password": "secret-pass-1", "role": "admin"}
    assert (await client.post("/auth/register", json=payload)).json()["role"] == "user"


async def test_login_returns_token_and_user(client, admin_headers):
    response = await client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert body["user"]["role"] == "admin"


async def test_login_rejects_wrong_password_and_unknown_user(client, admin_headers):
    wrong = await client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "nope-nope"})
    unknown = await client.post("/auth/login", json={"email": "ghost@example.com", "password": "whatever1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"] == "Invalid email or password"


async def test_me_and_profile_update(client, user_headers):
    me = await client.get("/auth/me", headers=user_headers)
    assert me.status_code == 200 and me.json()["email"] == "user@example.com"
    patched = await client.patch("/users/me", json={"name": "New Name"}, headers=user_headers)
    assert patched.json()["name"] == "New Name"


async def test_logout_revokes_token(client, user_headers):
    assert (await client.post("/auth/logout", headers=user_headers)).status_code == 200
    assert (await client.get("/auth/me", headers=user_headers)).status_code == 401


async def test_protected_endpoints_require_a_valid_token(client):
    protected = [
        ("GET", "/auth/me"),
        ("GET", "/users/me"),
        ("GET", "/vehicles"),
        ("POST", "/vehicles"),
        ("GET", "/audio"),
        ("GET", "/alerts"),
        ("GET", "/telemetry/CAR-1/latest"),
        ("GET", "/analytics/summary"),
        ("GET", "/analytics/events-over-time"),
        ("GET", "/analytics/events-by-type"),
    ]
    for method, path in protected:
        missing = await client.request(method, path)
        assert missing.status_code == 401, (method, path)
        bad = await client.request(method, path, headers={"Authorization": "Bearer not-a-real-token"})
        assert bad.status_code == 401, (method, path)
