from datetime import UTC, datetime, timedelta

import pytest
from fast_room_api.api import dependencies as deps
from fast_room_api.models.auth import InvalidToken
from fast_room_api.models.db import RefreshTokenORM


@pytest.mark.asyncio
async def test_access_and_refresh_token_roundtrip(create_user, unique_username, unique_password, db_session):
    user = await create_user(unique_username(), unique_password())
    access = deps.create_access_token(user.username, ttl_seconds=60)
    refresh = deps.create_refresh_token(user.username, ttl_seconds=120)
    payload_a = deps.decode_token(access)
    payload_r = deps.decode_token(refresh)
    assert payload_a.sub == user.username and payload_a.typ == "access"
    assert payload_r.sub == user.username and payload_r.typ == "refresh"

    # Persist refresh token
    await deps.persist_refresh_token(db_session, user.username, refresh, user_agent="pytest", ip="127.0.0.1")
    # Validate
    validated = await deps.validate_refresh_token(db_session, refresh)
    assert validated and validated.id == user.id


@pytest.mark.asyncio
async def test_refresh_token_revocation(create_user, unique_username, unique_password, db_session):
    user = await create_user(unique_username(), unique_password())
    refresh = deps.create_refresh_token(user.username, ttl_seconds=120)
    await deps.persist_refresh_token(db_session, user.username, refresh, None, None)
    await deps.revoke_refresh_token(db_session, refresh)
    res = await deps.validate_refresh_token(db_session, refresh)
    assert res is None


@pytest.mark.asyncio
async def test_refresh_token_expiry_handling(create_user, unique_username, unique_password, db_session):
    user = await create_user(unique_username(), unique_password())
    refresh = deps.create_refresh_token(user.username, ttl_seconds=120)
    await deps.persist_refresh_token(db_session, user.username, refresh, None, None)
    # Force expiry
    h = deps.hash_refresh_token(refresh)
    row = (
        (await db_session.execute(deps.select(RefreshTokenORM).where(RefreshTokenORM.token_hash == h)))
        .scalars()
        .first()
    )
    assert row
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    res = await deps.validate_refresh_token(db_session, refresh)
    assert res is None


@pytest.mark.asyncio
async def test_invalid_token_decode():
    with pytest.raises(InvalidToken):
        deps.decode_token("not-a-real-jwt")


@pytest.mark.asyncio
async def test_password_hash_and_verify():
    pw = "Sup3r$ecret"
    hashed = deps.get_password_hash(pw)
    assert deps.verify_password(pw, hashed) is True
    assert deps.verify_password("wrong", hashed) is False
