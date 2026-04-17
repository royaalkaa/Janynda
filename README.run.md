# Инструкция по запуску Janynda

## 1. Что нужно для запуска

Рекомендуемый вариант:

- Docker
- Docker Compose

Локальный запуск без Docker:

- Python 3.10-3.13
- Redis
- опционально PostgreSQL, либо SQLite для лёгкого локального старта

## 2. Самый быстрый запуск

Из корня проекта выполните:

```bash
bash scripts/up.sh
```

Что делает этот скрипт:

- выбирает Docker-режим, если установлен Docker Compose
- иначе переключается в локальный режим
- создаёт `.env` из `.env.example`, если файла ещё нет

## 3. Запуск через Docker

### Вариант A. Готовый demo-скрипт

```bash
bash scripts/up.sh docker
```

Скрипт:

- собирает контейнеры
- поднимает PostgreSQL, Redis, Django, Celery worker и Celery Beat
- применяет миграции
- загружает демо-данные

Приложение по умолчанию будет доступно по адресу:

- `http://127.0.0.1:8000`

Если порт `8000` занят, можно запустить на другом порту:

```bash
APP_PORT=8001 bash scripts/up.sh docker
```

Если вы запускаете проект на Fedora или другой системе с SELinux и для bind mount нужна перемаркировка:

```bash
DOCKER_BIND_MOUNT_SUFFIX=:z bash scripts/up.sh docker
```

### Вариант B. Ручной запуск через Docker Compose

Теперь в `docker-compose.yml` уже есть рабочие значения по умолчанию, поэтому проект может стартовать даже без заранее созданного `.env`.

```bash
docker compose up --build
```

В другом терминале:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Полезные команды:

```bash
docker compose ps
docker compose logs -f web
docker compose logs -f celery
docker compose logs -f celery-beat
docker compose down
```

## 4. Локальный запуск без Docker

### 4.1 Создать виртуальное окружение

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Если `python3.12` недоступен, используйте любую поддерживаемую версию от `3.10` до `3.13`.

### 4.2 Подготовить переменные окружения

```bash
cp .env.example .env
```

Для лёгкого локального запуска с SQLite:

```env
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://127.0.0.1:6379/0
```

Для PostgreSQL на localhost:

```env
DATABASE_URL=postgresql://janynda:janynda@localhost:5432/janynda
REDIS_URL=redis://127.0.0.1:6379/0
```

### 4.3 Запустить сервисы

Применить миграции:

```bash
python manage.py migrate
```

Создать администратора:

```bash
python manage.py createsuperuser
```

Запустить Django:

```bash
python manage.py runserver
```

Во втором терминале запустить Celery worker:

```bash
python -m celery -A config.celery worker -l info
```

В третьем терминале запустить Celery Beat:

```bash
python -m celery -A config.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## 5. Важные переменные окружения

Минимально важные переменные:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DATABASE_URL`
- `REDIS_URL`

Необязательные интеграции:

- `OPENWEATHER_API_KEY`
- `OPENAI_API_KEY`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`

Проект запускается и без внешних API-ключей, но погодное обогащение, AI-ответы и реальная отправка email будут ограничены или отключены.

## 6. Демо-аккаунты

При запуске demo-скриптов создаются следующие аккаунты:

- `admin@janynda.local / demo12345`
- `observer@janynda.local / demo12345`
- `daughter@janynda.local / demo12345`
- `mother@janynda.local / demo12345`
- `father@janynda.local / demo12345`

## 7. Что требует Celery

Основной интерфейс откроется и без фоновых процессов, но эти функции зависят от Celery и Celery Beat:

- генерация повторяющихся задач плана дня
- отправка напоминаний
- проверки отсутствия по геолокации
- проверки целей по wearable-данным

## 8. Полезные проверки

```bash
python manage.py check
python manage.py test -v 2
python manage.py check --settings=config.settings.prod
python manage.py makemigrations --check --dry-run --settings=config.settings.test
```
