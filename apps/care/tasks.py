from celery import shared_task

from apps.accounts.models import User

from .services import (
    check_subject_absence,
    dispatch_task_reminder,
    generate_recurring_occurrences,
    get_due_task_reminders,
    handle_zone_crossing_for_ping,
)


@shared_task
def generate_recurring_plan_items(days_ahead=30):
    return len(generate_recurring_occurrences(days_ahead=days_ahead))


@shared_task
def send_task_reminders():
    sent_count = 0
    for reminder in get_due_task_reminders():
        if dispatch_task_reminder(reminder):
            sent_count += 1
    return sent_count


@shared_task
def check_location_ping_events(ping_id):
    from .models import LocationPing

    ping = LocationPing.objects.filter(pk=ping_id).select_related("subject").first()
    if not ping:
        return 0
    return len(handle_zone_crossing_for_ping(ping))


@shared_task
def check_location_absence():
    count = 0
    for subject in User.objects.filter(location_sharing_settings__isnull=False):
        if check_subject_absence(subject):
            count += 1
    return count


@shared_task
def check_wearable_goals(subject_id=None):
    from .services import check_wearable_goals_for_subject

    if subject_id:
        subject = User.objects.filter(pk=subject_id).first()
        if not subject:
            return 0
        return check_wearable_goals_for_subject(subject)

    count = 0
    for subject in User.objects.filter(wearable_devices__isnull=False).distinct():
        count += check_wearable_goals_for_subject(subject)
    return count
