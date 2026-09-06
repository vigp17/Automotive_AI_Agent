#!/usr/bin/env bash
#
# Idempotent Cloud Agent bootstrap for the AI Cabin Copilot.
# Safe to re-run: reuses the existing venv and only refreshes dependencies.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# The base image ships Python 3.12 but not the venv/ensurepip module, which the
# README-documented `python3 -m venv .venv` flow requires.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12-venv
fi

# Backend: pinned deps in an isolated venv (matches the README quickstart).
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt
# ruff is the lint tool CI runs; same pinned version, one source.
.venv/bin/pip install -r backend/requirements-dev.txt

# Frontend: clean, lockfile-exact install (matches CI and the Dockerfile).
(cd frontend && npm ci --no-fund --no-audit)
