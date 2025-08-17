# Frontend (Vue 3 + Vite + Pinia)

SPA for the FastRoom realtime chat / rooms system.

## Stack

- Framework: Vue 3 (SFC + `<script setup>`)
- State: Pinia
- Router: vue-router 4
- Build: Vite
- API Client: Generated from backend OpenAPI (`@hey-api/openapi-ts` + axios)
- Lint/Format: ESLint (flat config) + Prettier

## Project Structure

```text
frontend/
├── Dockerfile.web              # Multi-stage build -> nginx
├── index.html                  # Vite entry HTML
├── vite.config.ts              # Dev server + proxy config
├── package.json                # Scripts & deps
├── tsconfig.json               # TS compiler options
├── .env.development            # Local dev env vars (NOT committed for prod)
├── src/
│   ├── main.ts                 # App bootstrap
│   ├── router.ts               # Route definitions
│   ├── App.vue                 # Root component
│   ├── pages/                  # Route-level views (Login, Rooms, Profile...)
│   ├── components/             # Reusable UI (ChatRoom, etc.)
│   ├── stores/                 # Pinia stores (auth.ts)
│   ├── utils/                  # WebSocket helpers (wsClient, useAuthedWSClient)
│   ├── plugins/                # App plugin setup (auth client)
│   └── generated/openapiclient # AUTO-GENERATED OpenAPI client (do not edit)
└── public/                     # Static assets served as-is
```

## Environment Variables

Defined in `.env.development` (auto-loaded by Vite):

| Name          | Purpose                                        | Default                  |
| ------------- | ---------------------------------------------- | ------------------------ |
| `VITE_WS_URL` | Base WebSocket endpoint used by custom clients | `ws://localhost:8000/ws` |

Add production overrides via deployment platform env or a separate `.env.production` (not committed). Any variable prefixed with `VITE_` is exposed to the client bundle.

## Scripts

| Script                 | Description                                       |
| ---------------------- | ------------------------------------------------- |
| `yarn dev`             | Start Vite dev server with proxy + HMR            |
| `yarn build`           | Production build (`dist/`)                        |
| `yarn preview`         | Preview built assets locally                      |
| `yarn generate:client` | Regenerate OpenAPI TS client from running backend |
| `yarn lint`            | Run ESLint (no fixes)                             |
| `yarn lint:fix`        | ESLint with fixes                                 |
| `yarn format`          | Prettier write                                    |
| `yarn format:check`    | Prettier check                                    |

## Development

1. Node version

```bash
nvm use # uses .nvmrc (22.x)
```

1. Install deps & start:

```bash
yarn
yarn dev
```

1. Backend should run at `http://127.0.0.1:8000` (or adjust proxy in `vite.config.ts`).

## API Client Generation

The folder `src/generated/openapiclient` is auto-generated and ignored by Prettier. To update after backend schema changes:

```bash
yarn generate:client
```

Requirements:

- Backend server running & serving `/openapi.json` (FastAPI default)
- Network reachable (uses `http://127.0.0.1:8000/openapi.json`)

Do not manually edit generated files; custom wrappers can live outside.

## Authentication Flow (High-Level)

1. User submits credentials via REST (login endpoint on backend).
2. Backend sets HttpOnly auth cookie (JWT) + returns user data.
3. `stores/auth.ts` keeps reactive auth state & exposes helpers.
4. API client requests automatically include credentials (axios config) if needed.
5. WebSocket connection uses the same cookie (browser attaches automatically) OR explicit token header/query (future enhancement).

## WebSocket Helpers

`utils/wsClient.ts` & `utils/useAuthedWSClient.ts` encapsulate:

- Connection lifecycle & reconnection strategy (backoff can be extended)
- Message send helper
- Hook for authenticated context

Planned (see backend README outline): a unified message envelope with `type`, `topic`, `msgId`, and `payload`.

### Example Usage

```ts
import { useAuthedWSClient } from '@/utils/useAuthedWSClient';

const { socket, sendJson, status } = useAuthedWSClient();

sendJson({ type: 'join', topic: 'room:123', payload: {} });
```

## Linting & Formatting

ESLint flat config (`eslint.config.cjs`) + Prettier. Auto-format via editor or run:

```bash
yarn lint:fix && yarn format
```

CI / pre-commit not yet wired on frontend (backend uses pre-commit). Could add a Husky hook later.

## Docker Build

Multi-stage Dockerfile:

1. Install deps & build (`node:22-alpine`)
2. Copy built `dist/` into `nginx:alpine`

To build image alone:

```bash
docker build -t fastroom-web .
```

Or via compose (from repo root):

```bash
docker compose up --build web
```

## Proxy Configuration

`vite.config.ts` proxies:

- `/api` -> `http://localhost:8000`
- `/ws` -> `ws://localhost:8000` (WebSocket upgrade)

Adjust if backend host/port changes (e.g. container networking).

## Troubleshooting

| Issue              | Cause                                | Fix                                                      |
| ------------------ | ------------------------------------ | -------------------------------------------------------- |
| 404 on API calls   | Missing `/api` prefix mismatch       | Ensure frontend targets same base path as backend routes |
| CORS errors        | Backend CORS not allowing dev origin | Add `http://localhost:5173` to backend CORS config       |
| WS fails (401)     | Cookie not set / auth required       | Verify login flow & cookie flags (Secure/SameSite)       |
| Client gen empty   | Backend not running                  | Start backend before `yarn generate:client`              |
| Wrong Node version | Global Node incompatible             | `nvm use` or install Node 22.x                           |
