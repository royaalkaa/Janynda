#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

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
    if docker compose exec -T web python manage.py check >/dev/null 2>&1; then
      return 0
    fi
    sleep "$sleep_seconds"
  done

  echo "Web container did not become ready in time."
  docker compose ps || true
  exit 1
}

ensure_docker_running "$@"

echo "Building and starting Docker services..."
docker compose up -d --build

echo "Waiting for Django container..."
wait_for_web

echo "Applying migrations..."
docker compose exec -T web python manage.py migrate

echo "Loading demo data..."
docker compose exec -T web python manage.py seed_demo_data --reset

echo ""
echo "Demo accounts:"
echo "  admin@janynda.local / demo12345"
echo "  observer@janynda.local / demo12345"
echo "  daughter@janynda.local / demo12345"
echo "  mother@janynda.local / demo12345"
echo "  father@janynda.local / demo12345"
echo ""
echo "App:   http://127.0.0.1:8000"
echo "Admin: http://127.0.0.1:8000/admin/"
echo ""
echo "Container status:"
docker compose ps
