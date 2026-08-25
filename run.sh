#!/usr/bin/env bash
cd "$(dirname "$0")"; set -a; . ./.env; set +a
exec .venv/bin/uvicorn runvouch.server:app --host 127.0.0.1 --port 8787 --log-level warning
