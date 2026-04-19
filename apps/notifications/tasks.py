from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import shared_task
from django.utils import timezone

from apps.health.models import MetricRecord, MetricType

from .models import Notification, NotificationSettings

ENTRY_REMINDER_TITLE = "Напоминание о вводе показателей"
ENTRY_REMINDER_BODY = (
    "Сегодня еще нет записей по давлению, пульсу или шагам. "
    "Откройте дашборд и добавьте показатели."
)
ENTRY_REMINDER_WINDOW_MINUTES = 10
PRIMARY_REMINDER_METRICS = (
    MetricType.BLOOD_PRESSURE,
    MetricType.HEART_RATE,
    MetricType.STEPS,
)


def _get_user_timezone(user):
    timezone_name = getattr(user, "timezone", "") or timezone.get_current_timezone_name()
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.get_current_timezone()


def _is_quiet_time(settings_obj, current_time):
    if not settings_obj.quiet_hours_start or not settings_obj.quiet_hours_end:
        return False

    start = settings_obj.quiet_hours_start
    end = settings_obj.quiet_hours_end
    if start < end:
        return start <= current_time < end
    return current_time >= start or current_time < end


def _is_due_reminder_time(reminder_time, current_dt):
    reminder_dt = current_dt.replace(
        hour=reminder_time.hour,
        minute=reminder_time.minute,
        second=0,
        microsecond=0,
    )
    return reminder_dt <= current_dt < reminder_dt + timedelta(minutes=ENTRY_REMINDER_WINDOW_MINUTES)


@shared_task
def send_entry_reminders(now=None):
    current_dt = now or timezone.now()
    if timezone.is_naive(current_dt):
        current_dt = timezone.make_aware(current_dt, timezone.get_current_timezone())

    sent_count = 0
    settings_queryset = NotificationSettings.objects.select_related("user").filter(
        entry_reminders=True,
        user__is_active=True,
        user__onboarding_completed=True,
    )

    for settings_obj in settings_queryset:
        user = settings_obj.user
        if not user.is_subject:
            continue

        user_now = timezone.localtime(current_dt, _get_user_timezone(user))
        if not _is_due_reminder_time(settings_obj.reminder_time, user_now):
            continue
        if _is_quiet_time(settings_obj, user_now.time()):
            continue

        day_start = user_now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        already_sent_today = Notification.objects.filter(
            recipient=user,
            category=Notification.Category.ENTRY_REMINDER,
            title=ENTRY_REMINDER_TITLE,
            created_at__gte=day_start,
            created_at__lt=day_end,
        ).exists()
        if already_sent_today:
            continue

        has_primary_metrics_today = MetricRecord.objects.filter(
            subject=user,
            metric_type__in=PRIMARY_REMINDER_METRICS,
            recorded_at__gte=day_start,
            recorded_at__lt=day_end,
        ).exists()
        if has_primary_metrics_today:
            continue

        Notification.objects.create(
            recipient=user,
            related_subject=user,
            title=ENTRY_REMINDER_TITLE,
            body=ENTRY_REMINDER_BODY,
            severity=Notification.Severity.INFO,
            category=Notification.Category.ENTRY_REMINDER,
        )
        sent_count += 1

    return sent_count
