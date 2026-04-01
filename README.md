# Janynda

Janynda is a Django family care app for monitoring elderly relatives: daily plans, medication routines, location sharing, helpful places, wearable summaries, notifications, and voice-assisted actions.

## Stack

- Python 3.12
- Django 5.1
- PostgreSQL
- Redis
- Celery + django-celery-beat
- HTMX
- Bootstrap 5
- Chart.js
- OpenWeatherMap API
- OpenAI API
- Browser Speech API
- Yandex Maps API

## Apps

- `accounts` — auth, onboarding, magic links
- `care` — daily plan, places, location, safe zones, wearables
- `family` — observer/subject relationships
- `health` — metrics, thresholds, history, quick entry
- `weather` — weather and AQI cache
- `notifications` — notification center and settings
- `ai_assistant` — AI comments and voice command flows
- `challenges` — family challenges
- `dashboard` — landing page and dashboards

## Current Scope

- Daily planner with create/edit/delete/history
- Recurring tasks and task reminders
- Observer access to manage an elderly relative's plan
- Useful places catalog with active longevity centers, clinics, pharmacies, parks, grocery, transport, favorites, routes, and map
- Location page with current point, period history, safe zones, SOS, and zone/absence alerts
- Voice assistant with browser voice input, TTS replies, command confirmation, cancellation, and actions for medication/doctor/metrics
- Wearable device registry, daily summaries, weekly/monthly analytics, charts, norms, and alerts
- Notification center
- Weather and AI insight layer

## Environment

Copy the example file and fill in real values where needed:

```bash
cp .env.example .env
```

Important variables:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DATABASE_URL`
- `REDIS_URL`
- `OPENWEATHER_API_KEY`
- `OPENAI_API_KEY`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`

Default `.env.example` is already configured for Docker Compose:

- PostgreSQL at `db:5432`
- Redis at `redis:6379`

If you run locally without Docker, change these two values:

```env
DATABASE_URL=postgresql://janynda:janynda@localhost:5432/janynda
REDIS_URL=redis://localhost:6379/0
```

Or use SQLite for a lightweight local run:

```env
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379/0
```

## Run With Docker

Run `docker compose` only from the project root:

```bash
cd /home/royalka/Документы/GitHub/Janynda
```

### Fedora / Linux Prerequisites

If you see this error:

```bash
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

then the issue is not the project itself. It means:

- Docker daemon is not running
- or your user is not allowed to access `/var/run/docker.sock`

Fix it once:

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

Then verify:

```bash
systemctl is-active docker
docker ps
docker compose version
```

Expected result:

- `systemctl is-active docker` returns `active`
- `docker ps` works without `permission denied`

If you do not want to re-login right now, you can use a temporary fallback:

```bash
sudo docker compose up --build
```

But the proper long-term fix is adding your user to the `docker` group and reopening the shell session.

If Docker is not installed yet on Fedora, install Docker Engine and the Compose plugin first, then repeat the steps above.

1. Create env file:

```bash
cp .env.example .env
```

2. Build and start all services:

```bash
docker compose up --build
```

This starts:

- `web` — Django dev server on `http://127.0.0.1:8000`
- `db` — PostgreSQL 16
- `redis` — Redis 7
- `celery` — background worker
- `celery-beat` — scheduled tasks

3. Apply migrations:

```bash
docker compose exec web python manage.py migrate
```

4. Create admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

5. Open the project:

- App: `http://127.0.0.1:8000`
- Admin: `http://127.0.0.1:8000/admin/`

Useful Docker commands:

```bash
docker compose logs -f web
docker compose logs -f celery
docker compose logs -f celery-beat
docker compose ps
docker compose down
```

If you changed Python dependencies or Docker base layers:

```bash
docker compose build --no-cache
docker compose up
```

## Run Locally Without Docker

### 1. Install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Prepare services

You need either:

- local PostgreSQL + Redis
- or SQLite + Redis

Create `.env`:

```bash
cp .env.example .env
```

For PostgreSQL on localhost:

```env
DATABASE_URL=postgresql://janynda:janynda@localhost:5432/janynda
REDIS_URL=redis://localhost:6379/0
```

For SQLite:

```env
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379/0
```

### 3. Apply migrations

```bash
python manage.py migrate
```

### 4. Create admin user

```bash
python manage.py createsuperuser
```

### 5. Start Django

```bash
python manage.py runserver
```

### 6. Start Celery worker

In a second terminal:

```bash
celery -A config.celery worker -l info
```

### 7. Start Celery Beat

In a third terminal:

```bash
celery -A config.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## What Works Without Celery

The app will open and most pages will render without worker processes, but these features rely on Celery/Beat to work properly:

- recurring task generation
- task reminder delivery
- zone/absence checks
- wearable goal alerts

## Tests

Tests use isolated settings automatically through `manage.py test`.

Run all tests:

```bash
python manage.py test -v 2
```

Useful checks:

```bash
python manage.py check
python manage.py check --settings=config.settings.prod
python manage.py makemigrations --check --dry-run --settings=config.settings.test
```

## Developer Notes

- `python manage.py test` uses `config.settings.test`
- all other `manage.py` commands default to `config.settings.dev`
- `config.celery` defaults to `config.settings.prod`, but Docker Compose overrides it to `config.settings.dev`
- browser voice input/output depends on browser support for Speech Recognition and Speech Synthesis
- maps are rendered in the browser through Yandex Maps API
- background alerts and reminders require Redis + Celery + Beat
- for Docker on Fedora, make sure `docker` service is active and your user is in the `docker` group

## Main Routes

- `/` — landing
- `/accounts/login/` — login
- `/dashboard/` — dashboards
- `/care/plan/` — daily plan
- `/care/location/` — geolocation
- `/care/places/` — useful places
- `/care/wearables/` — wearable devices
- `/ai/` — voice assistant
- `/notifications/` — notifications
- `/admin/` — Django admin
