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

pick_python_bin() {
  local candidates=()
  local candidate
  local version

  if [[ -n "${PYTHON_BIN:-}" ]]; then
    candidates+=("$PYTHON_BIN")
  fi

  candidates+=(python3.12 python3.13 python3.11 python3.10 python3 python)

  for candidate in "${candidates[@]}"; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi

    version="$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" || continue
    case "$version" in
      3.10|3.11|3.12|3.13)
        PYTHON_BIN="$candidate"
        return 0
        ;;
    esac
  done

  echo "Supported Python was not found. Use Python 3.10-3.13."
  exit 1
}

pick_python_bin
ensure_env_file

if ! "$PYTHON_BIN" -c "import django, celery" >/dev/null 2>&1; then
  echo "Project dependencies are not installed for $PYTHON_BIN."
  echo "Run: $PYTHON_BIN -m pip install -r requirements.txt"
  exit 1
fi

APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
APP_URL_HOST="${APP_URL_HOST:-127.0.0.1}"

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.dev}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT_DIR/db.sqlite3}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"

if command -v redis-cli >/dev/null 2>&1; then
  if ! redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
    if ! command -v redis-server >/dev/null 2>&1; then
      echo "Redis is not reachable at $REDIS_URL and redis-server is not installed."
      exit 1
    fi
    echo "Starting local Redis..."
    redis-server --daemonize yes >/dev/null 2>&1
    sleep 1
  fi
fi

echo "Applying migrations..."
"$PYTHON_BIN" manage.py migrate

echo "Loading demo data..."
"$PYTHON_BIN" manage.py seed_demo_data --reset

echo "Starting Celery worker..."
"$PYTHON_BIN" -m celery -A config.celery worker -l info >/tmp/janynda-celery.log 2>&1 &
CELERY_PID=$!

echo "Starting Celery Beat..."
"$PYTHON_BIN" -m celery -A config.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler >/tmp/janynda-celery-beat.log 2>&1 &
BEAT_PID=$!

cleanup() {
  kill "$CELERY_PID" "$BEAT_PID" >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

echo ""
echo "Demo accounts:"
echo "  admin@janynda.local / demo12345"
echo "  observer@janynda.local / demo12345"
echo "  daughter@janynda.local / demo12345"
echo "  mother@janynda.local / demo12345"
echo "  father@janynda.local / demo12345"
echo ""
echo "Server: http://$APP_URL_HOST:$APP_PORT"
echo "Admin:  http://$APP_URL_HOST:$APP_PORT/admin/"
echo ""
echo "Celery logs:"
echo "  /tmp/janynda-celery.log"
echo "  /tmp/janynda-celery-beat.log"
echo ""

exec "$PYTHON_BIN" manage.py runserver "$APP_HOST:$APP_PORT"
