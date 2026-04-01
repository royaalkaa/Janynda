from .base import *  # noqa

DEBUG = True

INSTALLED_APPS += ["debug_toolbar"]

MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE

INTERNAL_IPS = ["127.0.0.1"]

# Консольный email в разработке
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Подробные логи Celery
CELERY_TASK_ALWAYS_EAGER = False
