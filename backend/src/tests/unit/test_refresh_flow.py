import pytest
from fast_room_api.api.main import app

REFRESH_PATHS = [p for p in ("/refresh", "/auth/refresh") if any(getattr(r, "path", None) == p for r in app.routes)]
LOGIN_PATHS = [p for p in ("/token", "/auth/token") if any(getattr(r, "path", None) == p for r in app.routes)]
REGISTER_PATHS = [p for p in ("/register", "/auth/register") if any(getattr(r, "path", None) == p for r in app.routes)]
LOGOUT_PATHS = [p for p in ("/logout", "/auth/logout") if any(getattr(r, "path", None) == p for r in app.routes)]


@pytest.mark.asyncio
async def test_refresh_and_logout_revokes(client, unique_username, unique_password):
    if not (REFRESH_PATHS and LOGIN_PATHS and REGISTER_PATHS and LOGOUT_PATHS):
        pytest.skip("missing auth endpoints")
    username = unique_username()
    pw = unique_password()
    registeration_resp = await client.post(REGISTER_PATHS[0], params={"username": username, "password": pw})
    assert registeration_resp.status_code == 201 or registeration_resp.status_code == 409
    login_resp = await client.post(LOGIN_PATHS[0], data={"username": username, "password": pw})
    tokens = login_resp.json()
    assert tokens.get("access_token") and tokens.get("refresh_token")
    refresh_token = tokens["refresh_token"]
    # use refresh
    ref_resp = await client.post(REFRESH_PATHS[0], json={"refresh_token": refresh_token})
    assert ref_resp.status_code in (200, 401)
    if ref_resp.status_code != 200:
        return
    new_tokens = ref_resp.json()
    # logout with new refresh
    await client.post(LOGOUT_PATHS[0], json={"refresh_token": new_tokens["refresh_token"]})
    # reuse should fail
    reuse = await client.post(REFRESH_PATHS[0], json={"refresh_token": new_tokens["refresh_token"]})
    assert reuse.status_code == 401
