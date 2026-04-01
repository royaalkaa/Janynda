from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.services import attach_subject_to_observer
from apps.notifications.models import Notification

from .models import (
    CommunityPlace,
    DailyPlanItem,
    FavoritePlace,
    LocationPing,
    SafeZone,
    TaskReminder,
    WearableDailySummary,
    WearableDevice,
)
from .services import get_or_create_location_settings
from .tasks import check_location_absence, check_wearable_goals, generate_recurring_plan_items, send_task_reminders


User = get_user_model()


class CarePlanFlowTests(TestCase):
    def setUp(self):
        self.observer = User.objects.create_user(
            username="observer-plan",
            email="observer-plan@example.com",
            password="pass12345",
            role=User.Role.OBSERVER,
            onboarding_completed=True,
        )
        self.membership = attach_subject_to_observer(
            self.observer,
            group_name="Семья план",
            relative_name="Мама План",
            relation="mother",
            relative_email="plan-subject@example.com",
        )
        self.subject = self.membership.subject
        self.client.login(username=self.observer.email, password="pass12345")

    def test_observer_can_create_edit_and_delete_plan_item_for_subject(self):
        create_response = self.client.post(
            reverse("care-plan-subject", args=[self.subject.id]),
            {
                "title": "Выпить лекарство",
                "description": "После завтрака",
                "scheduled_date": timezone.localdate().isoformat(),
                "scheduled_time": "09:00",
                "duration_minutes": 10,
                "category": DailyPlanItem.Category.MEDICATION,
                "priority": DailyPlanItem.Priority.HIGH,
                "medicine_name": "Кардиомагнил",
                "medicine_dosage": "1 таблетка",
                "remind_before_minutes": 30,
            },
        )

        self.assertEqual(create_response.status_code, 302)
        item = DailyPlanItem.objects.get(subject=self.subject, title="Выпить лекарство")
        self.assertEqual(item.medicine_name, "Кардиомагнил")
        self.assertTrue(TaskReminder.objects.filter(task=item, remind_before_minutes=30).exists())

        edit_response = self.client.post(
            reverse("task_edit", args=[item.id]),
            {
                "title": "Выпить лекарство утром",
                "description": "После завтрака",
                "scheduled_date": timezone.localdate().isoformat(),
                "scheduled_time": "08:30",
                "duration_minutes": 10,
                "category": DailyPlanItem.Category.MEDICATION,
                "priority": DailyPlanItem.Priority.HIGH,
                "recurrence_type": DailyPlanItem.RecurrenceType.WEEKLY,
                "recurrence_days": ["0", "2"],
                "recurrence_end_date": (timezone.localdate() + timedelta(days=30)).isoformat(),
                "medicine_name": "Кардиомагнил",
                "medicine_dosage": "2 таблетки",
                "remind_before_minutes": 45,
            },
        )

        self.assertEqual(edit_response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.title, "Выпить лекарство утром")
        self.assertEqual(item.recurrence_type, DailyPlanItem.RecurrenceType.WEEKLY)
        self.assertEqual(item.recurrence_days, [0, 2])
        self.assertTrue(TaskReminder.objects.filter(task=item, remind_before_minutes=45).exists())

        delete_response = self.client.post(reverse("task_delete", args=[item.id]))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(DailyPlanItem.objects.filter(pk=item.id).exists())

    def test_task_history_shows_completed_items(self):
        task = DailyPlanItem.objects.create(
            subject=self.subject,
            created_by=self.observer,
            completed_by=self.observer,
            title="Контроль давления",
            scheduled_date=timezone.localdate(),
            category=DailyPlanItem.Category.HEALTH_CHECK,
            is_completed=True,
            completed_at=timezone.now(),
        )

        response = self.client.get(reverse("task_history"), {"subject_id": self.subject.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, task.title)

    def test_recurring_task_generation_creates_future_occurrences(self):
        template = DailyPlanItem.objects.create(
            subject=self.subject,
            created_by=self.observer,
            title="Стакан воды",
            scheduled_date=timezone.localdate(),
            category=DailyPlanItem.Category.WATER,
            recurrence_type=DailyPlanItem.RecurrenceType.DAILY,
            water_amount_ml=250,
        )
        TaskReminder.objects.create(task=template, remind_before_minutes=20)

        created_count = generate_recurring_plan_items(days_ahead=3)

        self.assertEqual(created_count, 3)
        self.assertEqual(template.generated_occurrences.count(), 3)
        self.assertEqual(TaskReminder.objects.filter(task__recurrence_parent=template).count(), 3)

    def test_send_task_reminders_creates_notifications(self):
        task = DailyPlanItem.objects.create(
            subject=self.subject,
            created_by=self.observer,
            title="Приём лекарства",
            scheduled_date=timezone.localdate(),
            scheduled_time=(timezone.localtime() + timedelta(minutes=5)).time().replace(second=0, microsecond=0),
            category=DailyPlanItem.Category.MEDICATION,
        )
        TaskReminder.objects.create(task=task, remind_before_minutes=10)

        sent_count = send_task_reminders()

        self.assertGreaterEqual(sent_count, 1)
        self.assertTrue(Notification.objects.filter(related_subject=self.subject, title__icontains="Напоминание").exists())


class LocationFlowTests(TestCase):
    def setUp(self):
        self.observer = User.objects.create_user(
            username="observer-location",
            email="observer-location@example.com",
            password="pass12345",
            role=User.Role.OBSERVER,
            onboarding_completed=True,
        )
        membership = attach_subject_to_observer(
            self.observer,
            group_name="Семья локация",
            relative_name="Бабушка Локация",
            relation="grandmother",
            relative_email="subject-location@example.com",
            can_view_location=True,
        )
        self.subject = membership.subject
        self.client.force_login(self.subject)

    def test_subject_can_submit_location_ping_and_sos(self):
        response = self.client.post(
            reverse("care-location"),
            {
                "action": "ping",
                "latitude": "43.238949",
                "longitude": "76.889709",
                "source": "manual",
                "note": "Дома",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(LocationPing.objects.filter(subject=self.subject, note="Дома").exists())

        sos_response = self.client.post(
            reverse("emergency_sos"),
            {"subject_id": self.subject.id, "latitude": "43.238949", "longitude": "76.889709"},
        )

        self.assertEqual(sos_response.status_code, 302)
        self.assertTrue(LocationPing.objects.filter(subject=self.subject, is_emergency=True).exists())
        self.assertTrue(Notification.objects.filter(title="SOS сигнал", related_subject=self.subject).exists())

    def test_safe_zone_crossing_and_absence_create_notifications(self):
        settings = get_or_create_location_settings(self.subject)
        settings.tracking_enabled = True
        settings.share_with_family = True
        settings.max_absence_hours = 4
        settings.save(update_fields=["tracking_enabled", "share_with_family", "max_absence_hours"])

        SafeZone.objects.create(
            subject=self.subject,
            name="Дом",
            latitude="43.238949",
            longitude="76.889709",
            radius_meters=200,
            is_home=True,
        )
        home_ping = LocationPing.objects.create(
            subject=self.subject,
            created_by=self.subject,
            latitude="43.238949",
            longitude="76.889709",
            note="Дома",
            captured_at=timezone.now() - timedelta(hours=5),
        )
        outside_ping = LocationPing.objects.create(
            subject=self.subject,
            created_by=self.subject,
            latitude="43.250000",
            longitude="76.920000",
            note="На прогулке",
            captured_at=timezone.now() - timedelta(hours=4, minutes=30),
        )

        self.assertTrue(Notification.objects.filter(title="Выход из дома", related_subject=self.subject).exists())

        notified = check_location_absence()

        self.assertGreaterEqual(notified, 1)
        self.assertTrue(Notification.objects.filter(title="Долгое отсутствие вне дома", related_subject=self.subject).exists())


class PlacesAndWearablesTests(TestCase):
    def setUp(self):
        self.subject = User.objects.create_user(
            username="subject-care",
            email="subject-care@example.com",
            password="pass12345",
            role=User.Role.SUBJECT,
            onboarding_completed=True,
        )
        self.client.login(username=self.subject.email, password="pass12345")

    def test_places_page_contains_active_longevity_center_and_favorites(self):
        settings = get_or_create_location_settings(self.subject)
        settings.home_latitude = "43.238949"
        settings.home_longitude = "76.889709"
        settings.city = "Алматы"
        settings.save(update_fields=["home_latitude", "home_longitude", "city"])

        place = CommunityPlace.objects.create(
            name="Аптека у дома",
            category=CommunityPlace.Category.PHARMACY,
            city="Алматы",
            address="Абая, 1",
            latitude="43.240000",
            longitude="76.890000",
            working_hours="08:00-22:00",
        )

        response = self.client.get(reverse("care-places"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Центр активного долголетия")

        favorite_response = self.client.post(
            reverse("toggle_favorite", args=[place.id]),
            {"subject_id": self.subject.id, "next": reverse("care-places")},
        )
        self.assertEqual(favorite_response.status_code, 302)
        self.assertTrue(FavoritePlace.objects.filter(subject=self.subject, place=place).exists())

        favorites_only = self.client.get(reverse("care-places"), {"favorites": "1"})
        self.assertContains(favorites_only, "Аптека у дома")

    def test_subject_can_add_wearable_summary_view_stats_and_get_goal_notifications(self):
        device_response = self.client.post(
            reverse("care-wearables"),
            {
                "action": "device",
                "provider": WearableDevice.Provider.XIAOMI,
                "nickname": "Mi Band",
                "external_id": "mi-1",
                "is_active": "on",
            },
        )
        self.assertEqual(device_response.status_code, 302)

        device = WearableDevice.objects.get(subject=self.subject, nickname="Mi Band")
        summary_response = self.client.post(
            reverse("care-wearables"),
            {
                "action": "summary",
                "device": device.id,
                "summary_date": timezone.localdate().isoformat(),
                "steps": 3200,
                "average_heart_rate": 71,
                "heart_rate_min": 49,
                "heart_rate_max": 125,
                "sleep_hours": "7.5",
                "sleep_quality": WearableDailySummary.SleepQuality.GOOD,
                "deep_sleep_hours": "2.1",
                "light_sleep_hours": "5.4",
                "active_minutes": 38,
                "distance_km": "4.60",
                "calories_kcal": 340,
            },
        )

        self.assertEqual(summary_response.status_code, 302)
        self.assertTrue(WearableDailySummary.objects.filter(device=device, heart_rate_max=125).exists())

        stats_response = self.client.get(reverse("wearables_stats"))
        self.assertEqual(stats_response.status_code, 200)
        self.assertContains(stats_response, "Графики")

        notifications_count = check_wearable_goals(self.subject.id)
        self.assertGreaterEqual(notifications_count, 1)
        self.assertTrue(Notification.objects.filter(related_subject=self.subject).exists())
