#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-auto}"

has_docker_compose() {
  docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1
}

case "$MODE" in
  docker)
    exec bash "$ROOT_DIR/scripts/docker_demo_up.sh"
    ;;
  local)
    exec bash "$ROOT_DIR/scripts/demo_local_up.sh"
    ;;
  auto)
    if command -v docker >/dev/null 2>&1 && has_docker_compose; then
      echo "Starting in Docker mode..."
      exec bash "$ROOT_DIR/scripts/docker_demo_up.sh"
    fi
    echo "Docker or Docker Compose not found. Falling back to local mode..."
    exec bash "$ROOT_DIR/scripts/demo_local_up.sh"
    ;;
  *)
    echo "Usage: bash scripts/up.sh [auto|docker|local]"
    exit 1
    ;;
esac
