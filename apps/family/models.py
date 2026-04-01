import uuid
from django.db import models
from django.utils import timezone


class FamilyGroup(models.Model):
    """Семейная группа. Один owner, несколько участников."""

    owner = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="owned_groups"
    )
    name = models.CharField(max_length=100)
    invite_code = models.CharField(max_length=12, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Семейная группа"
        verbose_name_plural = "Семейные группы"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.invite_code:
            self.invite_code = self._generate_invite_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_invite_code():
        import random, string
        chars = string.ascii_uppercase + string.digits
        while True:
            code = "".join(random.choices(chars, k=8))
            if not FamilyGroup.objects.filter(invite_code=code).exists():
                return code

    def get_members(self):
        return self.memberships.select_related("subject", "observer")


class FamilyMembership(models.Model):
    """
    Связь observer → subject внутри группы.
    Subject может ещё не быть зарегистрирован (pending invite).
    """

    class Relation(models.TextChoices):
        MOTHER = "mother", "Мама"
        FATHER = "father", "Папа"
        GRANDMOTHER = "grandmother", "Бабушка"
        GRANDFATHER = "grandfather", "Дедушка"
        SPOUSE = "spouse", "Супруг(а)"
        CHILD = "child", "Ребёнок"
        SIBLING = "sibling", "Брат/Сестра"
        OTHER = "other", "Другой"

    group = models.ForeignKey(FamilyGroup, on_delete=models.CASCADE, related_name="memberships")
    observer = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="observing"
    )
    subject = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="being_observed",
    )
    # Данные субъекта до регистрации
    subject_name = models.CharField(max_length=100)
    subject_email = models.EmailField(blank=True, null=True)
    relation = models.CharField(max_length=20, choices=Relation.choices, default=Relation.OTHER)

    # Доступ
    can_view_metrics = models.BooleanField(default=True)
    can_view_location = models.BooleanField(default=False)

    # Magic link для субъекта (чтобы войти без пароля)
    magic_link = models.OneToOneField(
        "accounts.MagicLink",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="membership",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Участник семьи"
        verbose_name_plural = "Участники семьи"
        unique_together = [("group", "observer", "subject_email")]

    def __str__(self):
        subject_str = str(self.subject) if self.subject else self.subject_name
        return f"{self.observer} наблюдает за {subject_str}"

    @property
    def is_pending(self):
        """Субъект ещё не зарегистрирован."""
        return self.subject is None

    def get_subject_display_name(self):
        if self.subject:
            return self.subject.get_display_name()
        return self.subject_name

    def get_relation_display_name(self):
        return self.get_relation_display()


class FamilyInvite(models.Model):
    """Приглашение по email для будущего субъекта."""

    group = models.ForeignKey(FamilyGroup, on_delete=models.CASCADE, related_name="invites")
    membership = models.OneToOneField(
        FamilyMembership, on_delete=models.CASCADE, related_name="invite"
    )
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "Приглашение"
        verbose_name_plural = "Приглашения"

    def __str__(self):
        return f"Invite → {self.email}"

    @property
    def is_valid(self):
        return not self.is_accepted and timezone.now() < self.expires_at
