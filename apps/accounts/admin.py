from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile, MagicLink


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Профиль"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ["email", "get_full_name", "role", "onboarding_completed", "is_active", "date_joined"]
    list_filter = ["role", "onboarding_completed", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["-date_joined"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Janynda", {"fields": ("role", "phone", "avatar", "timezone", "onboarding_completed")}),
    )


@admin.register(MagicLink)
class MagicLinkAdmin(admin.ModelAdmin):
    list_display = ["user", "purpose", "is_used", "is_valid", "created_at", "expires_at"]
    list_filter = ["purpose", "is_used"]
    search_fields = ["user__email"]
    ordering = ["-created_at"]
    readonly_fields = ["token", "created_at"]
