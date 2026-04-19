from django.db import models
from django.utils import timezone


class AIComment(models.Model):
    """
    Кешированный AI-комментарий по состоянию здоровья субъекта.
    Один актуальный комментарий на субъекта, TTL 24 часа.
    Пересоздаётся если данные изменились.
    """

    subject = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="ai_comments"
    )
    content = models.TextField()
    context_hash = models.CharField(max_length=64, blank=True)  # hash входных данных
    tokens_used = models.PositiveIntegerField(default=0)
    is_fallback = models.BooleanField(default=False)  # сгенерирован без AI (шаблон)
    generated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = "AI комментарий"
        verbose_name_plural = "AI комментарии"
        ordering = ["-generated_at"]
        get_latest_by = "generated_at"

    def __str__(self):
        return f"AIComment({self.subject}, {'fallback' if self.is_fallback else 'ai'})"

    @property
    def is_valid(self):
        return timezone.now() < self.expires_at

    @classmethod
    def get_current(cls, subject):
        """Возвращает актуальный комментарий или None."""
        try:
            comment = cls.objects.filter(subject=subject).latest()
            return comment if comment.is_valid else None
        except cls.DoesNotExist:
            return None


class AIConversation(models.Model):
    """История чата с AI-ассистентом (только Premium)."""

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="ai_conversations"
    )
    context_subject = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_conversations_about",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)
    total_tokens = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "AI разговор"
        verbose_name_plural = "AI разговоры"
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"Chat({self.user}, {self.started_at:%d.%m.%Y})"


class AIMessage(models.Model):
    """Сообщение в AI-чате."""

    class Role(models.TextChoices):
        USER = "user", "Пользователь"
        ASSISTANT = "assistant", "Ассистент"
        SYSTEM = "system", "Система"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "AI сообщение"
        verbose_name_plural = "AI сообщения"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"


class VoiceCommandLog(models.Model):
    class ActionType(models.TextChoices):
        ANSWER = "answer", "РћС‚РІРµС‚"
        PLAN_QUERY = "plan_query", "Р—Р°РїСЂРѕСЃ РїР»Р°РЅР°"
        PLAN_COMPLETE = "plan_complete", "РћС‚РјРµС‚РєР° РїР»Р°РЅР°"
        MEDICATION_LOG = "medication_log", "Р›РµРєР°СЂСЃС‚РІРѕ"
        DOCTOR_LOG = "doctor_log", "Р’РёР·РёС‚ Рє РІСЂР°С‡Сѓ"
        METRIC_LOG = "metric_log", "Р›РѕРі РјРµС‚СЂРёРєРё"
        REMINDER = "reminder", "РќР°РїРѕРјРёРЅР°РЅРёРµ"
        CANCELLED = "cancelled", "РћС‚РјРµРЅРµРЅРѕ"
        UNSUPPORTED = "unsupported", "РќРµ СЂР°СЃРїРѕР·РЅР°РЅРѕ"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="voice_command_logs",
    )
    subject = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="voice_command_subject_logs",
    )
    transcript = models.TextField()
    response_text = models.TextField()
    action_type = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        default=ActionType.ANSWER,
    )
    payload = models.JSONField(default=dict, blank=True)
    requires_confirmation = models.BooleanField(default=False)
    confirmed = models.BooleanField(default=False)
    is_system_message = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Р“РѕР»РѕСЃРѕРІР°СЏ РєРѕРјР°РЅРґР°"
        verbose_name_plural = "Р“РѕР»РѕСЃРѕРІС‹Рµ РєРѕРјР°РЅРґС‹"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} -> {self.action_type} ({self.created_at:%d.%m.%Y %H:%M})"

    def mark_read(self):
        if self.is_read:
            return
        self.is_read = True
        self.save(update_fields=["is_read"])
