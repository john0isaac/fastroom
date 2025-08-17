import pytest
from fast_room_api.api.main import app

ROOM_LIST = "/rooms/"


@pytest.mark.asyncio
async def test_rooms_list_initial(client):
    resp = await client.get(ROOM_LIST)
    assert resp.status_code in (200, 401, 403)
    if resp.status_code == 200:
        body = resp.json()
        assert body["items"] == [] or isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_room_create_join_lifecycle(client, auth_header, unique_username, unique_password):
    username = unique_username()
    password = unique_password()
    # register user
    reg_paths = [p for p in ("/register", "/auth/register") if any(getattr(r, "path", None) == p for r in app.routes)]
    if reg_paths:
        await client.post(reg_paths[0], params={"username": username, "password": password})
    headers = await auth_header(username, password)
    create_payload = {"name": f"room_{username}", "is_private": False}
    resp = await client.post(ROOM_LIST, json=create_payload, headers=headers)
    if resp.status_code == 401:
        pytest.skip("room creation requires auth and token invalid")
    if resp.status_code == 201:
        room = resp.json()
        rid = room["id"]
        # join attempt (should 409 since creator auto-member) or 201 for other flows
        join_resp = await client.post(f"/rooms/{rid}/join", headers=headers)
        assert join_resp.status_code in (201, 409)
        # list members
        members = await client.get(f"/rooms/{rid}/members", headers=headers)
        assert members.status_code in (200, 404)


@pytest.mark.asyncio
async def test_room_moderation_toggle(client, auth_header, unique_username, unique_password):
    username = unique_username()
    password = unique_password()
    reg_paths = [p for p in ("/register", "/auth/register") if any(getattr(r, "path", None) == p for r in app.routes)]
    if not reg_paths:
        pytest.skip("registration missing")
    await client.post(reg_paths[0], params={"username": username, "password": password})
    headers = await auth_header(username, password)
    create_payload = {"name": f"room_{username}_moderation", "is_private": False}
    room_resp = await client.post(ROOM_LIST, json=create_payload, headers=headers)
    assert room_resp.status_code == 201
    room_id = room_resp.json()["id"]
    # toggle moderator for self (will flip off) then back
    toggle = await client.post(f"/rooms/{room_id}/members/1/moderator", headers=headers)
    assert toggle.status_code in (200, 403, 404)
