# Placeholder for dependencies (auth, redis, etc.)
import hashlib
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

import bcrypt
from fastapi import Depends, FastAPI, HTTPException, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fast_room_api.models.auth import InvalidToken, TokenPayload
from fast_room_api.models.config import settings
from fast_room_api.models.db import RefreshTokenORM, UserORM, get_db

ALGO = "HS256"
HEADER = {"typ": "JWT", "alg": ALGO}
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def _encode_token(payload: TokenPayload) -> str:
    return jwt.encode(
        claims=payload.model_dump(mode="json"),
        key=settings.secret_key,
        algorithm=ALGO,
        headers=HEADER,
    )


def create_access_token(username: str, ttl_seconds: int | None = None) -> str:
    now = int(time.time())
    ttl = ttl_seconds or settings.access_token_exp_seconds
    payload = TokenPayload(sub=username, iat=now, exp=now + ttl, v=1, typ="access", jti=uuid.uuid4())
    return _encode_token(payload)


def create_refresh_token(username: str, ttl_seconds: int | None = None) -> str:
    now = int(time.time())
    ttl = ttl_seconds or settings.refresh_token_exp_seconds
    payload = TokenPayload(sub=username, iat=now, exp=now + ttl, v=1, typ="refresh", jti=uuid.uuid4())
    return _encode_token(payload)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def persist_refresh_token(
    db: AsyncSession,
    username: str,
    refresh_token: str,
    user_agent: str | None,
    ip: str | None,
) -> RefreshTokenORM:
    # Assumes user exists
    result = await db.execute(select(UserORM).where(UserORM.username == username))
    user = result.scalars().first()
    if not user:
        raise InvalidToken("user missing during refresh persist")
    payload = decode_token(refresh_token)
    expiry_dt = datetime.fromtimestamp(payload.exp, tz=UTC)
    rt = RefreshTokenORM(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=expiry_dt,
        user_agent=user_agent,
        ip_address=ip,
    )
    db.add(rt)
    await db.commit()
    await db.refresh(rt)
    return rt


async def revoke_refresh_token(db: AsyncSession, token: str) -> None:
    h = hash_refresh_token(token)
    result = await db.execute(select(RefreshTokenORM).where(RefreshTokenORM.token_hash == h))
    rt = result.scalars().first()
    if rt and not rt.revoked:
        rt.revoked = True
        await db.commit()


async def validate_refresh_token(db: AsyncSession, token: str) -> UserORM | None:
    try:
        payload = decode_token(token)
        if payload.typ != "refresh":
            return None
    except InvalidToken:
        return None
    h = hash_refresh_token(token)
    result = await db.execute(
        select(RefreshTokenORM, UserORM)
        .join(UserORM, RefreshTokenORM.user_id == UserORM.id)
        .where(RefreshTokenORM.token_hash == h)
    )
    row = result.first()
    if not row:
        return None
    rt, user = row
    if rt.revoked:
        return None

    exp = rt.expires_at
    if settings.test_mode:
        # In test mode (SQLite) datetimes may be naive; assume stored as UTC and attach tzinfo.
        exp = exp.replace(tzinfo=UTC)
    if exp < datetime.now(UTC):
        return None
    return user


def decode_token(token: str) -> TokenPayload:
    try:
        token_header: dict[str, Any] = jwt.get_unverified_header(token)
        if token_header != HEADER:
            raise JWTError("invalid header")
        payload: dict[str, Any] = jwt.decode(
            token,
            key=settings.secret_key,
            algorithms=[ALGO],
        )
        return TokenPayload(**payload)
    except (JWTError, ValidationError) as e:
        raise InvalidToken("token decode error") from e


class State(TypedDict):
    redis: Redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    yield {"redis": redis}
    await redis.close()


async def get_ws_redis_client(websocket: WebSocket) -> Redis:
    return websocket.state.redis


async def get_user_by_username(db: AsyncSession, username: str) -> UserORM | None:
    result = await db.execute(select(UserORM).where(UserORM.username == username))
    return result.scalars().first()


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserORM:
    try:
        token_payload = decode_token(token)
        if token_payload.typ != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        orm_user = await get_user_by_username(db, token_payload.sub)
        if not orm_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return orm_user
    except InvalidToken as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}") from e


async def get_current_active_user(
    current_user: Annotated[UserORM, Depends(get_current_user)],
) -> UserORM:
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def authenticate_user(db: AsyncSession, username: str, password: str) -> UserORM | None:
    orm_user = await get_user_by_username(db, username)
    if not orm_user:
        return None
    if not verify_password(password, orm_user.hashed_password):
        return None
    return orm_user


UserDeps = Annotated[UserORM, Depends(get_current_active_user)]
RedisClient = Annotated[Redis, Depends(get_ws_redis_client)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
