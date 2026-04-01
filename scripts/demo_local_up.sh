#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3.12}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found: $PYTHON_BIN"
  exit 1
fi

if ! "$PYTHON_BIN" -c "import django" >/dev/null 2>&1; then
  echo "Django is not installed in the current environment."
  echo "Run: pip install -r requirements.txt"
  exit 1
fi

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.dev}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT_DIR/db.sqlite3}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"

if command -v redis-cli >/dev/null 2>&1; then
  if ! redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
    echo "Starting local Redis..."
    redis-server --daemonize yes >/dev/null 2>&1 || true
    sleep 1
  fi
fi

echo "Applying migrations..."
"$PYTHON_BIN" manage.py migrate

echo "Loading demo data..."
"$PYTHON_BIN" manage.py seed_demo_data --reset

echo "Starting Celery worker..."
celery -A config.celery worker -l info >/tmp/janynda-celery.log 2>&1 &
CELERY_PID=$!

echo "Starting Celery Beat..."
celery -A config.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler >/tmp/janynda-celery-beat.log 2>&1 &
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
echo "Server: http://127.0.0.1:8000"
echo "Admin:  http://127.0.0.1:8000/admin/"
echo ""
echo "Celery logs:"
echo "  /tmp/janynda-celery.log"
echo "  /tmp/janynda-celery-beat.log"
echo ""

exec "$PYTHON_BIN" manage.py runserver 0.0.0.0:8000
