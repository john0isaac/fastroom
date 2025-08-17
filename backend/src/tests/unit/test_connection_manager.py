import pytest

from fast_room_api.api.routers.ws import HEARTBEAT_KEY_PREFIX, ConnectionManager


class DummyWS:
    def __init__(self):
        self.sent = []

    async def accept(self):  # pragma: no cover - not used here
        return None

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code=1000):  # pragma: no cover - not used here
        return None


@pytest.mark.asyncio
async def test_connection_manager_join_leave(fake_redis):
    cm = ConnectionManager(fake_redis)
    ws = DummyWS()
    first = await cm.join("room1", ws, "alice")  # type: ignore[arg-type]
    assert first is True
    # Heartbeat key created
    _, keys = await fake_redis.scan(0, f"{HEARTBEAT_KEY_PREFIX}room1:alice:*")
    assert keys, "heartbeat key missing after join"
    removed, uname = await cm.leave("room1", ws)  # type: ignore[arg-type]
    assert removed is True and uname == "alice"
    _, keys_after = await fake_redis.scan(0, f"{HEARTBEAT_KEY_PREFIX}room1:alice:*")
    assert not keys_after, "heartbeat key not deleted after leave"


@pytest.mark.asyncio
async def test_connection_manager_multi_join_same_user(fake_redis):
    cm = ConnectionManager(fake_redis)
    ws1 = DummyWS()
    ws2 = DummyWS()
    first = await cm.join("roomx", ws1, "bob")  # type: ignore[arg-type]
    second = await cm.join("roomx", ws2, "bob")  # type: ignore[arg-type]
    assert first is True
    assert second is False  # second websocket for same user shouldn't be first_global
