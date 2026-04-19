from .base import *  # noqa

DEBUG = True

if env.bool("ENABLE_DEBUG_TOOLBAR", default=False):
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
    INTERNAL_IPS = ["127.0.0.1"]

# Консольный email в разработке
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# В локальном режиме задачи выполняются без отдельного Celery/Redis процесса.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)
