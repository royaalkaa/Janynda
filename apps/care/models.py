import calendar
import math

from django.conf import settings
from django.db import models
from django.utils import timezone


def _distance_km(origin, destination):
    try:
        from geopy.distance import distance
    except ImportError:
        distance = None

    if distance is not None:
        return distance(origin, destination).km

    lat1, lon1 = map(math.radians, origin)
    lat2, lon2 = map(math.radians, destination)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371.0 * c


class DailyPlanItem(models.Model):
    class Category(models.TextChoices):
        MEDICATION = "medication", "Лекарства"
        DOCTOR_VISIT = "doctor_visit", "Врач"
        WALK = "walk", "Прогулка"
        EXERCISE = "exercise", "Упражнения"
        HEALTH_CHECK = "health_check", "Проверка здоровья"
        MEAL = "meal", "Питание"
        WATER = "water", "Вода"
        SOCIAL = "social", "Общение"
        SHOPPING = "shopping", "Покупки"
        TASK = "task", "Дело"

    class Priority(models.TextChoices):
        LOW = "low", "Низкий"
        NORMAL = "normal", "Обычный"
        HIGH = "high", "Высокий"

    class RecurrenceType(models.TextChoices):
        ONCE = "once", "Один раз"
        DAILY = "daily", "Каждый день"
        WEEKLY = "weekly", "По дням недели"
        MONTHLY = "monthly", "Каждый месяц"

    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_plan_items",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_daily_plan_items",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_daily_plan_items",
    )
    recurrence_parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="generated_occurrences",
    )
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    scheduled_date = models.DateField(db_index=True)
    scheduled_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.TASK)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    recurrence_type = models.CharField(
        max_length=10,
        choices=RecurrenceType.choices,
        default=RecurrenceType.ONCE,
    )
    recurrence_days = models.JSONField(default=list, blank=True)
    recurrence_end_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    via_voice = models.BooleanField(default=False)
    medicine_name = models.CharField(max_length=120, blank=True)
    medicine_dosage = models.CharField(max_length=120, blank=True)
    doctor_specialty = models.CharField(max_length=120, blank=True)
    doctor_address = models.CharField(max_length=220, blank=True)
    water_amount_ml = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Задача дня"
        verbose_name_plural = "Задачи дня"
        ordering = ["scheduled_date", "scheduled_time", "created_at"]
        indexes = [
            models.Index(fields=["subject", "scheduled_date", "is_completed"]),
        ]

    def __str__(self):
        return f"{self.subject} — {self.title} ({self.scheduled_date})"

    @property
    def time_label(self):
        if not self.scheduled_time:
            return "Без времени"
        return self.scheduled_time.strftime("%H:%M")

    @property
    def is_recurrence_template(self):
        return (
            self.recurrence_parent_id is None
            and self.recurrence_type != self.RecurrenceType.ONCE
        )

    @property
    def recurrence_label(self):
        if self.recurrence_type == self.RecurrenceType.WEEKLY and self.recurrence_days:
            weekday_map = {
                0: "пн",
                1: "вт",
                2: "ср",
                3: "чт",
                4: "пт",
                5: "сб",
                6: "вс",
            }
            labels = [weekday_map.get(day, str(day)) for day in self.recurrence_days]
            return f"Еженедельно: {', '.join(labels)}"
        return self.get_recurrence_type_display()

    @property
    def details(self):
        details = []
        if self.category == self.Category.MEDICATION:
            if self.medicine_name:
                details.append(self.medicine_name)
            if self.medicine_dosage:
                details.append(self.medicine_dosage)
        if self.category == self.Category.DOCTOR_VISIT:
            if self.doctor_specialty:
                details.append(self.doctor_specialty)
            if self.doctor_address:
                details.append(self.doctor_address)
        if self.category == self.Category.WATER and self.water_amount_ml:
            details.append(f"{self.water_amount_ml} мл")
        return details

    def occurs_on(self, target_date):
        if target_date < self.scheduled_date:
            return False
        if self.recurrence_end_date and target_date > self.recurrence_end_date:
            return False
        if self.recurrence_type == self.RecurrenceType.ONCE:
            return target_date == self.scheduled_date
        if self.recurrence_type == self.RecurrenceType.DAILY:
            return True
        if self.recurrence_type == self.RecurrenceType.WEEKLY:
            allowed_days = self.recurrence_days or [self.scheduled_date.weekday()]
            return target_date.weekday() in allowed_days
        if self.recurrence_type == self.RecurrenceType.MONTHLY:
            target_day = min(
                self.scheduled_date.day,
                calendar.monthrange(target_date.year, target_date.month)[1],
            )
            return target_date.day == target_day
        return False

    def build_occurrence(self, target_date):
        return DailyPlanItem(
            subject=self.subject,
            created_by=self.created_by,
            recurrence_parent=self,
            title=self.title,
            description=self.description,
            scheduled_date=target_date,
            scheduled_time=self.scheduled_time,
            duration_minutes=self.duration_minutes,
            category=self.category,
            priority=self.priority,
            recurrence_type=self.RecurrenceType.ONCE,
            via_voice=self.via_voice,
            medicine_name=self.medicine_name,
            medicine_dosage=self.medicine_dosage,
            doctor_specialty=self.doctor_specialty,
            doctor_address=self.doctor_address,
            water_amount_ml=self.water_amount_ml,
        )

    def mark_completed(self, actor):
        self.is_completed = True
        self.completed_at = timezone.now()
        self.completed_by = actor
        self.save(update_fields=["is_completed", "completed_at", "completed_by"])

    def mark_pending(self):
        self.is_completed = False
        self.completed_at = None
        self.completed_by = None
        self.save(update_fields=["is_completed", "completed_at", "completed_by"])


class CommunityPlace(models.Model):
    class Category(models.TextChoices):
        ACTIVE_LONGEVITY = "active_longevity", "Центр активного долголетия"
        CLINIC = "clinic", "Поликлиника"
        PHARMACY = "pharmacy", "Аптека"
        PARK = "park", "Парк"
        GROCERY = "grocery", "Продуктовые магазины"
        SOCIAL_CLUB = "social_club", "Клуб / кружок"
        REHAB = "rehab", "Реабилитация"
        SOCIAL_SERVICE = "social_service", "Социальные услуги"
        TRANSPORT = "transport", "Остановки транспорта"

    name = models.CharField(max_length=140)
    category = models.CharField(max_length=20, choices=Category.choices)
    city = models.CharField(max_length=80)
    address = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    website = models.URLField(blank=True)
    working_hours = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_featured = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Полезное место"
        verbose_name_plural = "Полезные места"
        ordering = ["city", "category", "name"]

    def __str__(self):
        return f"{self.name} ({self.city})"

    def get_distance_from_home(self, subject):
        settings_obj = getattr(subject, "location_sharing_settings", None)
        if (
            not settings_obj
            or settings_obj.home_latitude is None
            or settings_obj.home_longitude is None
            or self.latitude is None
            or self.longitude is None
        ):
            return None
        return round(
            _distance_km(
                (float(settings_obj.home_latitude), float(settings_obj.home_longitude)),
                (float(self.latitude), float(self.longitude)),
            ),
            1,
        )


class LocationSharingSettings(models.Model):
    subject = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location_sharing_settings",
    )
    tracking_enabled = models.BooleanField(default=True)
    share_with_family = models.BooleanField(default=True)
    allow_manual_updates = models.BooleanField(default=True)
    city = models.CharField(max_length=80, blank=True)
    home_address = models.CharField(max_length=220, blank=True)
    home_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    home_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    emergency_contact_notes = models.TextField(blank=True)
    max_absence_hours = models.PositiveSmallIntegerField(default=4)
    tracking_consent_given_at = models.DateTimeField(null=True, blank=True)
    last_shared_at = models.DateTimeField(null=True, blank=True)
    last_absence_alert_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Настройки геолокации"
        verbose_name_plural = "Настройки геолокации"

    def __str__(self):
        return f"Геолокация {self.subject}"

    def register_share(self):
        self.last_shared_at = timezone.now()
        self.save(update_fields=["last_shared_at"])

    def register_consent(self):
        if not self.tracking_consent_given_at:
            self.tracking_consent_given_at = timezone.now()
            self.save(update_fields=["tracking_consent_given_at"])

    def check_zone_crossing(self, ping):
        previous_ping = (
            self.subject.location_pings.filter(captured_at__lt=ping.captured_at)
            .order_by("-captured_at")
            .first()
        )
        if not previous_ping:
            return []

        events = []
        for zone in self.subject.safe_zones.all():
            was_inside = zone.contains(previous_ping.latitude, previous_ping.longitude)
            is_inside = zone.contains(ping.latitude, ping.longitude)
            if was_inside != is_inside:
                events.append(
                    {
                        "zone": zone,
                        "event_type": "entered" if is_inside else "left",
                    }
                )
        return events

    def mark_absence_alerted(self):
        self.last_absence_alert_at = timezone.now()
        self.save(update_fields=["last_absence_alert_at"])


class LocationPing(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Вручную"
        PHONE = "phone", "Телефон"
        WEARABLE = "wearable", "Браслет"

    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location_pings",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_location_pings",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.MANUAL)
    note = models.CharField(max_length=140, blank=True)
    is_emergency = models.BooleanField(default=False, db_index=True)
    captured_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Точка геолокации"
        verbose_name_plural = "Точки геолокации"
        ordering = ["-captured_at"]
        indexes = [
            models.Index(fields=["subject", "-captured_at"]),
        ]

    def __str__(self):
        return f"{self.subject} @ {self.latitude}, {self.longitude}"


class SafeZone(models.Model):
    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="safe_zones",
    )
    name = models.CharField(max_length=120)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius_meters = models.PositiveIntegerField(default=300)
    is_home = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Безопасная зона"
        verbose_name_plural = "Безопасные зоны"
        ordering = ["-is_home", "name"]

    def __str__(self):
        return f"{self.name} ({self.subject})"

    def contains(self, latitude, longitude):
        return _distance_km(
            (float(self.latitude), float(self.longitude)),
            (float(latitude), float(longitude)),
        ) * 1000 <= self.radius_meters


class WearableDevice(models.Model):
    class Provider(models.TextChoices):
        XIAOMI = "xiaomi", "Xiaomi / Mi Band"
        HUAWEI = "huawei", "Huawei"
        SAMSUNG = "samsung", "Samsung"
        APPLE = "apple", "Apple Health"
        GOOGLE_FIT = "google_fit", "Google Fit"
        FITBIT = "fitbit", "Fitbit"
        OTHER = "other", "Другое"

    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wearable_devices",
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    nickname = models.CharField(max_length=80)
    external_id = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Фитнес-браслет"
        verbose_name_plural = "Фитнес-браслеты"
        ordering = ["-is_active", "nickname"]

    def __str__(self):
        return f"{self.nickname} ({self.get_provider_display()})"

    def register_sync(self):
        self.last_synced_at = timezone.now()
        self.save(update_fields=["last_synced_at"])


class WearableDailySummary(models.Model):
    class SleepQuality(models.TextChoices):
        POOR = "poor", "Плохой"
        FAIR = "fair", "Удовлетворительный"
        GOOD = "good", "Хороший"
        EXCELLENT = "excellent", "Отличный"

    device = models.ForeignKey(
        WearableDevice,
        on_delete=models.CASCADE,
        related_name="daily_summaries",
    )
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imported_wearable_summaries",
    )
    summary_date = models.DateField(db_index=True)
    steps = models.PositiveIntegerField(default=0)
    average_heart_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    heart_rate_min = models.PositiveSmallIntegerField(null=True, blank=True)
    heart_rate_max = models.PositiveSmallIntegerField(null=True, blank=True)
    sleep_hours = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    sleep_quality = models.CharField(
        max_length=10,
        choices=SleepQuality.choices,
        blank=True,
    )
    deep_sleep_hours = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    light_sleep_hours = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    active_minutes = models.PositiveIntegerField(null=True, blank=True)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    calories_kcal = models.PositiveIntegerField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Сводка браслета"
        verbose_name_plural = "Сводки браслета"
        unique_together = [("device", "summary_date")]
        ordering = ["-summary_date", "-synced_at"]

    def __str__(self):
        return f"{self.device} — {self.summary_date}"


class FavoritePlace(models.Model):
    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_places",
    )
    place = models.ForeignKey(
        CommunityPlace,
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Избранное место"
        verbose_name_plural = "Избранные места"
        unique_together = [("subject", "place")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} → {self.place}"


class TaskReminder(models.Model):
    task = models.ForeignKey(
        DailyPlanItem,
        on_delete=models.CASCADE,
        related_name="reminders",
    )
    remind_before_minutes = models.PositiveIntegerField(default=60)
    sent = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Напоминание по задаче"
        verbose_name_plural = "Напоминания по задачам"
        unique_together = [("task", "remind_before_minutes")]
        ordering = ["remind_before_minutes"]

    def __str__(self):
        return f"{self.task} — за {self.remind_before_minutes} мин"

    def mark_sent(self):
        self.sent = True
        self.sent_at = timezone.now()
        self.save(update_fields=["sent", "sent_at"])
