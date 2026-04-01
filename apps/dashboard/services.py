import json
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from apps.ai_assistant.models import AIComment
from apps.challenges.models import Challenge
from apps.family.models import FamilyMembership
from apps.health.models import MetricRecord, MetricType


SEVERITY_ORDER = {"critical": 3, "warning": 2, "normal": 1, "no-data": 0}


def get_latest_metrics_for_subject(subject):
    latest = {}
    for record in MetricRecord.objects.filter(subject=subject).order_by("-recorded_at"):
        if record.metric_type not in latest:
            latest[record.metric_type] = record
    return latest


def get_subject_status(subject):
    latest = get_latest_metrics_for_subject(subject)
    if not latest:
        return "no-data", latest

    severities = [record.get_severity() for record in latest.values()]
    if "critical" in severities:
        return "critical", latest
    if "warning" in severities:
        return "warning", latest
    return "normal", latest


def get_observer_memberships_with_snapshots(observer):
    memberships = observer.observing.select_related("subject", "magic_link", "group").order_by("created_at")
    snapshots = []
    for membership in memberships:
        if membership.subject:
            status, latest_metrics = get_subject_status(membership.subject)
            last_seen = max((record.recorded_at for record in latest_metrics.values()), default=None)
        else:
            status, latest_metrics, last_seen = "no-data", {}, None

        snapshots.append(
            {
                "membership": membership,
                "status": status,
                "latest_metrics": latest_metrics,
                "last_seen": last_seen,
            }
        )
    return snapshots


def get_latest_comment_for_subject(subject):
    comment = AIComment.get_current(subject)
    if comment:
        return comment

    latest = get_latest_metrics_for_subject(subject)
    if not latest:
        return None

    fragments = []
    bp = latest.get(MetricType.BLOOD_PRESSURE)
    steps = latest.get(MetricType.STEPS)
    hr = latest.get(MetricType.HEART_RATE)
    if bp:
        severity = bp.get_severity()
        if severity == "critical":
            fragments.append("давление требует срочного внимания")
        elif severity == "warning":
            fragments.append("давление выше или ниже комфортного диапазона")
        else:
            fragments.append("давление сейчас без явных отклонений")
    if hr:
        fragments.append(f"пульс {hr.get_display_value().lower()}")
    if steps:
        fragments.append(f"активность зафиксирована: {steps.get_display_value().lower()}")

    content = "Сегодня " + ", ".join(fragments) + "."
    return AIComment.objects.create(
        subject=subject,
        content=content,
        is_fallback=True,
        expires_at=timezone.now() + timedelta(days=1),
    )


def get_subject_chart_payload(subject, days=7):
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    records = MetricRecord.objects.filter(subject=subject, recorded_at__date__gte=start_date)

    steps_map = defaultdict(int)
    bp_points = []
    for record in records:
        day = timezone.localtime(record.recorded_at).date()
        if record.metric_type == MetricType.STEPS:
            steps_map[day] += int(record.value_json.get("steps", 0))
        if record.metric_type == MetricType.BLOOD_PRESSURE:
            bp_points.append(
                {
                    "date": day.strftime("%d.%m"),
                    "systolic": record.value_json.get("systolic"),
                    "diastolic": record.value_json.get("diastolic"),
                }
            )

    labels = []
    steps_data = []
    for offset in range(days):
        current = start_date + timedelta(days=offset)
        labels.append(current.strftime("%d.%m"))
        steps_data.append(steps_map[current])

    return {
        "labels_json": json.dumps(labels, ensure_ascii=False),
        "steps_json": json.dumps(steps_data),
        "bp_json": json.dumps(bp_points[-7:], ensure_ascii=False),
    }


def get_user_challenges(user):
    return (
        Challenge.objects.filter(group__owner=user)
        .prefetch_related("participants")
        .order_by("-created_at")[:5]
    )
