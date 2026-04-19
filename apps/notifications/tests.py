import os
from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from apps.health.models import MetricRecord, MetricType

from .local_scheduler import (
    InProcessScheduler,
    LocalSchedulerJob,
    get_default_scheduler_jobs,
    should_start_inprocess_scheduler,
)
from .models import Notification
from .tasks import ENTRY_REMINDER_TITLE, send_entry_reminders


User = get_user_model()


class NotificationRedirectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="observer",
            email="observer@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.OBSERVER,
        )
        self.client.login(username=self.user.email, password="pass12345")
        self.notification = Notification.objects.create(
            recipient=self.user,
            title="Тест",
            body="Пора проверить показатели.",
        )

    def test_read_view_rejects_external_referer(self):
        response = self.client.post(
            reverse("notification-read", args=[self.notification.pk]),
            HTTP_REFERER="https://evil.example/phishing",
        )

        self.notification.refresh_from_db()

        self.assertTrue(self.notification.is_read)
        self.assertRedirects(response, reverse("notifications-list"))

    def test_read_view_preserves_internal_referer(self):
        response = self.client.post(
            reverse("notification-read", args=[self.notification.pk]),
            HTTP_REFERER="http://testserver/weather/",
        )

        self.assertRedirects(
            response,
            "http://testserver/weather/",
            fetch_redirect_response=False,
        )

    def test_observer_notifications_sidebar_exposes_reminders(self):
        response = self.client.get(reverse("notifications-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Напоминания")
        self.assertContains(response, reverse("care-plan"))


class NotificationNavigationTests(TestCase):
    def test_empty_notifications_link_to_reminders_page(self):
        user = User.objects.create_user(
            username="observer-empty-notifications",
            email="observer-empty-notifications@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.OBSERVER,
        )
        self.client.login(username=user.email, password="pass12345")

        response = self.client.get(reverse("notifications-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Уведомлений пока нет")
        self.assertContains(response, "Открыть напоминания")
        self.assertContains(response, reverse("care-plan"))

    def test_subject_notifications_use_subject_navigation_with_reminders(self):
        user = User.objects.create_user(
            username="subject-notifications",
            email="subject-notifications@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.SUBJECT,
        )
        self.client.login(username=user.email, password="pass12345")

        response = self.client.get(reverse("notifications-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Напоминания")
        self.assertNotContains(response, "Наблюдающий режим")


class ReminderFlowTests(TestCase):
    def test_periodic_tasks_for_notifications_and_reminders_are_registered(self):
        task_names = set(PeriodicTask.objects.values_list("name", flat=True))

        self.assertIn("janynda.generate_recurring_plan_items", task_names)
        self.assertIn("janynda.send_task_reminders", task_names)
        self.assertIn("janynda.send_entry_reminders", task_names)
        self.assertIn("janynda.check_location_absence", task_names)
        self.assertIn("janynda.check_wearable_goals", task_names)
        entry_reminder_task = PeriodicTask.objects.select_related("interval").get(
            name="janynda.send_entry_reminders"
        )
        self.assertEqual(entry_reminder_task.interval.every, 1)
        self.assertEqual(entry_reminder_task.interval.period, "minutes")

    def test_send_entry_reminders_creates_notification_only_once_for_due_subject(self):
        current_dt = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(20, 5)),
            timezone.get_current_timezone(),
        )

        due_subject = User.objects.create_user(
            username="subject-reminder",
            email="subject-reminder@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.SUBJECT,
        )
        due_subject.notification_settings.reminder_time = time(20, 0)
        due_subject.notification_settings.save(update_fields=["reminder_time"])

        observer = User.objects.create_user(
            username="observer-reminder",
            email="observer-reminder@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.OBSERVER,
        )
        observer.notification_settings.reminder_time = time(20, 0)
        observer.notification_settings.save(update_fields=["reminder_time"])

        subject_with_metrics = User.objects.create_user(
            username="subject-with-metrics",
            email="subject-with-metrics@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.SUBJECT,
        )
        subject_with_metrics.notification_settings.reminder_time = time(20, 0)
        subject_with_metrics.notification_settings.save(update_fields=["reminder_time"])
        MetricRecord.objects.create(
            subject=subject_with_metrics,
            metric_type=MetricType.STEPS,
            value_json={"steps": 4200},
            recorded_at=current_dt - timedelta(hours=1),
        )

        disabled_subject = User.objects.create_user(
            username="subject-disabled-reminder",
            email="subject-disabled-reminder@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.SUBJECT,
        )
        disabled_subject.notification_settings.entry_reminders = False
        disabled_subject.notification_settings.reminder_time = time(20, 0)
        disabled_subject.notification_settings.save(update_fields=["entry_reminders", "reminder_time"])

        sent_count = send_entry_reminders(now=current_dt)

        self.assertEqual(sent_count, 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=due_subject,
                related_subject=due_subject,
                title=ENTRY_REMINDER_TITLE,
            ).exists()
        )
        self.assertFalse(Notification.objects.filter(recipient=observer, title=ENTRY_REMINDER_TITLE).exists())
        self.assertFalse(
            Notification.objects.filter(
                recipient=subject_with_metrics,
                title=ENTRY_REMINDER_TITLE,
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                recipient=disabled_subject,
                title=ENTRY_REMINDER_TITLE,
            ).exists()
        )

        sent_count_again = send_entry_reminders(now=current_dt + timedelta(minutes=1))

        self.assertEqual(sent_count_again, 0)
        self.assertEqual(
            Notification.objects.filter(recipient=due_subject, title=ENTRY_REMINDER_TITLE).count(),
            1,
        )


class SingleProcessRuntimeTests(TestCase):
    def test_runtime_defaults_do_not_require_redis_or_celery_worker(self):
        self.assertIn("LocMemCache", settings.CACHES["default"]["BACKEND"])
        self.assertEqual(settings.CELERY_BROKER_URL, "memory://")
        self.assertEqual(settings.CELERY_RESULT_BACKEND, "cache+memory://")
        self.assertTrue(settings.CELERY_TASK_ALWAYS_EAGER)

    def test_default_local_scheduler_contains_reminder_jobs(self):
        job_names = {job.name for job in get_default_scheduler_jobs()}

        self.assertIn("send_task_reminders", job_names)
        self.assertIn("send_entry_reminders", job_names)
        self.assertIn("generate_recurring_plan_items", job_names)
        self.assertIn("check_location_absence", job_names)
        self.assertIn("check_wearable_goals", job_names)

    def test_inprocess_scheduler_runs_due_jobs_without_broker(self):
        calls = []
        current_dt = timezone.now()
        scheduler = InProcessScheduler(
            jobs=[
                LocalSchedulerJob(
                    name="local-reminder",
                    interval=timedelta(minutes=1),
                    callback=lambda: calls.append("ran") or "ok",
                )
            ],
            sleep_seconds=999,
        )

        first_results = scheduler.run_pending(now=current_dt)
        second_results = scheduler.run_pending(now=current_dt + timedelta(seconds=30))
        third_results = scheduler.run_pending(now=current_dt + timedelta(seconds=61))

        self.assertEqual(calls, ["ran", "ran"])
        self.assertEqual(first_results[0].name, "local-reminder")
        self.assertEqual(first_results[0].result, "ok")
        self.assertEqual(second_results, [])
        self.assertEqual(third_results[0].result, "ok")

    @override_settings(JANYNDA_INPROCESS_SCHEDULER_ENABLED=True)
    def test_inprocess_scheduler_starts_only_for_runserver_process(self):
        with patch("apps.notifications.local_scheduler.sys.argv", ["manage.py", "runserver"]):
            with patch.dict(os.environ, {"RUN_MAIN": "true"}, clear=False):
                self.assertTrue(should_start_inprocess_scheduler())

        with patch("apps.notifications.local_scheduler.sys.argv", ["manage.py", "migrate"]):
            with patch.dict(os.environ, {"RUN_MAIN": "true"}, clear=False):
                self.assertFalse(should_start_inprocess_scheduler())
