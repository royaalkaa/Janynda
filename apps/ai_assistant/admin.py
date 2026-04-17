from django.contrib import admin
from .models import AIComment, AIConversation, AIMessage


class AIMessageInline(admin.TabularInline):
    model = AIMessage
    extra = 0
    readonly_fields = ["role", "content", "tokens", "created_at"]


@admin.register(AIComment)
class AICommentAdmin(admin.ModelAdmin):
    list_display = ["subject", "is_fallback", "is_valid", "tokens_used", "generated_at", "expires_at"]
    list_filter = ["is_fallback"]
    search_fields = ["subject__email"]
    ordering = ["-generated_at"]


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ["user", "context_subject", "total_tokens", "started_at", "last_message_at"]
    search_fields = ["user__email"]
    inlines = [AIMessageInline]
