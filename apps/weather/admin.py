from django.contrib import admin
from .models import WeatherCache


@admin.register(WeatherCache)
class WeatherCacheAdmin(admin.ModelAdmin):
    list_display = ["city", "temperature_c", "aqi", "is_dangerous_air", "fetched_at", "is_fresh"]
    list_filter = ["is_dangerous_air", "weather_main"]
    search_fields = ["city"]
    ordering = ["-fetched_at"]
    readonly_fields = ["fetched_at"]
