import json
import logging
from collections.abc import Awaitable

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fast_room_api.api.dependencies import DBSession, RedisClient, UserDeps
from fast_room_api.api.routers.ws import CHANNEL_PREFIX, SERVER_ID
from fast_room_api.models.db import MessageORM, RoomMemberORM, RoomORM, UserORM
from fast_room_api.models.rooms import (
    Message,
    MessagesPage,
    MessageUpdate,
    PresenceState,
    Room,
    RoomCreate,
    RoomMember,
    RoomMembersPage,
    RoomsPage,
    RoomUpdate,
)
from fast_room_api.models.ws import OutMemberUpdate, OutMessageDeleted, OutMessageUpdated

logger = logging.getLogger("fast_room_api.rooms")
router = APIRouter(prefix="/rooms", tags=["rooms"])


# ---------- Helpers ---------- #


async def _get_room_by_name(db: AsyncSession, name: str) -> RoomORM | None:
    result = await db.execute(select(RoomORM).where(RoomORM.name == name))
    return result.scalars().first()


async def _get_room(db: AsyncSession, room_id: int) -> RoomORM | None:
    result = await db.execute(select(RoomORM).where(RoomORM.id == room_id))
    return result.scalars().first()


# ---------- Endpoints ---------- #


@router.get("/", response_model=RoomsPage)
async def list_rooms(
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    stmt = (
        select(RoomORM)
        .order_by(desc(RoomORM.created_at) if order == "desc" else asc(RoomORM.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = [Room.model_validate(r) for r in result.scalars().all()]
    total = (await db.execute(select(func.count()).select_from(RoomORM))).scalar_one()
    next_offset = offset + limit if offset + limit < total else None
    return RoomsPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=next_offset is not None,
        next_offset=next_offset,
    )


@router.post("/", response_model=Room, status_code=201)
async def create_room(db: DBSession, current_user: UserDeps, payload: RoomCreate):
    existing = await _get_room_by_name(db, payload.name)
    if existing:
        raise HTTPException(status_code=409, detail="room name exists")
    room = RoomORM(name=payload.name, is_private=payload.is_private)
    db.add(room)
    await db.flush()
    db.add(RoomMemberORM(room_id=room.id, user_id=current_user.id, is_moderator=True))
    await db.commit()
    await db.refresh(room)
    return Room.model_validate(room)


@router.get("/{room_id}", response_model=Room)
async def get_room(room_id: int, db: DBSession):
    room = await _get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    return Room.model_validate(room)


@router.patch("/{room_id}", response_model=Room)
async def update_room(room_id: int, payload: RoomUpdate, db: DBSession, current_user: UserDeps):
    room = await _get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    mod_stmt = select(RoomMemberORM).where(
        RoomMemberORM.room_id == room_id,
        RoomMemberORM.user_id == current_user.id,
        RoomMemberORM.is_moderator.is_(True),
    )
    is_mod = (await db.execute(mod_stmt)).scalars().first()
    if not is_mod:
        raise HTTPException(status_code=403, detail="not moderator")
    changed = False
    if payload.name and payload.name != room.name:
        conflict = await _get_room_by_name(db, payload.name)
        if conflict:
            raise HTTPException(status_code=409, detail="room name exists")
        room.name = payload.name
        changed = True
    if payload.is_private is not None and payload.is_private != room.is_private:
        room.is_private = payload.is_private
        changed = True
    if changed:
        await db.commit()
        await db.refresh(room)
    return Room.model_validate(room)


@router.delete("/{room_id}", status_code=204)
async def delete_room(room_id: int, db: DBSession, current_user: UserDeps):
    room = await _get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    mod_stmt = select(RoomMemberORM).where(
        RoomMemberORM.room_id == room_id,
        RoomMemberORM.user_id == current_user.id,
        RoomMemberORM.is_moderator.is_(True),
    )
    is_mod = (await db.execute(mod_stmt)).scalars().first()
    if not is_mod:
        raise HTTPException(status_code=403, detail="not moderator")
    await db.delete(room)
    await db.commit()
    return None


@router.get("/{room_id}/members", response_model=RoomMembersPage)
async def list_room_members(
    room_id: int,
    db: DBSession,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    room = await _get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    stmt = (
        select(RoomMemberORM, UserORM.username)
        .join(UserORM, UserORM.id == RoomMemberORM.user_id)
        .where(RoomMemberORM.room_id == room_id)
        .order_by(asc(RoomMemberORM.joined_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    rows = result.all()
    out: list[RoomMember] = [
        RoomMember(
            user_id=member.user_id,
            username=username,
            is_moderator=member.is_moderator,
            is_banned=member.is_banned,
            is_muted=member.is_muted,
            joined_at=member.joined_at,
        )
        for member, username in rows
    ]
    total = (
        await db.execute(select(func.count()).select_from(RoomMemberORM).where(RoomMemberORM.room_id == room_id))
    ).scalar_one()
    next_offset = offset + limit if offset + limit < total else None
    return RoomMembersPage(
        items=out,
        total=total,
        limit=limit,
        offset=offset,
        has_more=next_offset is not None,
        next_offset=next_offset,
    )


@router.post("/{room_id}/join", response_model=RoomMember, status_code=201)
async def join_room(room_id: int, db: DBSession, current_user: UserDeps):
    room = await _get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    # Check existing membership
    stmt = select(RoomMemberORM).where(RoomMemberORM.room_id == room_id, RoomMemberORM.user_id == current_user.id)
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="already member")
    member = RoomMemberORM(room_id=room_id, user_id=current_user.id)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    # Response includes username
    return RoomMember(
        user_id=current_user.id,
        username=current_user.username,
        is_moderator=member.is_moderator,
        is_banned=member.is_banned,
        is_muted=member.is_muted,
        joined_at=member.joined_at,
    )


@router.delete("/{room_id}/leave", status_code=204)
async def leave_room(room_id: int, db: DBSession, current_user: UserDeps):
    room = await _get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    stmt = select(RoomMemberORM).where(RoomMemberORM.room_id == room_id, RoomMemberORM.user_id == current_user.id)
    existing = (await db.execute(stmt)).scalars().first()
    if not existing:
        raise HTTPException(status_code=404, detail="membership not found")
    await db.delete(existing)
    await db.commit()
    return None


@router.get("/{room_id}/messages", response_model=MessagesPage)
async def list_room_messages(
    room_id: int,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    room = await _get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    stmt = (
        select(MessageORM, UserORM.username)
        .join(UserORM, UserORM.id == MessageORM.user_id, isouter=True)
        .where(MessageORM.room_id == room_id)
        .order_by(desc(MessageORM.id))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    rows = list(reversed(result.all()))
    items = [
        Message(
            id=m.id,
            user_id=m.user_id,
            username=uname,
            content=m.content,
            created_at=m.created_at,
        )
        for m, uname in rows
    ]
    total = (
        await db.execute(select(func.count()).select_from(MessageORM).where(MessageORM.room_id == room_id))
    ).scalar_one()
    next_offset = offset + limit if offset + limit < total else None
    return MessagesPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=next_offset is not None,
        next_offset=next_offset,
    )


@router.patch("/{room_id}/messages/{message_id}", response_model=Message)
async def edit_message(
    room_id: int,
    message_id: int,
    payload: MessageUpdate,
    db: DBSession,
    current_user: UserDeps,
    redis_client: RedisClient,
):
    room = await _get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    stmt = select(MessageORM).where(MessageORM.id == message_id, MessageORM.room_id == room_id)
    msg_obj = (await db.execute(stmt)).scalars().first()
    if not msg_obj:
        raise HTTPException(status_code=404, detail="message not found")
    is_mine = msg_obj.user_id == current_user.id
    is_mod = (
        (
            await db.execute(
                select(RoomMemberORM).where(
                    RoomMemberORM.room_id == room_id,
                    RoomMemberORM.user_id == current_user.id,
                    RoomMemberORM.is_moderator.is_(True),
                )
            )
        )
        .scalars()
        .first()
    )
    if not (is_mine or is_mod):
        raise HTTPException(status_code=403, detail="not permitted")
    msg_obj.content = payload.content
    await db.commit()
    await db.refresh(msg_obj)
    uname = (await db.execute(select(UserORM.username).where(UserORM.id == msg_obj.user_id))).scalar_one_or_none()
    # Broadcast websocket event
    room_name = room.name
    evt = OutMessageUpdated(room=room_name, message_id=msg_obj.id, content=msg_obj.content).model_dump(mode="json")
    evt.setdefault("srv", SERVER_ID)
    await redis_client.publish(CHANNEL_PREFIX + room_name, json.dumps(evt))
    return Message(
        id=msg_obj.id,
        user_id=msg_obj.user_id,
        username=uname,
        content=msg_obj.content,
        created_at=msg_obj.created_at,
    )


@router.delete("/{room_id}/messages/{message_id}", status_code=204)
async def delete_message(
    room_id: int, message_id: int, db: DBSession, current_user: UserDeps, redis_client: RedisClient
):
    stmt = select(MessageORM).where(MessageORM.id == message_id, MessageORM.room_id == room_id)
    msg_obj = (await db.execute(stmt)).scalars().first()
    if not msg_obj:
        raise HTTPException(status_code=404, detail="message not found")
    is_mine = msg_obj.user_id == current_user.id
    is_mod = (
        (
            await db.execute(
                select(RoomMemberORM).where(
                    RoomMemberORM.room_id == room_id,
                    RoomMemberORM.user_id == current_user.id,
                    RoomMemberORM.is_moderator.is_(True),
                )
            )
        )
        .scalars()
        .first()
    )
    if not (is_mine or is_mod):
        raise HTTPException(status_code=403, detail="not permitted")
    room = await _get_room(db, room_id)
    room_name = room.name if room else str(room_id)
    await db.delete(msg_obj)
    await db.commit()
    evt = OutMessageDeleted(room=room_name, message_id=message_id).model_dump(mode="json")
    evt.setdefault("srv", SERVER_ID)
    await redis_client.publish(CHANNEL_PREFIX + room_name, json.dumps(evt))
    return None


@router.get("/by-name/{room_name}", response_model=Room)
async def get_room_by_name(room_name: str, db: DBSession):
    room = await _get_room_by_name(db, room_name)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    return Room.model_validate(room)


@router.get("/{room_id}/presence", response_model=PresenceState)
async def get_room_presence(room_id: int, db: DBSession, redis_client: RedisClient):
    room = await _get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    from fast_room_api.api.routers.ws import HEARTBEAT_KEY_PREFIX  # local import to avoid cycle

    key = HEARTBEAT_KEY_PREFIX + room.name
    users_map: Awaitable[dict] | dict = redis_client.hgetall(key)
    if isinstance(users_map, Awaitable):
        users_map = await users_map
    users = sorted(users_map.keys())
    return PresenceState(room_id=room.id, room=room.name, users=users, count=len(users))


# -------- Moderation member actions -------- #


async def _require_moderator(db: DBSession, room_id: int, user_id: int) -> None:
    mod_stmt = select(RoomMemberORM).where(
        RoomMemberORM.room_id == room_id,
        RoomMemberORM.user_id == user_id,
        RoomMemberORM.is_moderator.is_(True),
    )
    if not (await db.execute(mod_stmt)).scalars().first():
        raise HTTPException(status_code=403, detail="not moderator")


def _member_to_schema(member: RoomMemberORM, username: str) -> RoomMember:
    return RoomMember(
        user_id=member.user_id,
        username=username,
        is_moderator=member.is_moderator,
        is_banned=member.is_banned,
        is_muted=member.is_muted,
        joined_at=member.joined_at,
    )


@router.post("/{room_id}/members/{target_user_id}/moderator", response_model=RoomMember)
async def toggle_moderator(
    room_id: int,
    target_user_id: int,
    db: DBSession,
    current_user: UserDeps,
    redis_client: RedisClient,
):
    await _require_moderator(db, room_id, current_user.id)
    stmt = (
        select(RoomMemberORM, UserORM.username)
        .join(UserORM, UserORM.id == RoomMemberORM.user_id)
        .where(
            RoomMemberORM.room_id == room_id,
            RoomMemberORM.user_id == target_user_id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="member not found")
    member, username = row
    member.is_moderator = not member.is_moderator
    await db.commit()
    await db.refresh(member)
    room = await _get_room(db, room_id)
    if room:
        evt = OutMemberUpdate(
            room=room.name,
            user_id=member.user_id,
            username=username,
            is_moderator=member.is_moderator,
            is_banned=member.is_banned,
            is_muted=member.is_muted,
        ).model_dump(mode="json")
        evt.setdefault("srv", SERVER_ID)
        await redis_client.publish(CHANNEL_PREFIX + room.name, json.dumps(evt))
    return _member_to_schema(member, username)


@router.post("/{room_id}/members/{target_user_id}/ban", response_model=RoomMember)
async def toggle_ban(
    room_id: int,
    target_user_id: int,
    db: DBSession,
    current_user: UserDeps,
    redis_client: RedisClient,
):
    await _require_moderator(db, room_id, current_user.id)
    stmt = (
        select(RoomMemberORM, UserORM.username)
        .join(UserORM, UserORM.id == RoomMemberORM.user_id)
        .where(
            RoomMemberORM.room_id == room_id,
            RoomMemberORM.user_id == target_user_id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="member not found")
    member, username = row
    member.is_banned = not member.is_banned
    await db.commit()
    await db.refresh(member)
    room = await _get_room(db, room_id)
    if room:
        evt = OutMemberUpdate(
            room=room.name,
            user_id=member.user_id,
            username=username,
            is_moderator=member.is_moderator,
            is_banned=member.is_banned,
            is_muted=member.is_muted,
        ).model_dump(mode="json")
        evt.setdefault("srv", SERVER_ID)
        await redis_client.publish(CHANNEL_PREFIX + room.name, json.dumps(evt))
    return _member_to_schema(member, username)


@router.post("/{room_id}/members/{target_user_id}/mute", response_model=RoomMember)
async def toggle_mute(
    room_id: int,
    target_user_id: int,
    db: DBSession,
    current_user: UserDeps,
    redis_client: RedisClient,
):
    await _require_moderator(db, room_id, current_user.id)
    stmt = (
        select(RoomMemberORM, UserORM.username)
        .join(UserORM, UserORM.id == RoomMemberORM.user_id)
        .where(
            RoomMemberORM.room_id == room_id,
            RoomMemberORM.user_id == target_user_id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="member not found")
    member, username = row
    member.is_muted = not member.is_muted
    await db.commit()
    await db.refresh(member)
    room = await _get_room(db, room_id)
    if room:
        evt = OutMemberUpdate(
            room=room.name,
            user_id=member.user_id,
            username=username,
            is_moderator=member.is_moderator,
            is_banned=member.is_banned,
            is_muted=member.is_muted,
        ).model_dump(mode="json")
        evt.setdefault("srv", SERVER_ID)
        await redis_client.publish(CHANNEL_PREFIX + room.name, json.dumps(evt))
    return _member_to_schema(member, username)
