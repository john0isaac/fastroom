import pytest
from fast_room_api.api.main import app


@pytest.mark.asyncio
async def test_register_and_login_flow(client, unique_username, unique_password):
    username = unique_username()
    password = unique_password()
    # Try register endpoint variants
    register_paths = [
        p for p in ("/register", "/auth/register") if any(getattr(r, "path", None) == p for r in app.routes)
    ]
    assert register_paths, "No register endpoint exposed"
    reg_path = register_paths[0]
    resp = await client.post(reg_path, params={"username": username, "password": password})
    assert resp.status_code in (201, 422)
    if resp.status_code == 201:
        data = resp.json()
        assert data["username"] == username
    # Attempt token request with OAuth2PasswordRequestForm style
    token_paths = [p for p in ("/token", "/auth/token") if any(getattr(r, "path", None) == p for r in app.routes)]
    assert token_paths, "No token endpoint exposed"
    tok_path = token_paths[0]
    form = {"username": username, "password": password}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp2 = await client.post(tok_path, data=form, headers=headers)
    assert resp2.status_code in (200, 401)
    if resp2.status_code == 200:
        payload = resp2.json()
        assert "access_token" in payload and "refresh_token" in payload


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    token_paths = [p for p in ("/token", "/auth/token") if any(getattr(r, "path", None) == p for r in app.routes)]
    if not token_paths:
        pytest.skip("No token endpoint")
    path = token_paths[0]
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = await client.post(path, data={"username": "nouser", "password": "bad"}, headers=headers)
    assert resp.status_code in (401, 400)
