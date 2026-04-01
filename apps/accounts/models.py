import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.conf import settings


class User(AbstractUser):
    """Расширенный пользователь. Может быть наблюдающим, субъектом или обоими."""

    class Role(models.TextChoices):
        OBSERVER = "observer", "Наблюдающий"
        SUBJECT = "subject", "Субъект"
        BOTH = "both", "Оба"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.BOTH)
    timezone = models.CharField(max_length=50, default="Asia/Almaty")
    onboarding_completed = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def is_observer(self):
        return self.role in (self.Role.OBSERVER, self.Role.BOTH)

    @property
    def is_subject(self):
        return self.role in (self.Role.SUBJECT, self.Role.BOTH)

    def get_display_name(self):
        return self.get_full_name() or self.email.split("@")[0]


class UserProfile(models.Model):
    """Медицинский профиль пользователя."""

    class Gender(models.TextChoices):
        MALE = "male", "Мужской"
        FEMALE = "female", "Женский"
        OTHER = "other", "Другой"

    class Condition(models.TextChoices):
        HYPERTENSION = "hypertension", "Гипертония"
        DIABETES = "diabetes", "Диабет"
        HEART_DISEASE = "heart_disease", "Болезнь сердца"
        NONE = "none", "Нет"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    blood_type = models.CharField(max_length=5, blank=True)
    chronic_conditions = models.JSONField(default=list)  # [Condition.HYPERTENSION, ...]
    emergency_contact = models.CharField(max_length=100, blank=True)
    medical_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Профиль"
        verbose_name_plural = "Профили"

    def __str__(self):
        return f"Профиль {self.user}"

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = timezone.now().date()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def bmi(self):
        if self.height_cm and self.weight_kg:
            h = float(self.height_cm) / 100
            return round(float(self.weight_kg) / (h * h), 1)
        return None


class MagicLink(models.Model):
    """Токен для входа без пароля — для пожилых субъектов."""

    class Purpose(models.TextChoices):
        SUBJECT_ENTRY = "subject_entry", "Ввод данных субъектом"
        FAMILY_INVITE = "family_invite", "Приглашение в семью"

    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="magic_links")
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.SUBJECT_ENTRY)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    extra_data = models.JSONField(default=dict)  # доп. данные (membership_id и т.д.)

    class Meta:
        verbose_name = "Magic Link"
        verbose_name_plural = "Magic Links"
        ordering = ["-created_at"]

    def __str__(self):
        return f"MagicLink({self.user}, {self.purpose})"

    @property
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    @classmethod
    def create_for_user(cls, user, purpose, days=None, extra_data=None):
        from datetime import timedelta
        ttl = days or settings.MAGIC_LINK_TTL_DAYS
        return cls.objects.create(
            user=user,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(days=ttl),
            extra_data=extra_data or {},
        )
