from django.db import models
from django.utils import timezone


class Challenge(models.Model):
    """Семейный челлендж по здоровью."""

    class ChallengeType(models.TextChoices):
        STEPS_TOTAL = "steps_total", "Сумма шагов за период"
        STEPS_DAILY = "steps_daily", "Ежедневные шаги"
        BP_STREAK = "bp_streak", "Дни с нормальным давлением подряд"
        WATER_DAILY = "water_daily", "Ежедневная норма воды"
        MOOD_STREAK = "mood_streak", "Дни с хорошим самочувствием"

    class Status(models.TextChoices):
        ACTIVE = "active", "Активен"
        COMPLETED = "completed", "Завершён"
        CANCELLED = "cancelled", "Отменён"

    group = models.ForeignKey(
        "family.FamilyGroup", on_delete=models.CASCADE, related_name="challenges"
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="created_challenges"
    )
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    challenge_type = models.CharField(max_length=20, choices=ChallengeType.choices)
    target_value = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Челлендж"
        verbose_name_plural = "Челленджи"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.group})"

    @property
    def is_active(self):
        today = timezone.now().date()
        return self.status == self.Status.ACTIVE and self.start_date <= today <= self.end_date

    @property
    def days_left(self):
        today = timezone.now().date()
        return max(0, (self.end_date - today).days)

    @property
    def progress_pct(self):
        today = timezone.now().date()
        total = (self.end_date - self.start_date).days or 1
        elapsed = (today - self.start_date).days
        return min(100, round(elapsed / total * 100))

    def get_unit_label(self):
        units = {
            self.ChallengeType.STEPS_TOTAL: "шагов",
            self.ChallengeType.STEPS_DAILY: "шагов/день",
            self.ChallengeType.BP_STREAK: "дней подряд",
            self.ChallengeType.WATER_DAILY: "мл/день",
            self.ChallengeType.MOOD_STREAK: "дней подряд",
        }
        return units.get(self.challenge_type, "")


class ChallengeParticipant(models.Model):
    """Участник челленджа с текущим прогрессом."""

    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="challenge_participations")
    current_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    streak_days = models.PositiveSmallIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_winner = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Участник"
        verbose_name_plural = "Участники"
        unique_together = [("challenge", "user")]
        ordering = ["-current_value"]

    def __str__(self):
        return f"{self.user} в «{self.challenge.title}»"

    @property
    def progress_pct(self):
        target = float(self.challenge.target_value)
        if not target:
            return 0
        return min(100, round(float(self.current_value) / target * 100))

    @property
    def is_goal_reached(self):
        return float(self.current_value) >= float(self.challenge.target_value)
