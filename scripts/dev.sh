#!/usr/bin/env bash
set -euo pipefail

project_path="${1:-.}"

codemble "${project_path}" --no-open --port 8000 &
server_pid=$!
trap 'kill "${server_pid}" 2>/dev/null || true' EXIT INT TERM

cd web
npm run dev -- --host 127.0.0.1 --port 5173
