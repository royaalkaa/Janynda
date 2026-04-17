#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ensure_env_file() {
  if [[ -f "$ROOT_DIR/.env" || ! -f "$ROOT_DIR/.env.example" ]]; then
    return 0
  fi

  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "Created .env from .env.example"
}

pick_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
    return 0
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
    return 0
  fi

  echo "Docker Compose is not installed."
  exit 1
}

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed."
  exit 1
fi

ensure_docker_running() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi

  if command -v systemctl >/dev/null 2>&1; then
    if ! systemctl is-active docker >/dev/null 2>&1; then
      echo "Starting Docker service..."
      if [[ "${EUID}" -eq 0 ]]; then
        systemctl enable --now docker >/dev/null 2>&1 || true
      else
        sudo systemctl enable --now docker
      fi
    fi
  fi

  if docker info >/dev/null 2>&1; then
    return 0
  fi

  if [[ "${EUID}" -ne 0 && -z "${JANYNDA_UP_AS_ROOT:-}" ]]; then
    echo "Docker requires elevated access in this shell. Re-running via sudo..."
    exec sudo env JANYNDA_UP_AS_ROOT=1 bash "$0" "$@"
  fi

  docker info >/dev/null
}

wait_for_web() {
  local attempts=45
  local sleep_seconds=2

  for ((i=1; i<=attempts; i++)); do
    if "${COMPOSE_CMD[@]}" exec -T web python manage.py check >/dev/null 2>&1; then
      return 0
    fi
    sleep "$sleep_seconds"
  done

  echo "Web container did not become ready in time."
  "${COMPOSE_CMD[@]}" ps || true
  exit 1
}

pick_compose_cmd
ensure_env_file
ensure_docker_running "$@"

echo "Building and starting Docker services..."
"${COMPOSE_CMD[@]}" up -d --build

echo "Waiting for Django container..."
wait_for_web

echo "Applying migrations..."
"${COMPOSE_CMD[@]}" exec -T web python manage.py migrate

echo "Loading demo data..."
"${COMPOSE_CMD[@]}" exec -T web python manage.py seed_demo_data --reset

APP_PORT="${APP_PORT:-8000}"
APP_URL_HOST="${APP_URL_HOST:-127.0.0.1}"

echo ""
echo "Demo accounts:"
echo "  admin@janynda.local / demo12345"
echo "  observer@janynda.local / demo12345"
echo "  daughter@janynda.local / demo12345"
echo "  mother@janynda.local / demo12345"
echo "  father@janynda.local / demo12345"
echo ""
echo "App:   http://$APP_URL_HOST:$APP_PORT"
echo "Admin: http://$APP_URL_HOST:$APP_PORT/admin/"
echo ""
echo "Container status:"
"${COMPOSE_CMD[@]}" ps
