"""Pytest configuration & fixtures for FastRoom backend unit tests.

Provides:
 - In-memory SQLite async database (overrides production DB)
 - FastAPI app fixture with dependency overrides (DB + Redis)
 - Async HTTP client without running real lifespan (avoids real Redis)
 - Helper factories for creating users & auth tokens
"""

from __future__ import annotations

import os

os.environ["FASTROOM_TEST"] = "1"  # enable Settings.test_mode


import asyncio
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from typing import Any

import bcrypt
import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from fast_room_api.api import dependencies as deps
from fast_room_api.api.main import app as real_app
from fast_room_api.models import db as models_db
from fast_room_api.models.db import Base, UserORM

# ---------------------------------------------------------------------------
# Event loop (pytest-asyncio auto mode may not be enabled in some envs)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Test Database (SQLite in-memory, single engine shared across tests)


@pytest.fixture(scope="session")
def test_engine():
    return _create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)


@pytest_asyncio.fixture(scope="session")
async def _create_all(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:  # optional teardown
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine, _create_all) -> AsyncGenerator[AsyncSession, None]:
    SessionTest = async_sessionmaker(test_engine, expire_on_commit=False)
    async with SessionTest() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


# ---------------------------------------------------------------------------
# Fake Redis implementation (enough surface for code under test)
# ---------------------------------------------------------------------------


class _FakePubSub:
    def __init__(self, parent: FakeRedis) -> None:
        self.parent = parent
        self._subscribed: set[str] = set()
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._listening = True

    async def subscribe(self, *channels: str) -> None:
        for ch in channels:
            self._subscribed.add(ch)

    async def unsubscribe(self, *channels: str) -> None:
        for ch in channels:
            self._subscribed.discard(ch)

    async def listen(self):  # async generator
        while self._listening:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=0.05)
                yield {"type": "message", "data": msg}
            except TimeoutError:
                if not self._subscribed:  # idle and nothing subscribed
                    await asyncio.sleep(0.01)

    async def push(self, channel: str, data: dict[str, Any] | str) -> None:
        if channel in self._subscribed:
            if isinstance(data, str):
                import json as _json

                try:
                    parsed = _json.loads(data)
                except Exception:
                    parsed = {"raw": data}
                if isinstance(parsed, dict):
                    await self._queue.put(parsed)
                else:
                    await self._queue.put({"data": parsed})
            else:
                await self._queue.put(data)

    async def close(self):
        self._listening = False


class FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._pubsub = _FakePubSub(self)
        self._published: list[tuple[str, str]] = []  # (channel, payload)

    # Presence / heartbeat related
    async def psetex(self, key: str, ttl_ms: int, value: str) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def scan(self, cursor: int, match: str, count: int = 50):
        # naive pattern: match must be prefix*
        prefix = match[:-1] if match.endswith("*") else match
        keys = [k for k in list(self._data.keys()) if k.startswith(prefix)]
        return 0, keys  # single pass

    async def hgetall(self, key: str) -> dict[str, str]:
        return self._hashes.get(key, {})

    # Pub/Sub & publishing
    def pubsub(self):
        return self._pubsub

    async def publish(self, channel: str, payload: str) -> None:
        self._published.append((channel, payload))
        await self._pubsub.push(channel, payload)

    # Compatibility helpers
    @classmethod
    def from_url(cls, *_args: Any, **_kwargs: Any) -> FakeRedis:  # for lifespan fallback
        return cls()

    async def close(self):  # used in lifespan
        await self._pubsub.close()


@pytest.fixture(scope="session")
def fake_redis() -> FakeRedis:
    return FakeRedis()


# ---------------------------------------------------------------------------
# FastAPI app fixture with dependency overrides
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app(fake_redis: FakeRedis):
    # Patch redis-related lifespan by disabling it (transport lifespan off) & attach fake redis
    # Ensure ws module missing constant patched for presence endpoint import

    real_app.state.redis = fake_redis  # for any direct access

    # Override redis dependency
    async def _override_get_ws_redis_client(_=None):
        return fake_redis

    real_app.dependency_overrides[deps.get_ws_redis_client] = _override_get_ws_redis_client
    return real_app


@pytest_asyncio.fixture()
async def client(app) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# DB dependency override (per-test session)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _override_get_db(app, db_session: AsyncSession):
    async def _get_db_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[models_db.get_db] = _get_db_override
    yield
    app.dependency_overrides.pop(models_db.get_db, None)


# ---------------------------------------------------------------------------
# User / auth helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def create_user(db_session: AsyncSession) -> Callable[[str, str], Awaitable[UserORM]]:
    async def _inner(username: str, password: str) -> UserORM:
        result = await db_session.execute(select(UserORM).where(UserORM.username == username))
        user = result.scalars().first()
        if not user:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user = UserORM(username=username, hashed_password=hashed, email=None, full_name=None)
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)
            return user
        return user

    return _inner


@pytest_asyncio.fixture()
async def auth_header(create_user, db_session: AsyncSession) -> Callable[[str, str], Awaitable[dict[str, str]]]:
    async def _inner(username: str, password: str) -> dict[str, str]:
        user = await create_user(username, password)
        token = deps.create_access_token(username=user.username, ttl_seconds=3600)
        return {"Authorization": f"Bearer {token}"}

    return _inner


@pytest.fixture(scope="session")
def unique_username() -> Callable[[], str]:
    constant = f"user_{uuid.uuid4().hex[:10]}"

    def _gen() -> str:
        return constant

    return _gen


@pytest.fixture(scope="session")
def unique_password() -> Callable[[], str]:
    constant = f"pw_{uuid.uuid4().hex[:10]}"

    def _gen() -> str:
        return constant

    return _gen
