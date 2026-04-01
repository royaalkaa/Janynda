from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.care.models import DailyPlanItem
from apps.health.models import MetricRecord, MetricType

from .models import VoiceCommandLog


User = get_user_model()


class VoiceAssistantCommandTests(TestCase):
    def setUp(self):
        self.subject = User.objects.create_user(
            username="voice-subject",
            email="voice-subject@example.com",
            password="pass12345",
            role=User.Role.SUBJECT,
            onboarding_completed=True,
        )
        self.client.login(username=self.subject.email, password="pass12345")

    def test_medication_command_requires_confirmation_and_marks_plan_item_completed(self):
        item = DailyPlanItem.objects.create(
            subject=self.subject,
            created_by=self.subject,
            title="Утренние таблетки",
            scheduled_date=timezone.localdate(),
            category=DailyPlanItem.Category.MEDICATION,
        )

        pending_response = self.client.post(
            reverse("ai-voice-command"),
            {"subject_id": self.subject.id, "transcript": "Я выпил лекарство кардиомагнил"},
        )

        self.assertEqual(pending_response.status_code, 200)
        pending_payload = pending_response.json()
        self.assertTrue(pending_payload["requires_confirmation"])
        pending_log = VoiceCommandLog.objects.get(pk=pending_payload["log_id"])
        self.assertFalse(pending_log.confirmed)

        confirm_response = self.client.post(
            reverse("ai-voice-command"),
            {
                "subject_id": self.subject.id,
                "confirmation": "yes",
                "confirmation_log_id": pending_log.id,
                "confirmation_text": "Подтверждаю",
            },
        )

        self.assertEqual(confirm_response.status_code, 200)
        item.refresh_from_db()
        self.assertTrue(item.is_completed)
        self.assertTrue(
            VoiceCommandLog.objects.filter(subject=self.subject, action_type="plan_complete", confirmed=True).exists()
        )

    def test_metric_command_confirmation_and_cancel(self):
        pending_response = self.client.post(
            reverse("ai-voice-command"),
            {"subject_id": self.subject.id, "transcript": "Пульс 72"},
        )

        pending_payload = pending_response.json()
        self.assertTrue(pending_payload["requires_confirmation"])
        self.assertFalse(
            MetricRecord.objects.filter(
                subject=self.subject,
                metric_type=MetricType.HEART_RATE,
                value_json__bpm=72,
            ).exists()
        )

        cancel_response = self.client.post(
            reverse("ai-voice-command"),
            {
                "subject_id": self.subject.id,
                "confirmation": "no",
                "confirmation_log_id": pending_payload["log_id"],
                "confirmation_text": "Отмена",
            },
        )

        self.assertEqual(cancel_response.status_code, 200)
        self.assertFalse(
            MetricRecord.objects.filter(
                subject=self.subject,
                metric_type=MetricType.HEART_RATE,
                value_json__bpm=72,
            ).exists()
        )
        self.assertTrue(VoiceCommandLog.objects.filter(action_type=VoiceCommandLog.ActionType.CANCELLED).exists())

    def test_extended_questions_about_medicine_doctor_and_water(self):
        DailyPlanItem.objects.create(
            subject=self.subject,
            created_by=self.subject,
            title="Утренний аспирин",
            scheduled_date=timezone.localdate(),
            scheduled_time=datetime.strptime("09:00", "%H:%M").time(),
            category=DailyPlanItem.Category.MEDICATION,
            medicine_name="Аспирин",
            medicine_dosage="1 таблетка",
        )
        DailyPlanItem.objects.create(
            subject=self.subject,
            created_by=self.subject,
            title="Кардиолог",
            scheduled_date=timezone.localdate() + timedelta(days=1),
            scheduled_time=datetime.strptime("11:00", "%H:%M").time(),
            category=DailyPlanItem.Category.DOCTOR_VISIT,
            doctor_specialty="Кардиолог",
            doctor_address="Поликлиника №5",
        )
        DailyPlanItem.objects.create(
            subject=self.subject,
            created_by=self.subject,
            completed_by=self.subject,
            title="Стакан воды",
            scheduled_date=timezone.localdate(),
            category=DailyPlanItem.Category.WATER,
            water_amount_ml=250,
            is_completed=True,
            completed_at=timezone.now(),
        )

        medicine_response = self.client.post(
            reverse("ai-voice-command"),
            {"subject_id": self.subject.id, "transcript": "Какое лекарство сейчас принимать?"},
        )
        self.assertIn("Аспирин", medicine_response.json()["response"])

        doctor_response = self.client.post(
            reverse("ai-voice-command"),
            {"subject_id": self.subject.id, "transcript": "Когда к врачу?"},
        )
        self.assertIn("Кардиолог", doctor_response.json()["response"])

        water_response = self.client.post(
            reverse("ai-voice-command"),
            {"subject_id": self.subject.id, "transcript": "Сколько воды я выпил сегодня?"},
        )
        self.assertIn("250 мл", water_response.json()["response"])
