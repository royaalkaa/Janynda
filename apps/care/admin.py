from django.contrib import admin

from .models import (
    CommunityPlace,
    DailyPlanItem,
    FavoritePlace,
    LocationPing,
    LocationSharingSettings,
    SafeZone,
    TaskReminder,
    WearableDailySummary,
    WearableDevice,
)


@admin.register(DailyPlanItem)
class DailyPlanItemAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "subject",
        "scheduled_date",
        "scheduled_time",
        "category",
        "recurrence_type",
        "is_completed",
    ]
    list_filter = ["category", "priority", "recurrence_type", "is_completed", "scheduled_date"]
    search_fields = ["title", "subject__email", "description", "medicine_name", "doctor_specialty"]


@admin.register(CommunityPlace)
class CommunityPlaceAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "category", "is_featured"]
    list_filter = ["city", "category", "is_featured"]
    search_fields = ["name", "city", "address"]


@admin.register(LocationSharingSettings)
class LocationSharingSettingsAdmin(admin.ModelAdmin):
    list_display = [
        "subject",
        "tracking_enabled",
        "share_with_family",
        "allow_manual_updates",
        "city",
        "last_shared_at",
    ]
    list_filter = ["tracking_enabled", "share_with_family", "allow_manual_updates", "city"]
    search_fields = ["subject__email", "city", "home_address"]


@admin.register(LocationPing)
class LocationPingAdmin(admin.ModelAdmin):
    list_display = ["subject", "latitude", "longitude", "source", "is_emergency", "captured_at"]
    list_filter = ["source", "is_emergency", "captured_at"]
    search_fields = ["subject__email", "note"]


@admin.register(WearableDevice)
class WearableDeviceAdmin(admin.ModelAdmin):
    list_display = ["nickname", "subject", "provider", "is_active", "last_synced_at"]
    list_filter = ["provider", "is_active"]
    search_fields = ["nickname", "subject__email", "external_id"]


@admin.register(WearableDailySummary)
class WearableDailySummaryAdmin(admin.ModelAdmin):
    list_display = [
        "device",
        "summary_date",
        "steps",
        "average_heart_rate",
        "heart_rate_min",
        "heart_rate_max",
        "sleep_hours",
        "active_minutes",
    ]
    list_filter = ["summary_date", "device__provider"]
    search_fields = ["device__nickname", "device__subject__email"]


@admin.register(TaskReminder)
class TaskReminderAdmin(admin.ModelAdmin):
    list_display = ["task", "remind_before_minutes", "sent", "sent_at"]
    list_filter = ["sent"]
    search_fields = ["task__title", "task__subject__email"]


@admin.register(SafeZone)
class SafeZoneAdmin(admin.ModelAdmin):
    list_display = ["name", "subject", "radius_meters", "is_home"]
    list_filter = ["is_home"]
    search_fields = ["name", "subject__email"]


@admin.register(FavoritePlace)
class FavoritePlaceAdmin(admin.ModelAdmin):
    list_display = ["subject", "place", "created_at"]
    search_fields = ["subject__email", "place__name"]
