from django.db import models
from django.utils import timezone


class WeatherCache(models.Model):
    """Кешированные данные погоды и качества воздуха (OpenWeatherMap)."""

    class AQILevel(models.IntegerChoices):
        GOOD = 1, "Хорошо"
        FAIR = 2, "Удовлетворительно"
        MODERATE = 3, "Умеренно"
        POOR = 4, "Плохо"
        VERY_POOR = 5, "Очень плохо"

    city = models.CharField(max_length=100, db_index=True)
    country = models.CharField(max_length=5, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    # Основные данные
    temperature_c = models.DecimalField(max_digits=5, decimal_places=2)
    feels_like_c = models.DecimalField(max_digits=5, decimal_places=2)
    humidity_pct = models.PositiveSmallIntegerField()
    wind_speed_ms = models.DecimalField(max_digits=5, decimal_places=2)
    pressure_hpa = models.PositiveIntegerField(default=1013)
    weather_main = models.CharField(max_length=50)    # Clear, Rain, Snow...
    weather_desc = models.CharField(max_length=200)
    weather_icon = models.CharField(max_length=10, blank=True)
    uv_index = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    visibility_m = models.PositiveIntegerField(null=True, blank=True)

    # Качество воздуха (AQI)
    aqi = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=AQILevel.choices
    )
    pm25 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    pm10 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    no2 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    # Вычисленные флаги
    is_dangerous_air = models.BooleanField(default=False)  # AQI >= 4
    is_extreme_heat = models.BooleanField(default=False)   # > 38°C
    is_extreme_cold = models.BooleanField(default=False)   # < -20°C

    fetched_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Погодный кеш"
        verbose_name_plural = "Погодный кеш"
        ordering = ["-fetched_at"]
        get_latest_by = "fetched_at"

    def __str__(self):
        return f"{self.city} — {self.temperature_c}°C — AQI:{self.aqi}"

    def save(self, *args, **kwargs):
        self.is_dangerous_air = bool(self.aqi and self.aqi >= 4)
        self.is_extreme_heat = float(self.temperature_c) > 38
        self.is_extreme_cold = float(self.temperature_c) < -20
        super().save(*args, **kwargs)

    @property
    def aqi_label(self):
        if not self.aqi:
            return "—"
        return self.AQILevel(self.aqi).label if self.aqi in self.AQILevel.values else "—"

    @property
    def aqi_color_class(self):
        colors = {1: "success", 2: "success", 3: "warning", 4: "danger", 5: "danger"}
        return colors.get(self.aqi, "secondary")

    @property
    def is_fresh(self):
        """Данные получены менее 30 минут назад."""
        from django.conf import settings
        ttl = getattr(settings, "WEATHER_CACHE_TTL_SECONDS", 1800)
        age = (timezone.now() - self.fetched_at).total_seconds()
        return age < ttl

    def get_walk_recommendation(self):
        """Краткая рекомендация по прогулке на основе погоды."""
        if self.is_dangerous_air:
            return "danger", "Воздух загрязнён — прогулки не рекомендуются"
        if self.is_extreme_heat:
            return "warning", "Слишком жарко — выходите ранним утром или вечером"
        if self.is_extreme_cold:
            return "warning", "Очень холодно — оденьтесь тепло или останьтесь дома"
        if self.weather_main in ("Rain", "Drizzle", "Thunderstorm", "Snow"):
            return "warning", "Осадки — возьмите зонт или оставайтесь дома"
        return "success", "Хорошие условия для прогулки"
