import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fast_room_api.api.dependencies import (
    DBSession,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    persist_refresh_token,
    revoke_refresh_token,
    validate_refresh_token,
)
from fast_room_api.models.auth import RefreshRequest, TokenPair
from fast_room_api.models.db import UserORM
from fast_room_api.models.users import User

logger = logging.getLogger("fast_room_api.auth")
router = APIRouter(tags=["auth"])


def sanitize_username(raw: str) -> str:
    """Validate and normalize a user provided username (unique, human-friendly)."""

    if raw is None or raw.strip() == "":
        raise ValueError("Username cannot be empty")
    name = raw.lower().strip()
    # Collapse separators (space / hyphen / underscore) into single underscore
    name = re.sub(r"[ _\-]+", "_", name)
    # Remove leading/trailing underscores that may result from trimming
    name = name.strip("_")
    # Validate allowed characters
    if not name or not re.fullmatch(r"[a-z0-9_.]+", name):
        raise ValueError("Username contains invalid characters")
    if not (3 <= len(name) <= 32):
        raise ValueError("Username length must be between 3 and 32 characters")
    return name


@router.post("/register", response_model=User, status_code=201)
async def register_user(
    db: DBSession,
    username: str,
    password: str,
    email: str | None = None,
    full_name: str | None = None,
):
    try:
        sanitized_username = sanitize_username(username)
    except ValueError:
        raise HTTPException(status_code=422, detail="username length invalid")
    if len(password) < 6:
        raise HTTPException(status_code=422, detail="password too short")
    db_user = await db.execute(select(UserORM).where(UserORM.username == sanitized_username))
    if db_user.scalars().first():
        raise HTTPException(status_code=409, detail="username already exists")
    hashed_pw = get_password_hash(password)
    user = UserORM(
        username=sanitized_username,
        email=email,
        full_name=full_name,
        hashed_password=hashed_pw,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="username or email already exists")
    await db.refresh(user)
    return User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
    )


@router.post("/token", response_model=TokenPair)
async def login_for_access_token(
    db: DBSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenPair:
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(username=user.username)
    refresh_token = create_refresh_token(username=user.username)
    # Persist refresh token hash (best effort; failures shouldn't leak raw token)
    try:
        await persist_refresh_token(
            db,
            username=user.username,
            refresh_token=refresh_token,
            user_agent=None,
            ip=None,
        )
    except Exception:
        logger.exception("refresh token persistence failed")
    return TokenPair(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(db: DBSession, payload: RefreshRequest) -> TokenPair:
    user = await validate_refresh_token(db, payload.refresh_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    access_token = create_access_token(username=user.username)
    new_refresh = create_refresh_token(username=user.username)
    try:
        # Persist new refresh first (atomicity not guaranteed; could wrap in transaction if needed)
        await persist_refresh_token(
            db,
            username=user.username,
            refresh_token=new_refresh,
            user_agent=None,
            ip=None,
        )
        # Revoke of old token
        await revoke_refresh_token(db, payload.refresh_token)
    except Exception:
        logger.exception("refresh token persistence failed")
    return TokenPair(access_token=access_token, refresh_token=new_refresh)


@router.post("/logout", status_code=204)
async def logout(db: DBSession, payload: RefreshRequest):
    """Revoke a refresh token (best effort) and end session. Access tokens remain stateless."""
    try:
        await revoke_refresh_token(db, payload.refresh_token)
    except Exception:
        logger.exception("logout revoke failed")
    return Response(status_code=204)
