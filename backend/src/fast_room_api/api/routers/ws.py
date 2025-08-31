import asyncio
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from fast_room_api.api.dependencies import DBSession, RedisClient, get_current_user
from fast_room_api.models.db import MessageORM, RoomMemberORM, RoomORM, UserORM
from fast_room_api.models.ws import (
    OutChatMessage,
    OutPresenceDiff,
    OutPresenceState,
    OutSystemMessage,
    OutTypingMessage,
)

logger = logging.getLogger("fast_room_api.websocket")
router = APIRouter()

SERVER_ID = os.environ.get("SERVER_ID", uuid.uuid4().hex[:6])
CHANNEL_PREFIX = "room:"
HEARTBEAT_KEY_PREFIX = "presence:hb:"
HISTORY_LIMIT = 50  # number of recent chat messages to send on join
HEARTBEAT_INTERVAL = int(os.environ.get("WS_HEARTBEAT_INTERVAL", "25"))  # seconds
HEARTBEAT_TTL_MS = int(os.environ.get("WS_HEARTBEAT_TTL_MS", str((HEARTBEAT_INTERVAL + 5) * 1000)))  # ms
HEARTBEAT_ONLY = True  # Only heartbeat presence is used


class ConnectionManager:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self.conn_rooms: dict[WebSocket, set[str]] = defaultdict(set)
        self.ws_username: dict[WebSocket, str] = {}
        self.pubsub = self.redis.pubsub()
        self.room_subscribed: set[str] = set()
        self.pubsub_task: asyncio.Task | None = None
        # self.reconcile_task removed
        self.lock = asyncio.Lock()
        # Heartbeat tasks keyed by (ws, room)
        self.heartbeat_tasks: dict[tuple[WebSocket, str], asyncio.Task] = {}
        # Connection ids per websocket (stable for its lifetime)
        self.ws_conn_id: dict[WebSocket, str] = {}

    async def ensure_pubsub_task(self):
        if not self.pubsub_task:
            self.pubsub_task = asyncio.create_task(self._pubsub_reader())

    async def _pubsub_reader(self):
        try:
            async for msg in self.pubsub.listen():
                if msg.get("type") != "message":
                    continue
                data = json.loads(msg["data"])
                if data.get("srv") == SERVER_ID:
                    continue
                room = data.get("room")
                if not room:
                    continue
                # Broadcast to local sockets in that room
                for ws in list(self.rooms.get(room, [])):
                    try:
                        await ws.send_json(data)
                    except Exception:
                        logger.debug("failed to send pubsub msg", exc_info=True)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("pubsub reader error")

    async def subscribe_room(self, room: str):
        async with self.lock:
            if room not in self.room_subscribed:
                await self.pubsub.subscribe(CHANNEL_PREFIX + room)
                self.room_subscribed.add(room)
                await self.ensure_pubsub_task()

    async def unsubscribe_room_if_empty(self, room: str):
        async with self.lock:
            if room in self.room_subscribed and not self.rooms.get(room):
                await self.pubsub.unsubscribe(CHANNEL_PREFIX + room)
                self.room_subscribed.discard(room)

    def in_room(self, ws: WebSocket, room: str) -> bool:
        return room in self.conn_rooms.get(ws, set())

    async def join(self, room: str, ws: WebSocket, username: str) -> bool:
        await self.subscribe_room(room)
        self.rooms[room].add(ws)
        self.conn_rooms[ws].add(room)
        self.ws_username[ws] = username
        if ws not in self.ws_conn_id:
            self.ws_conn_id[ws] = uuid.uuid4().hex
        # Determine if this user already has any heartbeat key for this room
        pattern_user = f"{HEARTBEAT_KEY_PREFIX}{room}:{username}:*"
        cursor = 0
        seen = False
        while True:
            cursor, keys = await self.redis.scan(cursor=cursor, match=pattern_user, count=50)
            if keys:
                seen = True
                break
            if cursor == 0:
                break
        first_global = not seen
        await self._start_heartbeat(room, ws, username)
        return first_global

    async def leave(self, room: str, ws: WebSocket) -> tuple[bool, str | None]:
        if room in self.rooms:
            self.rooms[room].discard(ws)
            if not self.rooms[room]:
                self.rooms.pop(room, None)
        self.conn_rooms[ws].discard(room)
        await self._stop_heartbeat(room, ws)
        username = self.ws_username.get(ws)
        removed = False
        if username:
            # Check if any heartbeat key remains for this (room, user)
            pattern_user = f"{HEARTBEAT_KEY_PREFIX}{room}:{username}:*"
            cursor = 0
            any_left = False
            while True:
                cursor, keys = await self.redis.scan(cursor=cursor, match=pattern_user, count=50)
                if keys:
                    any_left = True
                    break
                if cursor == 0:
                    break
            removed = not any_left
        await self.unsubscribe_room_if_empty(room)
        return removed, username

    async def leave_all(self, ws: WebSocket):
        removed_events: list[tuple[str, str]] = []  # (room, username)
        for r in list(self.conn_rooms.get(ws, [])):
            removed, uname = await self.leave(r, ws)
            if removed and uname:
                removed_events.append((r, uname))
        self.conn_rooms.pop(ws, None)
        username = self.ws_username.pop(ws, None)
        self.ws_conn_id.pop(ws, None)
        # Emit presence diffs + system messages for implicit disconnect leaves.
        # Without this, manual disconnect (socket close) would rely on heartbeat TTL expiry to update peers.
        for room, uname in removed_events:
            try:
                diff_payload = OutPresenceDiff(room=room, leave=[uname]).model_dump(mode="json")
                for peer in list(self.rooms.get(room, [])):
                    try:
                        await peer.send_json(diff_payload)
                    except Exception:
                        logger.debug("presence diff (implicit leave) local send failure", exc_info=True)
                await self.publish(room, diff_payload)
                sys_payload = OutSystemMessage(room=room, message=f"{uname} left").model_dump(mode="json")
                for peer in list(self.rooms.get(room, [])):
                    try:
                        await peer.send_json(sys_payload)
                    except Exception:
                        logger.debug("system leave (implicit) local send failure", exc_info=True)
                await self.publish(room, sys_payload)
            except Exception:
                logger.debug(
                    "failed broadcasting implicit leave for room=%s user=%s",
                    room,
                    username or uname,
                    exc_info=True,
                )

    async def publish(self, room: str, data: dict[str, Any]):
        data.setdefault("srv", SERVER_ID)
        # Ensure all values (e.g. datetime) are JSON serializable
        enc = jsonable_encoder(data)
        await self.redis.publish(CHANNEL_PREFIX + room, json.dumps(enc))

    # ---------------- Heartbeat Management -----------------
    def _heartbeat_key(self, room: str, username: str, conn_id: str) -> str:
        return f"{HEARTBEAT_KEY_PREFIX}{room}:{username}:{conn_id}"

    async def _start_heartbeat(self, room: str, ws: WebSocket, username: str):
        key = (ws, room)
        if key in self.heartbeat_tasks:
            return
        conn_id = self.ws_conn_id.get(ws)
        if not conn_id:
            conn_id = uuid.uuid4().hex
            self.ws_conn_id[ws] = conn_id
        # Generate the heartbeat key once (stable for this (ws, room) pair)
        hb_key = self._heartbeat_key(room, username, conn_id)
        # IMPORTANT: Set the key immediately (synchronously) so that a subsequent
        # presence_state scan performed right after join already sees this user.
        try:
            await self.redis.psetex(hb_key, HEARTBEAT_TTL_MS, "1")
        except Exception:
            logger.exception("failed to set initial heartbeat key room=%s user=%s", room, username)

        async def beat():
            try:
                while True:
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
                    await self.redis.psetex(hb_key, HEARTBEAT_TTL_MS, "1")
            except asyncio.CancelledError:
                # Let key expire naturally. Optionally could delete.
                pass
            except Exception:
                logger.exception("heartbeat task error room=%s user=%s", room, username)

        task = asyncio.create_task(beat())
        self.heartbeat_tasks[key] = task

    async def _stop_heartbeat(self, room: str, ws: WebSocket):
        key = (ws, room)
        task = self.heartbeat_tasks.pop(key, None)
        if task:
            task.cancel()
            try:
                await task
            except (Exception, asyncio.CancelledError):
                pass
        # Proactively delete the heartbeat key so presence updates immediately instead of
        # waiting for TTL expiry (otherwise users appear to "linger" in a room after switching).
        try:
            username = self.ws_username.get(ws)
            conn_id = self.ws_conn_id.get(ws)
            if username and conn_id:
                hb_key = self._heartbeat_key(room, username, conn_id)
                await self.redis.delete(hb_key)
        except Exception:
            logger.debug("failed to delete heartbeat key on stop", exc_info=True)


def get_manager(app, redis_client: Redis) -> ConnectionManager:
    mgr = getattr(app.state, "ws_manager", None)
    if mgr is None:
        mgr = ConnectionManager(redis_client)
        app.state.ws_manager = mgr
    return mgr


async def ensure_room_and_membership(db: AsyncSession, room: str, user: UserORM) -> RoomORM:
    result = await db.execute(select(RoomORM).where(RoomORM.name == room))
    room_obj = result.scalars().first()
    if not room_obj:
        room_obj = RoomORM(name=room)
        db.add(room_obj)
        await db.flush()
    # membership (idempotent)
    result = await db.execute(
        select(RoomMemberORM).where(
            RoomMemberORM.room_id == room_obj.id,
            RoomMemberORM.user_id == user.id,
        )
    )
    if not result.scalars().first():
        db.add(RoomMemberORM(room_id=room_obj.id, user_id=user.id))
    await db.commit()
    return room_obj


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    redis_client: RedisClient,
    db: DBSession,
):
    await ws.accept()
    try:
        user = await get_current_user(ws.query_params.get("access_token", ""), db)
    except Exception as e:
        logger.error("user auth failed", exc_info=e)
        await ws.close(code=4400)
        return
    if not user or user.disabled:
        await ws.send_json({"type": "error", "message": "unauthorized"})
        await ws.close(code=4400)
        return
    manager = get_manager(ws.app, redis_client)
    await ws.send_json(
        {
            "type": "system",
            "message": f"connected as {user.username}",
            # Provide heartbeat interval hint (seconds) so client can adapt its ping schedule
            "heartbeatInterval": HEARTBEAT_INTERVAL,
            "presenceMode": "heartbeat",
        }
    )
    logger.debug("ws connected user=%s token_ok=1", user.username)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                await ws.send_json({"type": "error", "message": "invalid json"})
                continue
            mtype = msg.get("type")
            logger.debug("ws msg type=%s user=%s raw=%s", mtype, user.username, raw[:500])
            if mtype == "join":
                room = msg.get("room")
                if not isinstance(room, str):
                    await ws.send_json({"type": "error", "message": "room required"})
                    continue
                room_obj = await ensure_room_and_membership(db, room, user)
                first_global = await manager.join(room, ws, user.username)
                # explicit join ack for frontend
                await ws.send_json({"type": "joined", "room": room})
                # Send full presence state
                # Gather users from heartbeat keys
                pattern = f"{HEARTBEAT_KEY_PREFIX}{room}:*"
                cursor = 0
                user_set: set[str] = set()
                while True:
                    cursor, keys = await redis_client.scan(cursor=cursor, match=pattern, count=100)
                    for k in keys:
                        parts = k.split(":")
                        if len(parts) >= 5:
                            user_set.add(parts[3])
                    if cursor == 0:
                        break
                users_list = sorted(user_set)
                await ws.send_json(OutPresenceState(room=room, users=users_list).model_dump(mode="json"))
                # Fetch recent message history (most recent first, then reverse to chronological)
                history_stmt = (
                    select(MessageORM, UserORM.username)
                    .join(UserORM, MessageORM.user_id == UserORM.id, isouter=True)
                    .where(MessageORM.room_id == room_obj.id)
                    .order_by(desc(MessageORM.created_at))
                    .limit(HISTORY_LIMIT)
                )
                hist_result = await db.execute(history_stmt)
                rows = hist_result.all()
                if rows:
                    initial_messages = []
                    for msg_row, uname in reversed(rows):  # chronological
                        initial_messages.append(
                            OutChatMessage(
                                room=room,
                                user=uname or "",  # empty if user deleted
                                message=msg_row.content,
                                message_id=msg_row.id,
                                ts=msg_row.created_at,
                            ).model_dump(mode="json")
                        )
                    await ws.send_json({"type": "history", "room": room, "messages": initial_messages})
                # Broadcast presence diff if first global appearance
                if first_global:
                    diff_payload = OutPresenceDiff(room=room, join=[user.username]).model_dump(mode="json")
                    # Immediately deliver presence_diff + system line to local peers (excluding the joining socket)
                    for peer in list(manager.rooms.get(room, [])):
                        if peer is ws:
                            continue  # joining client already handles its own joined + presence_state
                        try:
                            await peer.send_json(diff_payload)
                        except Exception:
                            logger.debug("presence diff local send failure", exc_info=True)
                    await manager.publish(room, diff_payload)
                    sys_payload = OutSystemMessage(room=room, message=f"{user.username} joined").model_dump(mode="json")
                    for peer in list(manager.rooms.get(room, [])):
                        if peer is ws:
                            continue
                        try:
                            await peer.send_json(sys_payload)
                        except Exception:
                            logger.debug("system join local send failure", exc_info=True)
                    await manager.publish(room, sys_payload)
            elif mtype == "leave":
                room = msg.get("room")
                if isinstance(room, str) and manager.in_room(ws, room):
                    removed, uname = await manager.leave(room, ws)
                    if removed and uname:
                        diff_payload = OutPresenceDiff(room=room, leave=[uname]).model_dump(mode="json")
                        # Broadcast locally first so connected peers update immediately, then publish for others.
                        for peer in list(manager.rooms.get(room, [])):
                            try:
                                await peer.send_json(diff_payload)
                            except Exception:
                                logger.debug("presence diff (leave) local send failure", exc_info=True)
                        await manager.publish(room, diff_payload)
                        sys_payload = OutSystemMessage(room=room, message=f"{uname} left").model_dump(mode="json")
                        for peer in list(manager.rooms.get(room, [])):
                            try:
                                await peer.send_json(sys_payload)
                            except Exception:
                                logger.debug("system leave local send failure", exc_info=True)
                        await manager.publish(room, sys_payload)
            elif mtype == "chat":
                room = msg.get("room")
                content = msg.get("message")
                if not (isinstance(room, str) and isinstance(content, str) and manager.in_room(ws, room)):
                    await ws.send_json({"type": "error", "message": "invalid chat"})
                    continue
                result = await db.execute(select(RoomORM).where(RoomORM.name == room))
                chat_room_obj = result.scalars().first()
                if not chat_room_obj:
                    await ws.send_json({"type": "error", "message": "room missing"})
                    continue
                # Enforce membership + ban/mute status
                member_stmt = select(RoomMemberORM).where(
                    RoomMemberORM.room_id == chat_room_obj.id,
                    RoomMemberORM.user_id == user.id,
                )
                member = (await db.execute(member_stmt)).scalars().first()
                if not member:
                    await ws.send_json({"type": "error", "message": "not a member"})
                    continue
                if member.is_banned:
                    await ws.send_json({"type": "error", "message": "banned"})
                    continue
                if member.is_muted:
                    await ws.send_json({"type": "error", "message": "muted"})
                    continue
                message_obj = MessageORM(room_id=chat_room_obj.id, user_id=user.id, content=content)
                db.add(message_obj)
                await db.flush()
                await db.commit()
                out = OutChatMessage(room=room, user=user.username, message=content, message_id=message_obj.id)
                payload = out.model_dump(mode="json")
                for peer in list(manager.rooms.get(room, [])):
                    try:
                        await peer.send_json(payload)
                    except Exception:
                        logger.debug("send failure", exc_info=True)
                await manager.publish(room, payload)
            elif mtype == "history_more":
                room = msg.get("room")
                before_id = msg.get("before_id")
                if not (isinstance(room, str) and isinstance(before_id, int) and manager.in_room(ws, room)):
                    await ws.send_json({"type": "error", "message": "invalid history_more"})
                    continue
                # Fetch room id
                result = await db.execute(select(RoomORM).where(RoomORM.name == room))
                history_room_obj = result.scalars().first()
                if not history_room_obj:
                    await ws.send_json({"type": "error", "message": "room missing"})
                    continue
                # Older messages have id < before_id
                history_stmt = (
                    select(MessageORM, UserORM.username)
                    .join(UserORM, MessageORM.user_id == UserORM.id, isouter=True)
                    .where(MessageORM.room_id == history_room_obj.id, MessageORM.id < before_id)
                    .order_by(desc(MessageORM.created_at))
                    .limit(HISTORY_LIMIT)
                )
                hist_result = await db.execute(history_stmt)
                rows = hist_result.all()
                older_messages: list[dict[str, Any]] = []
                if rows:
                    for msg_row, uname in reversed(rows):  # reverse back to chronological (oldest first)
                        older_messages.append(
                            OutChatMessage(
                                room=room,
                                user=uname or "",
                                message=msg_row.content,
                                message_id=msg_row.id,
                                ts=msg_row.created_at,
                            ).model_dump(mode="json")
                        )
                more = len(rows) == HISTORY_LIMIT
                await ws.send_json({"type": "history_more", "room": room, "messages": older_messages, "more": more})
            elif mtype == "typing":
                room = msg.get("room")
                is_typing = bool(msg.get("isTyping"))
                if not (isinstance(room, str) and manager.in_room(ws, room)):
                    await ws.send_json({"type": "error", "message": "invalid typing"})
                    continue
                typing_payload = OutTypingMessage(room=room, user=user.username, isTyping=is_typing).model_dump(
                    mode="json"
                )
                # Broadcast to local sockets (sender & peers) immediately; Redis pubsub skips same server messages
                for peer in list(manager.rooms.get(room, [])):
                    try:
                        await peer.send_json(typing_payload)
                    except Exception:
                        logger.debug("typing send failure", exc_info=True)
                await manager.publish(room, typing_payload)
            elif mtype == "ping":
                await ws.send_json({"type": "pong", "ts": time.time()})
            else:
                await ws.send_json({"type": "error", "message": "unknown type"})
    except WebSocketDisconnect:
        logger.debug("ws disconnect user=%s", getattr(user, "username", "?"))
    finally:
        await manager.leave_all(ws)
        logger.debug("ws cleanup done user=%s", getattr(user, "username", "?"))
