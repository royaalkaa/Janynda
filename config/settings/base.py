from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="change-me-in-production")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "testserver"])

# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_htmx",
    "django_celery_beat",
    "django_extensions",
    "rosetta",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.family",
    "apps.health",
    "apps.weather",
    "apps.notifications",
    "apps.ai_assistant",
    "apps.care",
    "apps.challenges",
    "apps.dashboard",
    "apps.payment",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

SITE_ID = 1

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.notifications.context_processors.unread_notifications_count",
                "apps.weather.context_processors.current_weather",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3")
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
USE_REDIS = env.bool("USE_REDIS", default=False)
REDIS_URL = env("REDIS_URL", default="")

if USE_REDIS and REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "janynda",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "janynda-local-cache",
        }
    }

SESSION_ENGINE = "django.contrib.sessions.backends.db"

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL",
    default=REDIS_URL if USE_REDIS and REDIS_URL else "memory://",
)
CELERY_RESULT_BACKEND = env(
    "CELERY_RESULT_BACKEND",
    default=REDIS_URL if USE_REDIS and REDIS_URL else "cache+memory://",
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Almaty"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=not (USE_REDIS and REDIS_URL))
CELERY_TASK_EAGER_PROPAGATES = env.bool("CELERY_TASK_EAGER_PROPAGATES", default=True)
JANYNDA_INPROCESS_SCHEDULER_ENABLED = env.bool("JANYNDA_INPROCESS_SCHEDULER_ENABLED", default=True)
JANYNDA_INPROCESS_SCHEDULER_INTERVAL_SECONDS = env.int(
    "JANYNDA_INPROCESS_SCHEDULER_INTERVAL_SECONDS",
    default=30,
)

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Janynda <noreply@janynda.kz>")

# ---------------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("ru", "Русский"),
    ("kk", "Қазақша"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# Kaspi payment settings (override in .env)
KASPI_PHONE = env("KASPI_PHONE", default="+7 777 000 00 00")
KASPI_NAME  = env("KASPI_NAME",  default="Janynda")
KASPI_URL   = env("KASPI_URL",   default="https://kaspi.kz/pay/Janynda")

# ---------------------------------------------------------------------------
# Crispy Forms
# ---------------------------------------------------------------------------
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ---------------------------------------------------------------------------
# Third-party API keys
# ---------------------------------------------------------------------------
OPENWEATHER_API_KEY = env("OPENWEATHER_API_KEY", default="")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")

# ---------------------------------------------------------------------------
# App settings
# ---------------------------------------------------------------------------
MAGIC_LINK_TTL_DAYS = 7
WEATHER_CACHE_TTL_SECONDS = 1800  # 30 минут
AI_COMMENT_CACHE_TTL_SECONDS = 86400  # 24 часа
ALERT_CHECK_INTERVAL_MINUTES = 5

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
