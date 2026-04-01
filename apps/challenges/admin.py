from django.contrib import admin
from .models import Challenge, ChallengeParticipant


class ChallengeParticipantInline(admin.TabularInline):
    model = ChallengeParticipant
    extra = 0
    readonly_fields = ["current_value", "streak_days", "progress_pct", "joined_at"]


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ["title", "group", "challenge_type", "status", "start_date", "end_date", "is_active"]
    list_filter = ["challenge_type", "status"]
    search_fields = ["title", "group__name"]
    inlines = [ChallengeParticipantInline]


@admin.register(ChallengeParticipant)
class ChallengeParticipantAdmin(admin.ModelAdmin):
    list_display = ["user", "challenge", "current_value", "progress_pct", "streak_days", "is_winner"]
    list_filter = ["is_winner"]
    search_fields = ["user__email", "challenge__title"]
