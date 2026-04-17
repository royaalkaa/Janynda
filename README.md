# Janynda

Janynda is a Django-based family health tracker for monitoring relatives' metrics, surfacing alerts, and preparing the product foundation for weather-aware recommendations and AI assistance.

## Stack

- Django 5
- PostgreSQL
- Redis + Celery
- HTMX
- Bootstrap 5
- Chart.js
- OpenWeatherMap
- OpenAI API

## Apps

- `accounts` — auth, onboarding, magic link login
- `family` — family group and relative management
- `health` — metric records, thresholds, quick entry, history
- `weather` — cached weather and AQI
- `notifications` — notification center and settings
- `ai_assistant` — cached health comments
- `challenges` — family challenge models and list
- `dashboard` — landing page plus observer/subject dashboards

## Run With Docker

1. Copy `.env.example` to `.env` and set real API keys if needed.
2. Start services:

```bash
docker compose up --build
```

3. Run migrations in the container:

```bash
docker compose exec web python manage.py migrate
```

4. Create an admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

## Local Smoke Run

If PostgreSQL/Redis containers are not running, you can still validate the project with SQLite:

```bash
DATABASE_URL=sqlite:///db.sqlite3 python manage.py migrate
python manage.py runserver
```

## Current Product Scope

- Custom signup/login
- 4-step onboarding
- Observer dashboard for family monitoring
- Subject dashboard with HTMX quick entry
- Magic link flow for invited relatives
- Health history screen
- Notification center, weather page, and AI insight placeholder
