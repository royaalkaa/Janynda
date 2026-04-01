from django.db import models
from django.utils import timezone
from datetime import time


class Notification(models.Model):
    """Уведомление для пользователя."""

    class Severity(models.TextChoices):
        INFO = "info", "Информация"
        WARNING = "warning", "Предупреждение"
        CRITICAL = "critical", "Критично"

    class Category(models.TextChoices):
        HEALTH_ALERT = "health_alert", "Показатель здоровья"
        WEATHER = "weather", "Погода"
        ENTRY_REMINDER = "entry_reminder", "Напоминание о вводе"
        CHALLENGE = "challenge", "Челлендж"
        AI_TIP = "ai_tip", "AI-совет"
        SYSTEM = "system", "Система"

    recipient = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.SYSTEM)

    # Связь с субъектом который вызвал уведомление (опционально)
    related_subject = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_notifications",
    )
    related_metric_id = models.PositiveIntegerField(null=True, blank=True)

    is_read = models.BooleanField(default=False, db_index=True)
    is_emailed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.title} → {self.recipient}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    @property
    def severity_icon(self):
        icons = {
            self.Severity.INFO: "bi-info-circle",
            self.Severity.WARNING: "bi-exclamation-triangle",
            self.Severity.CRITICAL: "bi-exclamation-octagon",
        }
        return icons.get(self.severity, "bi-bell")

    @property
    def severity_color(self):
        colors = {
            self.Severity.INFO: "primary",
            self.Severity.WARNING: "warning",
            self.Severity.CRITICAL: "danger",
        }
        return colors.get(self.severity, "secondary")


class NotificationSettings(models.Model):
    """Настройки уведомлений пользователя."""

    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="notification_settings"
    )
    health_alerts = models.BooleanField(default=True)
    weather_alerts = models.BooleanField(default=True)
    entry_reminders = models.BooleanField(default=True)
    challenge_updates = models.BooleanField(default=True)
    ai_tips = models.BooleanField(default=True)

    reminder_time = models.TimeField(default=time(20, 0))  # время ежедневного напоминания
    quiet_hours_start = models.TimeField(null=True, blank=True)  # 22:00
    quiet_hours_end = models.TimeField(null=True, blank=True)    # 08:00

    email_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Настройки уведомлений"
        verbose_name_plural = "Настройки уведомлений"

    def __str__(self):
        return f"Настройки уведомлений {self.user}"

    def is_quiet_time(self):
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        now = timezone.localtime().time()
        s, e = self.quiet_hours_start, self.quiet_hours_end
        if s < e:
            return s <= now < e
        return now >= s or now < e  # через полночь
