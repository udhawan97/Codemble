#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
demo_port="${CODEMBLE_DEMO_PORT:-8876}"
demo_state="$(mktemp -d /tmp/codemble-demo-state.XXXXXX)"
demo_frames="$(mktemp -d /tmp/codemble-demo-frames.XXXXXX)"
server_pid=""

cleanup() {
  if [[ -n "${server_pid}" ]]; then
    kill "${server_pid}" 2>/dev/null || true
  fi
  if [[ "${demo_state}" == /tmp/codemble-demo-state.* ]]; then
    rm -rf "${demo_state}"
  fi
  if [[ "${demo_frames}" == /tmp/codemble-demo-frames.* ]]; then
    rm -rf "${demo_frames}"
  fi
}
trap cleanup EXIT INT TERM

for command_name in node npm ffmpeg curl codemble; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "record_demo: missing required command: ${command_name}" >&2
    exit 2
  fi
done

cd "${repo_root}/web"
npm run build

cd "${repo_root}"
CODEMBLE_DATA_DIR="${demo_state}" codemble tests/fixtures/sampleproj \
  --no-open --port "${demo_port}" &
server_pid=$!

for _attempt in {1..40}; do
  if curl --fail --silent "http://127.0.0.1:${demo_port}/api/graph" >/dev/null; then
    break
  fi
  sleep 0.1
done
if ! curl --fail --silent "http://127.0.0.1:${demo_port}/api/graph" >/dev/null; then
  echo "record_demo: Codemble did not start on port ${demo_port}" >&2
  exit 2
fi

cd "${repo_root}/web"
CODEMBLE_DEMO_URL="http://127.0.0.1:${demo_port}" \
CODEMBLE_DEMO_FRAMES="${demo_frames}" \
  node scripts/record_demo.mjs

mkdir -p "${repo_root}/assets"
ffmpeg -hide_banner -loglevel error -y \
  -framerate 5 -i "${demo_frames}/frame-%03d.png" \
  -vf "fps=10,scale=960:-1:flags=lanczos,palettegen=max_colors=128" \
  "${demo_frames}/palette.png"
ffmpeg -hide_banner -loglevel error -y \
  -framerate 5 -i "${demo_frames}/frame-%03d.png" \
  -i "${demo_frames}/palette.png" \
  -lavfi "fps=10,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer" \
  "${repo_root}/assets/demo.gif"

echo "Wrote ${repo_root}/assets/demo.gif"
