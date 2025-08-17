# Backend (FastAPI + Async SQLAlchemy + Redis)

Core realtime + REST API powering FastRoom. Provides auth (JWT + refresh tokens), room & membership CRUD, chat persistence, and presence via WebSocket heartbeat keys in Redis.

## Features

- FastAPI app (async) served by Uvicorn
- JWT access + rotating refresh tokens (hashed in DB)
- Rooms CRUD, membership & moderation (mute / ban / mod toggle)
- Chat message storage + pagination + edit/delete with WebSocket fanout
- Presence via Redis heartbeat keys (per connection) with diff + state messages
- Typing indicators, history pagination over WS
- OpenAPI schema for client generation
- Structured modular routers (`auth`, `users`, `rooms`, `ws`)

## Development

1. Install uv (if needed): <https://docs.astral.sh/uv/>
2. Create virtual env & install dependencies:

```bash
cd backend
uv venv
source .venv/bin/activate
uv sync
```

1. Run the API (sqlite / local):

```bash
uv run src/fast_room_api/api/main.py
```

Or with Docker Compose (Postgres + Redis): from repo root:

```bash
docker compose up api
```

Hot reload (local, no Docker) is managed by `uvicorn --reload` if you prefer:

```bash
uv run uvicorn fast_room_api.api.main:app --reload --port 8000
```

## Environment Variables (Settings)

Defined via pydantic-settings in `models/config.py` (also reads `.env`).

| Variable | Default | Description |
|----------|---------|-------------|
| `FASTROOM_SECRET` | `dev-secret-change-me` | HMAC secret for JWT signing |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5433/fastroom` | Async DB URL |
| `REDIS_URL` / `redis_url` | `redis://redis:6379/0` | Redis connection string |
| `ACCESS_TOKEN_EXP_SECONDS` | 28800 (8h) | Access token TTL |
| `REFRESH_TOKEN_EXP_SECONDS` | 1209600 (14d) | Refresh token TTL |
| `LOG_LEVEL` | INFO | Logging level (INFO/DEBUG/etc.) |
| `DEBUG` | true | Influences certain dev behaviours (parsing logic in config) |
| `FASTROOM_TEST` | false | Test mode tweaks token/date handling |
| `WS_HEARTBEAT_INTERVAL` | 25 | Heartbeat ping interval (sec) |
| `WS_HEARTBEAT_TTL_MS` | interval+5s | TTL for presence heartbeat keys |
| `SERVER_ID` | random 6 hex | Process id tag for WS fanout filtering |

Override in `.env` (not committed) or environment.

## REST API Overview

Auth (router: `auth.py`):

- `POST /register` – create user (body: username, password, email?)
- `POST /token` – OAuth2 password form login -> `{ access_token, refresh_token, token_type }`
- `POST /refresh` – rotate using `refresh_token` -> new pair
- `POST /logout` – revoke given refresh token

Users (router: `users.py`):

- `GET /users/me` – profile of current user
- `GET /users?limit&offset&order` – list users
- `GET /users/{username}` – get specific user

Rooms (router: `rooms.py` prefix `/rooms`):

- `GET /rooms/` – list (pagination)
- `POST /rooms/` – create
- `GET /rooms/{room_id}` – fetch by id
- `PATCH /rooms/{room_id}` – update (moderator)
- `DELETE /rooms/{room_id}` – delete (moderator)
- `GET /rooms/{room_id}/members` – list members
- `POST /rooms/{room_id}/join` – join
- `DELETE /rooms/{room_id}/leave` – leave
- `GET /rooms/{room_id}/messages` – list messages (pagination)
- `PATCH /rooms/{room_id}/messages/{message_id}` – edit (owner/mod)
- `DELETE /rooms/{room_id}/messages/{message_id}` – delete (owner/mod)
- `GET /rooms/by-name/{room_name}` – fetch by name
- `GET /rooms/{room_id}/presence` – current presence snapshot
- Moderation toggles:
  - `POST /rooms/{room_id}/members/{user_id}/moderator`
  - `POST /rooms/{room_id}/members/{user_id}/ban`
  - `POST /rooms/{room_id}/members/{user_id}/mute`

OpenAPI docs at `/docs` and `/openapi.json`.

## WebSocket Protocol (`/ws`)

Messages are JSON objects with a `type` field.

Inbound types:

- `join` `{ "type": "join", "room": "general" }`
- `leave` `{ "type": "leave", "room": "general" }`
- `chat` `{ "type": "chat", "room": "general", "message": "hi" }`
- `history_more` `{ "type": "history_more", "room": "general", "before_id": 123 }`
- `typing` `{ "type": "typing", "room": "general", "isTyping": true }`
- `ping` `{ "type": "ping" }`

Outbound types (non-exhaustive):

- `system` – system lines, includes initial connection banner
- `joined` – ack for a join
- `presence_state` – full list after join `{ users: [...] }`
- `presence_diff` – `{ join: [..] }` or `{ leave: [..] }`
- `chat` – broadcast chat message `{ room, user, message, message_id, ts }`
- `history` – initial backlog on join `{ messages: [...] }`
- `history_more` – older messages page `{ messages: [...], more: bool }`
- `typing` – typing indicator
- `pong` – response to ping
- `error` – validation / auth errors

Presence Implementation:

- Each active (websocket, room) pair sets a heartbeat key `presence:hb:{room}:{username}:{connId}` with TTL refreshed every `WS_HEARTBEAT_INTERVAL` seconds. User presence list is derived by scanning keys; first join triggers a `presence_diff` join; disconnect triggers diff leave (immediate due to proactive deletion of key).

Fanout & Scaling:

- Local broadcast + Redis pub/sub channel per room (`room:{room_name}`) with `srv` marker to suppress echo.
- Designed to scale horizontally by sharing Redis.

History:

- On join: last 50 messages (chronological).
- `history_more` paginates backwards in time by `before_id`.

Typing:

- Sent to all peers (including sender) to allow UI edge cases to reconcile quickly.

## Token & Refresh Flow

1. `POST /token` (password form) -> pair
2. Client uses `access_token` for Authorization: `Bearer <token>`
3. When near expiry, call `POST /refresh` with body `{ "refresh_token": "..." }`
4. On success old refresh hash is revoked and new pair returned
5. `POST /logout` allows explicit revocation

Refresh tokens are stored hashed (SHA-256) with expiry & revoked flag. Expired or revoked tokens yield 401.

## Database & Migrations

Models: users, rooms, room_members, messages, refresh_tokens.

Run migrations:

```bash
uv run alembic upgrade head
```

Create new migration after model changes:

```bash
uv run alembic revision --autogenerate -m "add foo"
uv run alembic upgrade head
```

Rollback one step:

```bash
uv run alembic downgrade -1
```

During container startup you can invoke:

```bash
uv run alembic upgrade head && uv run fast_room_api/api/main.py
```

## Testing

Tests under `src/tests` (unit + integration). Run:

```bash
uv run pytest -q
```

`FASTROOM_TEST=1` may be set to tweak datetime comparisons.

## Logging

`settings.log_level` determines base log level. WebSocket and room events use structured messages with categories: `fast_room_api.auth`, `fast_room_api.rooms`, `fast_room_api.websocket`, `fast_room_api.users`.

## Security Notes

- Replace `FASTROOM_SECRET` in production
- Consider rotating secrets + invalidating tokens via `jti` blocklist for high security contexts.
