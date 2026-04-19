import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.services import get_subject_chart_payload
from apps.health.models import MetricRecord, MetricType


User = get_user_model()


class DashboardMetricTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="subject-user",
            email="subject@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.SUBJECT,
        )
        self.client.login(username=self.user.email, password="pass12345")

    def test_subject_dashboard_shows_pulse_from_latest_blood_pressure_when_standalone_record_is_missing(self):
        MetricRecord.objects.create(
            subject=self.user,
            metric_type=MetricType.BLOOD_PRESSURE,
            value_json={"systolic": 118, "diastolic": 77, "pulse": 69},
        )

        response = self.client.get(reverse("subject-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "69")

    def test_subject_dashboard_renders_all_metric_charts(self):
        MetricRecord.objects.create(
            subject=self.user,
            metric_type=MetricType.STEPS,
            value_json={"steps": 6800},
        )
        MetricRecord.objects.create(
            subject=self.user,
            metric_type=MetricType.BLOOD_PRESSURE,
            value_json={"systolic": 122, "diastolic": 81, "pulse": 73},
        )

        response = self.client.get(reverse("subject-dashboard"))

        self.assertContains(response, 'id="steps-chart"')
        self.assertContains(response, 'id="bp-chart"')
        self.assertContains(response, 'id="heart-rate-chart"')
        self.assertContains(response, "renderHeartRateChart")

    def test_chart_payload_is_chronological_and_uses_local_day_boundaries(self):
        tz = ZoneInfo("Asia/Almaty")
        today = timezone.localdate()
        start_date = today - timedelta(days=6)
        edge_timestamp = datetime.combine(start_date, datetime.min.time(), tzinfo=tz) + timedelta(minutes=30)

        MetricRecord.objects.create(
            subject=self.user,
            metric_type=MetricType.STEPS,
            value_json={"steps": 1500},
            recorded_at=edge_timestamp,
        )
        MetricRecord.objects.create(
            subject=self.user,
            metric_type=MetricType.BLOOD_PRESSURE,
            value_json={"systolic": 130, "diastolic": 85, "pulse": 71},
            recorded_at=edge_timestamp + timedelta(hours=1),
        )
        MetricRecord.objects.create(
            subject=self.user,
            metric_type=MetricType.HEART_RATE,
            value_json={"bpm": 74},
            recorded_at=edge_timestamp + timedelta(days=1),
        )

        chart_payload = get_subject_chart_payload(self.user)
        labels = json.loads(chart_payload["labels_json"])
        steps = json.loads(chart_payload["steps_json"])
        blood_pressure_points = json.loads(chart_payload["bp_json"])
        heart_rate_points = json.loads(chart_payload["heart_rate_json"])

        self.assertEqual(labels[0], start_date.strftime("%d.%m"))
        self.assertEqual(steps[0], 1500)
        self.assertEqual(blood_pressure_points[0]["date"], start_date.strftime("%d.%m"))
        self.assertEqual(heart_rate_points[0]["bpm"], 71)
        self.assertEqual(heart_rate_points[-1]["bpm"], 74)
