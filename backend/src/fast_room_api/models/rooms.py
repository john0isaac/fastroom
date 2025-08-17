from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Room(BaseModel):
    id: int
    name: str
    is_private: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RoomCreate(BaseModel):
    name: str
    is_private: bool = False


class RoomUpdate(BaseModel):
    name: str | None = None
    is_private: bool | None = None


class RoomMember(BaseModel):
    user_id: int
    username: str
    is_moderator: bool
    is_banned: bool
    is_muted: bool
    joined_at: datetime


class Message(BaseModel):
    id: int
    user_id: int | None
    username: str | None
    content: str
    created_at: datetime


class MessageUpdate(BaseModel):
    content: str


class PresenceState(BaseModel):
    room_id: int
    room: str
    users: list[str]
    count: int


class RoomsPage(BaseModel):
    items: list[Room]
    total: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None = None


class RoomMembersPage(BaseModel):
    items: list[RoomMember]
    total: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None = None


class MessagesPage(BaseModel):
    items: list[Message]
    total: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None = None
