#!/bin/sh
set -e

echo "[post-create] Install UV..."
if ! command -v uv >/dev/null 2>&1; then
  pip install --upgrade uv

echo "[post-create] Setting up backend virtual environment with uv..."
cd ./backend
if [ ! -d .venv ]; then
  uv venv
fi
source .venv/bin/activate
uv sync

# Run migrations (ignore errors if DB not up yet)
if command -v uv >/dev/null 2>&1; then
  echo "[post-create] Attempting alembic migration (may fail if postgres not ready)..."
  (uv run alembic upgrade head || echo "[post-create] Migration skipped")
fi

# Move to Root
cd ..

echo "[post-create] Installing frontend dependencies..."
cd ./frontend
if [ -f package.json ]; then
  yarn install --frozen-lockfile || yarn install
fi

# Move to Root
cd ..

echo "[post-create] Installing pre-commit..."
if ! command -v pre-commit >/dev/null 2>&1; then
  pip install pre-commit
fi

pre-commit install

echo "[post-create] Post-create steps complete."
