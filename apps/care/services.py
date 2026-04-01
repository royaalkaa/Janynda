import math
from datetime import datetime, timedelta

from django.db.models import Avg, Q, Sum
from django.http import Http404
from django.utils import timezone

from apps.accounts.models import User
from apps.family.models import FamilyMembership

from .models import (
    CommunityPlace,
    DailyPlanItem,
    FavoritePlace,
    LocationPing,
    LocationSharingSettings,
    SafeZone,
    TaskReminder,
    WearableDailySummary,
)

RECOMMENDED_STEPS = 10000
RECOMMENDED_SLEEP_HOURS = 8


DEFAULT_PLACE_CATALOG = [
    {
        "name": "Центр активного долголетия",
        "category": CommunityPlace.Category.ACTIVE_LONGEVITY,
        "city": "Алматы",
        "address": "Проспект Абая, 90",
        "description": "Танцы, ЛФК, арт-терапия, цифровая грамотность и общение.",
        "working_hours": "Будни, 09:00-18:00",
        "phone": "",
        "website": "",
        "latitude": 43.238949,
        "longitude": 76.889709,
        "is_featured": True,
    },
    {
        "name": "Поликлиника рядом с домом",
        "category": CommunityPlace.Category.CLINIC,
        "city": "Алматы",
        "address": "Улица Жандосова, 6",
        "description": "Плановые осмотры, рецепты, контроль хронических состояний.",
        "working_hours": "Пн-Пт 08:00-18:00",
        "phone": "",
        "website": "",
        "latitude": 43.232742,
        "longitude": 76.904210,
        "is_featured": True,
    },
    {
        "name": "Аптека с доставкой",
        "category": CommunityPlace.Category.PHARMACY,
        "city": "Алматы",
        "address": "Проспект Назарбаева, 120",
        "description": "Удобно для регулярных лекарств и расходников.",
        "working_hours": "Ежедневно, 08:00-22:00",
        "phone": "",
        "website": "",
        "latitude": 43.242593,
        "longitude": 76.945977,
        "is_featured": True,
    },
    {
        "name": "Парк для спокойных прогулок",
        "category": CommunityPlace.Category.PARK,
        "city": "Алматы",
        "address": "Парк 28 гвардейцев-панфиловцев",
        "description": "Подходит для прогулок, упражнений и встреч с семьёй.",
        "working_hours": "Ежедневно",
        "phone": "",
        "website": "",
        "latitude": 43.258217,
        "longitude": 76.954706,
        "is_featured": True,
    },
    {
        "name": "Продуктовый рядом с домом",
        "category": CommunityPlace.Category.GROCERY,
        "city": "Алматы",
        "address": "Улица Сатпаева, 30",
        "description": "Небольшой магазин с товарами первой необходимости.",
        "working_hours": "Ежедневно, 08:00-23:00",
        "phone": "",
        "website": "",
        "latitude": 43.235998,
        "longitude": 76.927120,
        "is_featured": False,
    },
    {
        "name": "Остановка общественного транспорта",
        "category": CommunityPlace.Category.TRANSPORT,
        "city": "Алматы",
        "address": "Проспект Абая, остановка у метро",
        "description": "Удобная пересадка на автобус и метро.",
        "working_hours": "Круглосуточно",
        "phone": "",
        "website": "",
        "latitude": 43.240667,
        "longitude": 76.905248,
        "is_featured": False,
    },
    {
        "name": "Клуб общения / кружок",
        "category": CommunityPlace.Category.SOCIAL_CLUB,
        "city": "Алматы",
        "address": "Дом культуры, улица Толе би, 58",
        "description": "Помогает не выпадать из общения и поддерживать память.",
        "working_hours": "По расписанию",
        "phone": "",
        "website": "",
        "latitude": 43.254969,
        "longitude": 76.928417,
        "is_featured": False,
    },
    {
        "name": "Служба социальной поддержки",
        "category": CommunityPlace.Category.SOCIAL_SERVICE,
        "city": "Алматы",
        "address": "Районный ЦОН / соцзащита",
        "description": "Вопросы льгот, сопровождения, помощи на дому.",
        "working_hours": "Будни, 09:00-18:00",
        "phone": "",
        "website": "",
        "latitude": 43.245676,
        "longitude": 76.913422,
        "is_featured": False,
    },
]


def get_accessible_subject(actor, subject_id=None, *, default_to_first_observed=False):
    if subject_id:
        subject = User.objects.filter(pk=subject_id).first()
        if not subject:
            raise Http404
        if subject == actor:
            return subject
        if FamilyMembership.objects.filter(observer=actor, subject=subject).exists():
            return subject
        raise Http404

    if default_to_first_observed:
        membership = actor.observing.select_related("subject").order_by("created_at").first()
        if membership and membership.subject:
            return membership.subject

    return actor


def can_manage_subject(actor, subject):
    return actor == subject or FamilyMembership.objects.filter(observer=actor, subject=subject).exists()


def get_related_subjects(actor):
    subjects = []
    seen_ids = set()
    for membership in actor.observing.select_related("subject").order_by("created_at"):
        if membership.subject and membership.subject_id not in seen_ids:
            subjects.append(membership.subject)
            seen_ids.add(membership.subject_id)
    return subjects


def get_observers_for_subject(subject, *, require_location_access=False):
    memberships = FamilyMembership.objects.filter(subject=subject).select_related("observer")
    if require_location_access:
        memberships = memberships.filter(can_view_location=True)
    return [membership.observer for membership in memberships if membership.observer_id]


def get_base_template(actor, subject):
    if subject == actor and actor.is_subject and not actor.is_observer:
        return "base/subject.html"
    return "base/observer.html"


def get_day_plan(subject, target_date=None):
    target_date = target_date or timezone.localdate()
    return (
        DailyPlanItem.objects.filter(subject=subject, scheduled_date=target_date)
        .select_related("created_by", "completed_by", "recurrence_parent")
        .prefetch_related("reminders")
    )


def get_plan_summary(subject, target_date=None):
    items = list(get_day_plan(subject, target_date))
    completed = sum(1 for item in items if item.is_completed)
    return {
        "items": items,
        "total": len(items),
        "completed": completed,
        "pending": max(0, len(items) - completed),
    }


def get_plan_window(subject, center_date=None, days=5):
    center_date = center_date or timezone.localdate()
    start_date = center_date - timedelta(days=days // 2)
    dates = [start_date + timedelta(days=offset) for offset in range(days)]
    plan_map = {current_date: list(get_day_plan(subject, current_date)) for current_date in dates}
    return dates, plan_map


def get_completed_task_history(subject, *, date_from=None, date_to=None):
    queryset = (
        DailyPlanItem.objects.filter(subject=subject, is_completed=True)
        .select_related("created_by", "completed_by")
        .order_by("-completed_at", "-scheduled_date")
    )
    if date_from:
        queryset = queryset.filter(completed_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(completed_at__date__lte=date_to)
    return queryset


def get_or_create_location_settings(subject):
    return LocationSharingSettings.objects.get_or_create(subject=subject)[0]


def get_location_period_start(period):
    today = timezone.localdate()
    if period == "month":
        return today - timedelta(days=29)
    if period == "week":
        return today - timedelta(days=6)
    return today


def get_last_location_ping(subject):
    return LocationPing.objects.filter(subject=subject).order_by("-captured_at").first()


def get_recent_location_pings(subject, *, limit=None, period="today"):
    queryset = LocationPing.objects.filter(subject=subject)
    start_date = get_location_period_start(period)
    queryset = queryset.filter(captured_at__date__gte=start_date).order_by("-captured_at")
    if limit:
        return queryset[:limit]
    return queryset


def serialize_location_pings(pings):
    payload = []
    for ping in pings:
        payload.append(
            {
                "id": ping.id,
                "latitude": float(ping.latitude),
                "longitude": float(ping.longitude),
                "captured_at": timezone.localtime(ping.captured_at).strftime("%d.%m.%Y %H:%M"),
                "source": ping.get_source_display(),
                "note": ping.note,
                "is_emergency": ping.is_emergency,
            }
        )
    return payload


def serialize_safe_zones(zones):
    return [
        {
            "id": zone.id,
            "name": zone.name,
            "latitude": float(zone.latitude),
            "longitude": float(zone.longitude),
            "radius_meters": zone.radius_meters,
            "is_home": zone.is_home,
        }
        for zone in zones
    ]


def _distance_km(origin, destination):
    try:
        from geopy.distance import distance
    except ImportError:
        distance = None
    if distance is not None:
        return round(distance(origin, destination).km, 1)

    lat1, lon1 = map(math.radians, origin)
    lat2, lon2 = map(math.radians, destination)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(6371.0 * c, 1)


def _normalize_place(item, *, subject=None, favorite_ids=None):
    favorite_ids = favorite_ids or set()
    if isinstance(item, CommunityPlace):
        distance_km = item.get_distance_from_home(subject) if subject else None
        route_url = ""
        if item.latitude is not None and item.longitude is not None:
            route_url = f"https://www.google.com/maps/dir/?api=1&destination={item.latitude},{item.longitude}"
        return {
            "id": item.id,
            "name": item.name,
            "category": item.category,
            "category_label": item.get_category_display(),
            "city": item.city,
            "address": item.address,
            "description": item.description,
            "phone": item.phone,
            "website": item.website,
            "working_hours": item.working_hours,
            "latitude": float(item.latitude) if item.latitude is not None else None,
            "longitude": float(item.longitude) if item.longitude is not None else None,
            "is_featured": item.is_featured,
            "distance_km": distance_km,
            "route_url": route_url,
            "is_favorite": item.id in favorite_ids,
        }

    distance_km = None
    if subject and item.get("latitude") and item.get("longitude"):
        settings_obj = getattr(subject, "location_sharing_settings", None)
        if settings_obj and settings_obj.home_latitude is not None and settings_obj.home_longitude is not None:
            distance_km = _distance_km(
                (float(settings_obj.home_latitude), float(settings_obj.home_longitude)),
                (float(item["latitude"]), float(item["longitude"])),
            )
    route_url = ""
    if item.get("latitude") and item.get("longitude"):
        route_url = f"https://www.google.com/maps/dir/?api=1&destination={item['latitude']},{item['longitude']}"
    return {
        **item,
        "id": None,
        "category_label": dict(CommunityPlace.Category.choices).get(item["category"], item["category"]),
        "distance_km": distance_km,
        "route_url": route_url,
        "is_favorite": False,
    }


def get_place_suggestions(city=None, category=None, *, subject=None, favorites_only=False):
    favorite_ids = set()
    if subject:
        favorite_ids = set(
            FavoritePlace.objects.filter(subject=subject).values_list("place_id", flat=True)
        )

    queryset = CommunityPlace.objects.all()
    if city:
        queryset = queryset.filter(city__iexact=city)
    if category:
        queryset = queryset.filter(category=category)
    if favorites_only:
        queryset = queryset.filter(id__in=favorite_ids)

    database_places = [_normalize_place(item, subject=subject, favorite_ids=favorite_ids) for item in queryset]
    if database_places or favorites_only:
        return database_places

    suggestions = DEFAULT_PLACE_CATALOG
    if city:
        suggestions = [item for item in suggestions if item["city"].lower() == city.lower()]
    if category:
        suggestions = [item for item in suggestions if item["category"] == category]
    return [_normalize_place(item, subject=subject, favorite_ids=favorite_ids) for item in suggestions]


def get_featured_places(city=None, *, subject=None, limit=4):
    return [item for item in get_place_suggestions(city=city, subject=subject) if item["is_featured"]][:limit]


def get_latest_wearable_summary(subject):
    return (
        WearableDailySummary.objects.filter(device__subject=subject, device__is_active=True)
        .select_related("device")
        .order_by("-summary_date", "-synced_at")
        .first()
    )


def get_wearable_stats(subject, period="week"):
    start_date = get_location_period_start(period)
    queryset = (
        WearableDailySummary.objects.filter(device__subject=subject, summary_date__gte=start_date)
        .select_related("device")
        .order_by("summary_date")
    )
    aggregates = queryset.aggregate(
        total_steps=Sum("steps"),
        avg_heart_rate=Avg("average_heart_rate"),
        avg_sleep_hours=Avg("sleep_hours"),
        avg_active_minutes=Avg("active_minutes"),
    )
    chart_data = {
        "labels": [summary.summary_date.strftime("%d.%m") for summary in queryset],
        "steps": [summary.steps for summary in queryset],
        "heart_rate": [summary.average_heart_rate or 0 for summary in queryset],
        "sleep_hours": [float(summary.sleep_hours or 0) for summary in queryset],
    }
    return queryset, aggregates, chart_data


def get_goal_indicator(value, target):
    if value is None:
        return "secondary"
    if value >= target:
        return "success"
    if value >= target * 0.75:
        return "warning"
    return "danger"


def get_task_scheduled_at(task):
    if not task.scheduled_time:
        return None
    naive_dt = datetime.combine(task.scheduled_date, task.scheduled_time)
    if timezone.is_naive(naive_dt):
        return timezone.make_aware(naive_dt, timezone.get_current_timezone())
    return naive_dt


def generate_recurring_occurrences(*, days_ahead=30, start_date=None):
    created_items = []
    start_date = start_date or timezone.localdate()
    end_date = start_date + timedelta(days=days_ahead)
    templates = DailyPlanItem.objects.filter(
        recurrence_parent__isnull=True,
    ).exclude(recurrence_type=DailyPlanItem.RecurrenceType.ONCE)

    for template in templates:
        current_date = max(start_date, template.scheduled_date + timedelta(days=1))
        while current_date <= end_date:
            if template.occurs_on(current_date):
                exists = DailyPlanItem.objects.filter(
                    Q(pk=template.pk) | Q(recurrence_parent=template),
                    scheduled_date=current_date,
                ).exists()
                if not exists:
                    occurrence = template.build_occurrence(current_date)
                    occurrence.save()
                    for reminder in template.reminders.all():
                        TaskReminder.objects.create(
                            task=occurrence,
                            remind_before_minutes=reminder.remind_before_minutes,
                        )
                    created_items.append(occurrence)
            current_date += timedelta(days=1)
    return created_items


def get_due_task_reminders(*, now=None):
    now = now or timezone.now()
    reminders = (
        TaskReminder.objects.filter(sent=False, task__is_completed=False)
        .select_related("task", "task__subject")
        .order_by("task__scheduled_date", "task__scheduled_time")
    )
    due_reminders = []
    for reminder in reminders:
        scheduled_at = get_task_scheduled_at(reminder.task)
        if not scheduled_at:
            continue
        remind_at = scheduled_at - timedelta(minutes=reminder.remind_before_minutes)
        if remind_at <= now <= scheduled_at + timedelta(hours=1):
            due_reminders.append(reminder)
    return due_reminders


def create_notification(*, recipient, title, body, severity, category, related_subject=None):
    from apps.notifications.models import Notification

    return Notification.objects.create(
        recipient=recipient,
        title=title,
        body=body,
        severity=severity,
        category=category,
        related_subject=related_subject,
    )


def dispatch_task_reminder(reminder):
    from apps.ai_assistant.models import VoiceCommandLog
    from apps.notifications.models import Notification

    task = reminder.task
    scheduled_at = get_task_scheduled_at(task)
    if not scheduled_at:
        return None

    title = f"Напоминание: {task.title}"
    body = (
        f"Через {reminder.remind_before_minutes} мин: {task.title}. "
        f"Время: {scheduled_at.astimezone(timezone.get_current_timezone()):%H:%M}."
    )

    recipients = [task.subject, *get_observers_for_subject(task.subject)]
    seen_ids = set()
    for recipient in recipients:
        if recipient.id in seen_ids:
            continue
        seen_ids.add(recipient.id)
        create_notification(
            recipient=recipient,
            title=title,
            body=body,
            severity=Notification.Severity.INFO,
            category=Notification.Category.ENTRY_REMINDER,
            related_subject=task.subject,
        )

    VoiceCommandLog.objects.create(
        user=task.created_by,
        subject=task.subject,
        transcript=title,
        response_text=body,
        action_type=VoiceCommandLog.ActionType.REMINDER,
        payload={"task_id": task.id, "reminder_id": reminder.id},
        is_system_message=True,
        is_read=False,
    )
    reminder.mark_sent()
    return body


def handle_zone_crossing_for_ping(ping):
    from apps.notifications.models import Notification

    settings_obj = get_or_create_location_settings(ping.subject)
    if not settings_obj.tracking_enabled or not settings_obj.share_with_family:
        return []

    recipients = get_observers_for_subject(ping.subject, require_location_access=True)
    if not recipients:
        return []

    events = settings_obj.check_zone_crossing(ping)
    notifications = []
    for event in events:
        zone = event["zone"]
        event_type = event["event_type"]
        if zone.is_home:
            title = "Возвращение домой" if event_type == "entered" else "Выход из дома"
        else:
            title = (
                f"Вход в зону «{zone.name}»"
                if event_type == "entered"
                else f"Выход из зоны «{zone.name}»"
            )
        body = (
            f"{ping.subject.get_display_name()} "
            f"{'вошёл(ла)' if event_type == 'entered' else 'вышел(ла)'} "
            f"из зоны «{zone.name}» в {timezone.localtime(ping.captured_at):%d.%m %H:%M}."
        )
        for recipient in recipients:
            notifications.append(
                create_notification(
                    recipient=recipient,
                    title=title,
                    body=body,
                    severity=Notification.Severity.WARNING if zone.is_home else Notification.Severity.INFO,
                    category=Notification.Category.SYSTEM,
                    related_subject=ping.subject,
                )
            )
    return notifications


def check_subject_absence(subject, *, now=None):
    from apps.notifications.models import Notification

    now = now or timezone.now()
    settings_obj = get_or_create_location_settings(subject)
    if not settings_obj.tracking_enabled or not settings_obj.share_with_family:
        return False

    home_zones = list(subject.safe_zones.filter(is_home=True))
    if not home_zones:
        return False

    latest_ping = get_last_location_ping(subject)
    if not latest_ping:
        return False

    if any(zone.contains(latest_ping.latitude, latest_ping.longitude) for zone in home_zones):
        return False

    latest_home_ping = None
    for ping in subject.location_pings.order_by("-captured_at"):
        if any(zone.contains(ping.latitude, ping.longitude) for zone in home_zones):
            latest_home_ping = ping
            break

    if not latest_home_ping:
        return False

    threshold = timedelta(hours=settings_obj.max_absence_hours)
    if now - latest_home_ping.captured_at < threshold:
        return False

    if settings_obj.last_absence_alert_at and settings_obj.last_absence_alert_at >= latest_home_ping.captured_at:
        return False

    title = "Долгое отсутствие вне дома"
    body = (
        f"{subject.get_display_name()} не возвращался(ась) домой уже "
        f"более {settings_obj.max_absence_hours} ч."
    )
    for recipient in get_observers_for_subject(subject, require_location_access=True):
        create_notification(
            recipient=recipient,
            title=title,
            body=body,
            severity=Notification.Severity.WARNING,
            category=Notification.Category.SYSTEM,
            related_subject=subject,
        )
    settings_obj.mark_absence_alerted()
    return True


def _notification_exists(recipient, subject, title, *, day=None):
    from apps.notifications.models import Notification

    day = day or timezone.localdate()
    return Notification.objects.filter(
        recipient=recipient,
        related_subject=subject,
        title=title,
        created_at__date=day,
    ).exists()


def check_wearable_goals_for_subject(subject, *, now=None):
    from apps.notifications.models import Notification

    now = now or timezone.localtime()
    latest_summary = get_latest_wearable_summary(subject)
    if not latest_summary:
        return 0

    notifications_count = 0
    recipients = []
    seen_ids = set()
    for recipient in [subject, *get_observers_for_subject(subject)]:
        if recipient.id not in seen_ids:
            recipients.append(recipient)
            seen_ids.add(recipient.id)

    if latest_summary.summary_date == timezone.localdate() and latest_summary.steps < 5000 and now.hour >= 16:
        title = "Пора на прогулку"
        body = f"Сегодня пока только {latest_summary.steps} шагов. Небольшая прогулка поможет закрыть день активнее."
        for recipient in recipients:
            if _notification_exists(recipient, subject, title):
                continue
            create_notification(
                recipient=recipient,
                title=title,
                body=body,
                severity=Notification.Severity.INFO,
                category=Notification.Category.CHALLENGE,
                related_subject=subject,
            )
            notifications_count += 1

    if latest_summary.heart_rate_max and (latest_summary.heart_rate_max > 120 or latest_summary.heart_rate_max < 50):
        title = "Проверьте пульс"
        body = f"Максимальный пульс за день: {latest_summary.heart_rate_max}. Стоит обратить внимание на самочувствие."
        for recipient in recipients:
            if _notification_exists(recipient, subject, title):
                continue
            create_notification(
                recipient=recipient,
                title=title,
                body=body,
                severity=Notification.Severity.WARNING,
                category=Notification.Category.HEALTH_ALERT,
                related_subject=subject,
            )
            notifications_count += 1

    if latest_summary.summary_date == timezone.localdate() and latest_summary.steps >= RECOMMENDED_STEPS:
        title = "Цель по шагам выполнена"
        body = f"Сегодня уже {latest_summary.steps} шагов. Отличный результат."
        for recipient in recipients:
            if _notification_exists(recipient, subject, title):
                continue
            create_notification(
                recipient=recipient,
                title=title,
                body=body,
                severity=Notification.Severity.INFO,
                category=Notification.Category.CHALLENGE,
                related_subject=subject,
            )
            notifications_count += 1

    return notifications_count
