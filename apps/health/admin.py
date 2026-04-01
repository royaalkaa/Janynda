from django.contrib import admin
from .models import MetricRecord, ThresholdConfig, HealthGoal


@admin.register(MetricRecord)
class MetricRecordAdmin(admin.ModelAdmin):
    list_display = ["subject", "metric_type", "get_display_value", "source", "recorded_at"]
    list_filter = ["metric_type", "source"]
    search_fields = ["subject__email"]
    ordering = ["-recorded_at"]
    date_hierarchy = "recorded_at"


@admin.register(ThresholdConfig)
class ThresholdConfigAdmin(admin.ModelAdmin):
    list_display = ["subject", "metric_type", "updated_at"]
    list_filter = ["metric_type"]
    search_fields = ["subject__email"]


@admin.register(HealthGoal)
class HealthGoalAdmin(admin.ModelAdmin):
    list_display = ["subject", "metric_type", "target_value", "period", "is_active"]
    list_filter = ["metric_type", "period", "is_active"]
    search_fields = ["subject__email"]
