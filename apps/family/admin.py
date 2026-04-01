from django.contrib import admin
from .models import FamilyGroup, FamilyMembership, FamilyInvite


class FamilyMembershipInline(admin.TabularInline):
    model = FamilyMembership
    extra = 0
    fields = ["observer", "subject", "subject_name", "relation", "can_view_metrics"]


@admin.register(FamilyGroup)
class FamilyGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "invite_code", "created_at"]
    search_fields = ["name", "owner__email", "invite_code"]
    inlines = [FamilyMembershipInline]


@admin.register(FamilyMembership)
class FamilyMembershipAdmin(admin.ModelAdmin):
    list_display = ["observer", "subject_name", "subject", "relation", "group", "is_pending"]
    list_filter = ["relation"]
    search_fields = ["observer__email", "subject__email", "subject_name"]


@admin.register(FamilyInvite)
class FamilyInviteAdmin(admin.ModelAdmin):
    list_display = ["email", "group", "is_accepted", "is_valid", "created_at"]
    list_filter = ["is_accepted"]
    search_fields = ["email"]
