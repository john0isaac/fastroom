from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TypingMessage(BaseModel):
    type: Literal["typing"]
    room: str
    isTyping: bool


class JoinMessage(BaseModel):
    type: Literal["join"]
    room: str


class LeaveMessage(BaseModel):
    type: Literal["leave"]
    room: str


class ChatMessage(BaseModel):
    type: Literal["chat"]
    room: str
    message: str


class Ping(BaseModel):
    type: Literal["ping"]


class Pong(BaseModel):
    type: Literal["pong"]


IncomingMessage = JoinMessage | LeaveMessage | ChatMessage | TypingMessage | Ping


class OutTypingMessage(BaseModel):
    type: Literal["typing"] = "typing"
    room: str
    user: str
    isTyping: bool
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutPresenceState(BaseModel):
    type: Literal["presence_state"] = "presence_state"
    room: str
    users: list[str]
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutPresenceDiff(BaseModel):
    type: Literal["presence_diff"] = "presence_diff"
    room: str
    join: list[str] = []
    leave: list[str] = []
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutChatMessage(BaseModel):
    type: Literal["chat"] = "chat"
    room: str
    user: str
    message: str
    message_id: int | None = None
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutSystemMessage(BaseModel):
    type: Literal["system"] = "system"
    room: str
    message: str
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutMessageUpdated(BaseModel):
    type: Literal["message_updated"] = "message_updated"
    room: str
    message_id: int
    content: str
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutMessageDeleted(BaseModel):
    type: Literal["message_deleted"] = "message_deleted"
    room: str
    message_id: int
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutMemberUpdate(BaseModel):
    type: Literal["member_update"] = "member_update"
    room: str
    user_id: int
    username: str
    is_moderator: bool
    is_banned: bool
    is_muted: bool
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Envelope(BaseModel):
    version: int
    type: str
    topic: str | None = None
    msgId: str | None = None
    payload: dict | None = None
