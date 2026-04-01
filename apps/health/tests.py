import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.health.models import MetricRecord, MetricType


User = get_user_model()


class QuickEntryCsrfTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="subject",
            email="subject@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.SUBJECT,
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.login(username=self.user.email, password="pass12345")

    def test_subject_dashboard_renders_csrf_tokens_for_quick_entry_forms(self):
        response = self.client.get(reverse("subject-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "csrfmiddlewaretoken", count=3)

    def test_quick_entry_accepts_valid_post_with_csrf_token(self):
        page = self.client.get(reverse("subject-dashboard"))
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())
        self.assertIsNotNone(match)

        response = self.client.post(
            reverse("health-quick-entry", args=[MetricType.HEART_RATE]),
            {"bpm": 72, "csrfmiddlewaretoken": match.group(1)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сохранено")
        self.assertTrue(
            MetricRecord.objects.filter(
                subject=self.user,
                metric_type=MetricType.HEART_RATE,
                value_json__bpm=72,
            ).exists()
        )
