from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from apps.health.models import MetricRecord, MetricType

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


class ReminderFlowTests(TestCase):
    def test_periodic_tasks_for_notifications_and_reminders_are_registered(self):
        task_names = set(PeriodicTask.objects.values_list("name", flat=True))

        self.assertIn("janynda.generate_recurring_plan_items", task_names)
        self.assertIn("janynda.send_task_reminders", task_names)
        self.assertIn("janynda.send_entry_reminders", task_names)
        self.assertIn("janynda.check_location_absence", task_names)
        self.assertIn("janynda.check_wearable_goals", task_names)

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
