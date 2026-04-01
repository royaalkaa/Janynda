from datetime import time

from django.conf import settings
from django.utils.text import slugify

from apps.family.models import FamilyGroup, FamilyMembership
from apps.health.models import HealthGoal, MetricType
from apps.notifications.models import NotificationSettings

from .models import MagicLink, User


def generate_unique_username(base_value: str) -> str:
    base = slugify(base_value) or "user"
    username = base[:140]
    index = 1
    while User.objects.filter(username=username).exists():
        index += 1
        username = f"{base[:130]}-{index}"
    return username


def generate_placeholder_email(display_name: str) -> str:
    base = slugify(display_name) or "member"
    email = f"{base}@placeholder.janynda.local"
    index = 1
    while User.objects.filter(email=email).exists():
        index += 1
        email = f"{base}-{index}@placeholder.janynda.local"
    return email


def upgrade_user_role_to_subject(user: User) -> User:
    if user.role == User.Role.OBSERVER:
        user.role = User.Role.BOTH
        user.save(update_fields=["role"])
    return user


def provision_subject_user(subject_name: str, subject_email: str | None = None) -> User:
    email = (subject_email or "").strip().lower() or generate_placeholder_email(subject_name)
    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        return upgrade_user_role_to_subject(existing_user)

    first_name, _, last_name = subject_name.strip().partition(" ")
    user = User.objects.create(
        username=generate_unique_username(subject_name or email.split("@")[0]),
        email=email,
        first_name=first_name or subject_name or "Родственник",
        last_name=last_name,
        role=User.Role.SUBJECT,
        onboarding_completed=True,
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user


def get_or_create_primary_group(observer: User, group_name: str | None = None) -> FamilyGroup:
    group = observer.owned_groups.order_by("created_at").first()
    if group:
        return group

    default_name = group_name or f"Семья {observer.get_display_name()}"
    return FamilyGroup.objects.create(owner=observer, name=default_name, invite_code="")


def attach_subject_to_observer(
    observer: User,
    *,
    group_name: str | None,
    relative_name: str,
    relation: str,
    relative_email: str | None,
    can_view_location: bool = False,
) -> FamilyMembership:
    group = get_or_create_primary_group(observer, group_name)
    subject = provision_subject_user(relative_name, relative_email)

    membership, created = FamilyMembership.objects.get_or_create(
        group=group,
        observer=observer,
        subject=subject,
        defaults={
            "subject_name": relative_name,
            "subject_email": subject.email,
            "relation": relation,
            "can_view_location": can_view_location,
        },
    )

    if not created:
        membership.subject_name = relative_name
        membership.subject_email = subject.email
        membership.relation = relation
        membership.can_view_location = can_view_location
        membership.save(
            update_fields=["subject_name", "subject_email", "relation", "can_view_location"]
        )

    if not membership.magic_link or not membership.magic_link.is_valid:
        membership.magic_link = MagicLink.create_for_user(
            subject,
            MagicLink.Purpose.SUBJECT_ENTRY,
            days=settings.MAGIC_LINK_TTL_DAYS,
            extra_data={"membership_id": membership.id},
        )
        membership.save(update_fields=["magic_link"])

    return membership


def finalize_onboarding(
    user: User,
    *,
    family_data: dict,
    preferences_data: dict,
) -> None:
    settings_obj, _ = NotificationSettings.objects.get_or_create(user=user)
    settings_obj.reminder_time = preferences_data.get("reminder_time") or time(20, 0)
    settings_obj.health_alerts = preferences_data.get("health_alerts", True)
    settings_obj.weather_alerts = preferences_data.get("weather_alerts", True)
    settings_obj.save(
        update_fields=["reminder_time", "health_alerts", "weather_alerts"]
    )

    if preferences_data.get("daily_steps_goal"):
        HealthGoal.objects.update_or_create(
            subject=user,
            metric_type=MetricType.STEPS,
            period=HealthGoal.Period.DAILY,
            defaults={"target_value": preferences_data["daily_steps_goal"], "is_active": True},
        )

    if family_data.get("relative_name") and user.role in (User.Role.OBSERVER, User.Role.BOTH):
        attach_subject_to_observer(
            user,
            group_name=family_data.get("group_name"),
            relative_name=family_data["relative_name"],
            relation=family_data.get("relation") or FamilyMembership.Relation.OTHER,
            relative_email=family_data.get("relative_email"),
        )

    user.onboarding_completed = True
    user.save(update_fields=["onboarding_completed"])
