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
