# Contribution

Thanks for your interest in improving FastRoom. This guide explains how to set up a local environment, propose changes, and submit high‑quality pull requests.

How to [contribute to the project](https://docs.github.com/en/get-started/quickstart/contributing-to-projects)?

## Table of Contents

- [Contribution](#contribution)
  - [Table of Contents](#table-of-contents)
  - [1. Workflow Overview](#1-workflow-overview)
  - [2. Environment Setup](#2-environment-setup)
  - [3. Backend Changes](#3-backend-changes)
  - [4. Frontend Changes](#4-frontend-changes)
  - [5. Tests \& Quality Gates](#5-tests--quality-gates)
  - [6. Documentation \& Changelogs](#6-documentation--changelogs)
  - [7. Pull Request Checklist](#7-pull-request-checklist)
  - [8. Issue Types](#8-issue-types)
  - [9. Security \& Responsible Disclosure](#9-security--responsible-disclosure)
  - [Code of Conduct](#code-of-conduct)

---

## 1. Workflow Overview

1. Open / pick an issue (or create one) describing the proposed change.
2. Create a feature branch off `main`.
3. Make changes with tests + docs.
4. Run quality gates (lint, type check, tests, format, build).
5. Open a PR referencing the issue; fill checklist.
6. Address review comments; squash (optional) & merge.

## 2. Environment Setup

Backend:

```bash
cd backend
uv venv
source .venv/bin/activate
uv sync
uv run alembic upgrade head
uv run src/fast_room_api/api/main.py
```

Frontend:

```bash
cd frontend
yarn
yarn dev
```

Optional: `docker compose up --build` to run full stack with Postgres + Redis.

## 3. Backend Changes

- Add / modify models: update SQLAlchemy ORM + Pydantic schemas.
- Generate a migration:

  ```bash
  uv run alembic revision --autogenerate -m "describe change"
  uv run alembic upgrade head
  ```

- New endpoints: place in an existing router or create a new one under `api/routers/`.
- Authentication / token logic changes: update tests under `tests/unit` or integration tests (e.g. `test_refresh_flow.py`).
- WebSocket protocol changes: document in `backend/README.md` (Protocol section) and update frontend helpers if needed.
- Performance-sensitive code: add brief rationale in comments.

## 4. Frontend Changes

- Run `yarn generate:client` if backend OpenAPI changed.
- Keep generated client out of version control modifications (do not manually edit).
- Shared logic: prefer composables under `src/utils` or `src/composables`.
- State mutations: centralize in Pinia stores where possible.
- Large UI changes: add screenshots (PR description) if visual.

## 5. Tests & Quality Gates

Run before pushing:

```bash
# Backend
cd backend
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy .

# Frontend (when tests introduced)
cd ../frontend
yarn lint
```

Add tests for:

- New endpoints (success + failure path)
- Schema / validation changes
- Token / auth logic
- WebSocket message handling (where feasible)

## 6. Documentation & Changelogs

- Update root `README.md` if you add high‑level capabilities.
- Update `backend/README.md` for new REST or WS message types.
- Update `frontend/README.md` if build/config/scripts change.
- If introducing breaking changes (API or message envelope) call them out clearly in PR.

## 7. Pull Request Checklist

- [ ] Linked issue (or rationale explained)
- [ ] Scope limited / focused
- [ ] Tests added or updated
- [ ] Lint + type checks pass
- [ ] Docs updated (root / backend / frontend as needed)
- [ ] No unnecessary console / debug output
- [ ] Migrations included (if DB schema changed)
- [ ] Generated client refreshed (if OpenAPI changed)

## 8. Issue Types

| Type | Use For |
|------|---------|
| feat | New functionality / endpoints / WS types |
| fix | Bug fixes |
| chore | Tooling, build, dependency bumps |
| docs | Documentation-only changes |
| refactor | Internal restructuring without feature change |
| perf | Performance improvements |
| test | Adding or improving tests |

## 9. Security & Responsible Disclosure

Do not open public issues for vulnerabilities. Instead, contact the maintainer privately (email listed in `pyproject.toml`). Provide steps to reproduce, impact assessment, and suggested mitigations. A disclosure and fix plan will be coordinated before public release.

## Code of Conduct

All contributors are expected to uphold a respectful, inclusive environment. [Code Of Conduct](./CODE_OF_CONDUCT.md).

---
Maintained by [John Aziz](https://github.com/john0isaac).
