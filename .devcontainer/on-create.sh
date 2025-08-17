#!/usr/bin/env bash
set -euo pipefail

echo "[on-create] Updating apt and installing base packages..."
apt-get update -y && apt-get install -y --no-install-recommends curl git build-essential ca-certificates && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager)
if ! command -v uv >/dev/null 2>&1; then
  echo "[on-create] Installing uv..."
  pip install --no-cache-dir -U pip
  pip install --no-cache-dir uv
fi

echo "[on-create] Done."
