import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import asc, select

from fast_room_api.api.dependencies import DBSession, UserDeps
from fast_room_api.models.db import UserORM
from fast_room_api.models.users import User

logger = logging.getLogger("fast_room_api.users")
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=User)
async def read_users_me(current_user: UserDeps):
    return current_user


@router.get("/", response_model=list[User])
async def list_users(
    db: DBSession,
    current_user: UserDeps,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order: Literal["asc", "desc"] = Query("asc"),
):
    stmt = select(UserORM).order_by(asc(UserORM.username)).limit(limit).offset(offset)
    if order == "desc":
        stmt = select(UserORM).order_by(UserORM.username.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [
        User(
            username=u.username,
            email=u.email,
            full_name=u.full_name,
            disabled=u.disabled,
        )
        for u in users
    ]


@router.get("/{username}", response_model=User)
async def get_user(username: str, current_user: UserDeps, db: DBSession):
    result = await db.execute(select(UserORM).where(UserORM.username == username))
    u = result.scalars().first()
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    return User(
        username=u.username,
        email=u.email,
        full_name=u.full_name,
        disabled=u.disabled,
    )
