from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Уведомления"

    def ready(self):
        from .local_scheduler import start_inprocess_scheduler_if_enabled

        start_inprocess_scheduler_if_enabled()
