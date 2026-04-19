import json
import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.dashboard.services import get_subject_chart_payload
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

    def _get_csrf_token(self):
        page = self.client.get(reverse("subject-dashboard"))
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())
        self.assertIsNotNone(match)
        return match.group(1)

    def test_subject_dashboard_renders_csrf_tokens_for_quick_entry_forms(self):
        response = self.client.get(reverse("subject-dashboard"))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        for metric_type in [MetricType.BLOOD_PRESSURE, MetricType.STEPS, MetricType.HEART_RATE]:
            form_action = re.escape(reverse("health-quick-entry", args=[metric_type]))
            self.assertRegex(
                html,
                re.compile(rf'<form[^>]+hx-post="{form_action}"[^>]*>.*?name="csrfmiddlewaretoken"', re.S),
            )

    def test_quick_entry_accepts_valid_post_with_csrf_token(self):
        response = self.client.post(
            reverse("health-quick-entry", args=[MetricType.HEART_RATE]),
            {"bpm": 72, "csrfmiddlewaretoken": self._get_csrf_token()},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Refresh"), "true")
        self.assertTrue(
            MetricRecord.objects.filter(
                subject=self.user,
                metric_type=MetricType.HEART_RATE,
                value_json__bpm=72,
            ).exists()
        )

    def test_blood_pressure_quick_entry_with_pulse_creates_heart_rate_record_and_chart_points(self):
        response = self.client.post(
            reverse("health-quick-entry", args=[MetricType.BLOOD_PRESSURE]),
            {
                "systolic": 120,
                "diastolic": 80,
                "pulse": 70,
                "csrfmiddlewaretoken": self._get_csrf_token(),
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Refresh"), "true")

        blood_pressure_record = MetricRecord.objects.get(
            subject=self.user,
            metric_type=MetricType.BLOOD_PRESSURE,
        )
        heart_rate_record = MetricRecord.objects.get(
            subject=self.user,
            metric_type=MetricType.HEART_RATE,
        )

        self.assertEqual(blood_pressure_record.value_json["pulse"], 70)
        self.assertEqual(heart_rate_record.value_json["bpm"], 70)
        self.assertEqual(heart_rate_record.recorded_at, blood_pressure_record.recorded_at)

        chart_payload = get_subject_chart_payload(self.user)
        self.assertEqual(json.loads(chart_payload["bp_json"])[-1]["systolic"], 120)
        self.assertEqual(json.loads(chart_payload["heart_rate_json"])[-1]["bpm"], 70)
