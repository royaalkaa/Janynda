import django.utils.timezone
from django.db import migrations


PERIODIC_TASK_NAMES = (
    "janynda.generate_recurring_plan_items",
    "janynda.send_task_reminders",
    "janynda.send_entry_reminders",
    "janynda.check_location_absence",
    "janynda.check_wearable_goals",
)


def setup_periodic_tasks(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTasks = apps.get_model("django_celery_beat", "PeriodicTasks")

    every_minute, _ = IntervalSchedule.objects.get_or_create(every=1, period="minutes")
    every_five_minutes, _ = IntervalSchedule.objects.get_or_create(every=5, period="minutes")
    every_ten_minutes, _ = IntervalSchedule.objects.get_or_create(every=10, period="minutes")
    every_thirty_minutes, _ = IntervalSchedule.objects.get_or_create(every=30, period="minutes")
    daily_after_midnight, _ = CrontabSchedule.objects.get_or_create(
        minute="5",
        hour="0",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="Asia/Almaty",
    )

    PeriodicTask.objects.update_or_create(
        name="janynda.generate_recurring_plan_items",
        defaults={
            "task": "apps.care.tasks.generate_recurring_plan_items",
            "crontab": daily_after_midnight,
            "interval": None,
            "kwargs": '{"days_ahead": 30}',
            "enabled": True,
        },
    )
    PeriodicTask.objects.update_or_create(
        name="janynda.send_task_reminders",
        defaults={
            "task": "apps.care.tasks.send_task_reminders",
            "interval": every_minute,
            "crontab": None,
            "enabled": True,
        },
    )
    PeriodicTask.objects.update_or_create(
        name="janynda.send_entry_reminders",
        defaults={
            "task": "apps.notifications.tasks.send_entry_reminders",
            "interval": every_ten_minutes,
            "crontab": None,
            "enabled": True,
        },
    )
    PeriodicTask.objects.update_or_create(
        name="janynda.check_location_absence",
        defaults={
            "task": "apps.care.tasks.check_location_absence",
            "interval": every_five_minutes,
            "crontab": None,
            "enabled": True,
        },
    )
    PeriodicTask.objects.update_or_create(
        name="janynda.check_wearable_goals",
        defaults={
            "task": "apps.care.tasks.check_wearable_goals",
            "interval": every_thirty_minutes,
            "crontab": None,
            "enabled": True,
        },
    )

    PeriodicTasks.objects.update_or_create(
        ident=1,
        defaults={"last_update": django.utils.timezone.now()},
    )


def remove_periodic_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTasks = apps.get_model("django_celery_beat", "PeriodicTasks")

    PeriodicTask.objects.filter(name__in=PERIODIC_TASK_NAMES).delete()
    PeriodicTasks.objects.update_or_create(
        ident=1,
        defaults={"last_update": django.utils.timezone.now()},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(setup_periodic_tasks, remove_periodic_tasks),
    ]
