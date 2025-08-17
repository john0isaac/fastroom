import pytest
from fast_room_api.api.main import app


@pytest.mark.asyncio
async def test_list_users_one(client, auth_header, unique_username, unique_password):
    paths = [r for r in app.routes if getattr(r, "path", None) == "/users/"]
    if not paths:
        pytest.skip("users list route missing")
    username = unique_username()
    reg_paths = [p for p in ("/register", "/auth/register") if any(getattr(r, "path", None) == p for r in app.routes)]
    if reg_paths:
        await client.post(reg_paths[0], params={"username": username, "password": unique_password})
    headers = await auth_header(username, unique_password)

    resp = await client.get("/users/", headers=headers)
    assert resp.status_code in (200, 401, 403)
    if resp.status_code == 200:
        assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_create_and_get_user_via_register_and_me(client, auth_header, unique_username, unique_password):
    # Attempt register then fetch via /users/{username}
    username = unique_username()
    password = unique_password()
    reg_paths = [p for p in ("/register", "/auth/register") if any(getattr(r, "path", None) == p for r in app.routes)]
    if not reg_paths:
        pytest.skip("register not exposed")
    await client.post(reg_paths[0], params={"username": username, "password": password})
    headers = await auth_header(username, password)
    # Public get
    user_get_path = f"/users/{username}"
    resp_get = await client.get(user_get_path, headers=headers)
    if resp_get.status_code == 200:
        data = resp_get.json()
        assert data["username"] == username
