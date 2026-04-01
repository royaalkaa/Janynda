from django.contrib import admin
from .models import Notification, NotificationSettings


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "title", "severity", "category", "is_read", "created_at"]
    list_filter = ["severity", "category", "is_read"]
    search_fields = ["recipient__email", "title"]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ["user", "email_enabled", "reminder_time", "health_alerts", "weather_alerts"]
    search_fields = ["user__email"]
