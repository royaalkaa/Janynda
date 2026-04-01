from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class MetricType(models.TextChoices):
    BLOOD_PRESSURE = "blood_pressure", "Кровяное давление"
    HEART_RATE = "heart_rate", "Сердечный ритм"
    STEPS = "steps", "Шаги"
    WEIGHT = "weight", "Вес"
    TEMPERATURE = "temperature", "Температура"
    MOOD = "mood", "Самочувствие"
    WATER = "water", "Вода"
    SLEEP = "sleep", "Сон"
    BLOOD_SUGAR = "blood_sugar", "Сахар в крови"
    OXYGEN = "oxygen", "Кислород (SpO2)"


# ---------------------------------------------------------------------------
# Пороговые значения по умолчанию (зависят от возраста)
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS = {
    MetricType.BLOOD_PRESSURE: {
        # {"systolic": ..., "diastolic": ...}
        "young": {"warn_hi_sys": 130, "crit_hi_sys": 150, "warn_lo_sys": 90, "crit_lo_sys": 80,
                  "warn_hi_dia": 85, "crit_hi_dia": 100, "warn_lo_dia": 60, "crit_lo_dia": 50},
        "middle": {"warn_hi_sys": 135, "crit_hi_sys": 160, "warn_lo_sys": 90, "crit_lo_sys": 80,
                   "warn_hi_dia": 88, "crit_hi_dia": 105, "warn_lo_dia": 60, "crit_lo_dia": 50},
        "elder": {"warn_hi_sys": 140, "crit_hi_sys": 180, "warn_lo_sys": 95, "crit_lo_sys": 85,
                  "warn_hi_dia": 90, "crit_hi_dia": 110, "warn_lo_dia": 60, "crit_lo_dia": 50},
    },
    MetricType.HEART_RATE: {
        "all": {"warn_lo": 50, "crit_lo": 40, "warn_hi": 100, "crit_hi": 130},
    },
    MetricType.OXYGEN: {
        "all": {"warn_lo": 94, "crit_lo": 90},
    },
    MetricType.TEMPERATURE: {
        "all": {"warn_hi": 37.5, "crit_hi": 38.5},
    },
    MetricType.BLOOD_SUGAR: {
        "all": {"warn_hi": 7.0, "crit_hi": 11.0, "warn_lo": 3.9, "crit_lo": 3.0},
    },
}


class ThresholdConfig(models.Model):
    """
    Пороговые значения метрики для конкретного субъекта.
    Создаются автоматически при добавлении члена семьи по возрасту.
    """

    subject = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="thresholds"
    )
    metric_type = models.CharField(max_length=20, choices=MetricType.choices)
    config = models.JSONField(default=dict)  # пороги в формате DEFAULT_THRESHOLDS
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Порог метрики"
        verbose_name_plural = "Пороги метрик"
        unique_together = [("subject", "metric_type")]

    def __str__(self):
        return f"{self.subject} — {self.metric_type}"


class MetricRecord(models.Model):
    """
    Универсальная запись любой метрики здоровья.
    Данные хранятся в value_json — схема зависит от metric_type.

    Схемы value_json:
      blood_pressure : {"systolic": 120, "diastolic": 80, "pulse": 70}
      heart_rate     : {"bpm": 72}
      steps          : {"steps": 8500, "distance_m": 6120, "calories": 320}
      weight         : {"kg": 72.5}
      temperature    : {"celsius": 36.6}
      mood           : {"score": 4, "note": "хорошее"}  (1-5)
      water          : {"ml": 1500}
      sleep          : {"hours": 7.5, "quality": 4}
      blood_sugar    : {"mmol": 5.2}
      oxygen         : {"pct": 97}
    """

    class Source(models.TextChoices):
        MANUAL = "manual", "Вручную"
        MAGIC_LINK = "magic_link", "Magic Link"
        AUTO = "auto", "Автоматически"

    subject = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="metric_records"
    )
    metric_type = models.CharField(max_length=20, choices=MetricType.choices)
    value_json = models.JSONField()
    source = models.CharField(max_length=15, choices=Source.choices, default=Source.MANUAL)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Запись метрики"
        verbose_name_plural = "Записи метрик"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["subject", "metric_type", "-recorded_at"]),
        ]

    def __str__(self):
        return f"{self.subject} — {self.metric_type} — {self.recorded_at:%d.%m.%Y %H:%M}"

    def get_severity(self):
        """
        Вычисляет уровень серьёзности: 'normal', 'warning', 'critical'.
        Использует ThresholdConfig или DEFAULT_THRESHOLDS.
        """
        try:
            tc = ThresholdConfig.objects.get(subject=self.subject, metric_type=self.metric_type)
            thresholds = tc.config
        except ThresholdConfig.DoesNotExist:
            age = getattr(getattr(self.subject, "profile", None), "age", None)
            age_key = _get_age_key(age)
            thresholds = DEFAULT_THRESHOLDS.get(self.metric_type, {}).get(
                age_key, DEFAULT_THRESHOLDS.get(self.metric_type, {}).get("all", {})
            )

        return _evaluate_severity(self.metric_type, self.value_json, thresholds)

    def get_display_value(self):
        """Возвращает строку для отображения."""
        v = self.value_json
        if self.metric_type == MetricType.BLOOD_PRESSURE:
            return f"{v.get('systolic')}/{v.get('diastolic')}"
        if self.metric_type == MetricType.HEART_RATE:
            return f"{v.get('bpm')} уд/мин"
        if self.metric_type == MetricType.STEPS:
            return f"{v.get('steps', 0):,} шагов"
        if self.metric_type == MetricType.WEIGHT:
            return f"{v.get('kg')} кг"
        if self.metric_type == MetricType.TEMPERATURE:
            return f"{v.get('celsius')} °C"
        if self.metric_type == MetricType.MOOD:
            return f"{v.get('score')}/5"
        if self.metric_type == MetricType.WATER:
            return f"{v.get('ml')} мл"
        if self.metric_type == MetricType.SLEEP:
            return f"{v.get('hours')} ч"
        if self.metric_type == MetricType.BLOOD_SUGAR:
            return f"{v.get('mmol')} ммоль/л"
        if self.metric_type == MetricType.OXYGEN:
            return f"{v.get('pct')} %"
        return str(v)

    def get_unit(self):
        units = {
            MetricType.BLOOD_PRESSURE: "мм рт.ст.",
            MetricType.HEART_RATE: "уд/мин",
            MetricType.STEPS: "шагов",
            MetricType.WEIGHT: "кг",
            MetricType.TEMPERATURE: "°C",
            MetricType.MOOD: "/5",
            MetricType.WATER: "мл",
            MetricType.SLEEP: "ч",
            MetricType.BLOOD_SUGAR: "ммоль/л",
            MetricType.OXYGEN: "%",
        }
        return units.get(self.metric_type, "")


def _get_age_key(age):
    if age is None:
        return "middle"
    if age < 55:
        return "young"
    if age < 70:
        return "middle"
    return "elder"


def _evaluate_severity(metric_type, value_json, thresholds):
    if not thresholds:
        return "normal"

    if metric_type == MetricType.BLOOD_PRESSURE:
        sys_val = value_json.get("systolic", 0)
        dia_val = value_json.get("diastolic", 0)
        if sys_val >= thresholds.get("crit_hi_sys", 999) or dia_val >= thresholds.get("crit_hi_dia", 999):
            return "critical"
        if sys_val <= thresholds.get("crit_lo_sys", 0) or dia_val <= thresholds.get("crit_lo_dia", 0):
            return "critical"
        if sys_val >= thresholds.get("warn_hi_sys", 999) or dia_val >= thresholds.get("warn_hi_dia", 999):
            return "warning"
        if sys_val <= thresholds.get("warn_lo_sys", 0) or dia_val <= thresholds.get("warn_lo_dia", 0):
            return "warning"
        return "normal"

    # Для одиночных числовых метрик
    val_map = {
        MetricType.HEART_RATE: value_json.get("bpm", 0),
        MetricType.OXYGEN: value_json.get("pct", 100),
        MetricType.TEMPERATURE: value_json.get("celsius", 36.0),
        MetricType.BLOOD_SUGAR: value_json.get("mmol", 5.0),
    }
    val = val_map.get(metric_type)
    if val is None:
        return "normal"

    if val >= thresholds.get("crit_hi", 9999) or val <= thresholds.get("crit_lo", -9999):
        return "critical"
    if val >= thresholds.get("warn_hi", 9999) or val <= thresholds.get("warn_lo", -9999):
        return "warning"
    return "normal"


class HealthGoal(models.Model):
    """Цель по метрике (например: 8000 шагов/день)."""

    class Period(models.TextChoices):
        DAILY = "daily", "В день"
        WEEKLY = "weekly", "В неделю"

    subject = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="health_goals"
    )
    metric_type = models.CharField(max_length=20, choices=MetricType.choices)
    target_value = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.CharField(max_length=10, choices=Period.choices, default=Period.DAILY)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Цель здоровья"
        verbose_name_plural = "Цели здоровья"
        unique_together = [("subject", "metric_type", "period")]

    def __str__(self):
        return f"{self.subject} → {self.metric_type} {self.target_value} {self.period}"
