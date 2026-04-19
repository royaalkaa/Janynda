import json
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone

from apps.ai_assistant.models import AIComment
from apps.challenges.models import Challenge
from apps.family.models import FamilyMembership
from apps.health.models import MetricRecord, MetricType


SEVERITY_ORDER = {"critical": 3, "warning": 2, "normal": 1, "no-data": 0}


def _build_synthetic_heart_rate_record(record):
    pulse = record.value_json.get("pulse")
    if pulse is None:
        return None

    return MetricRecord(
        subject=record.subject,
        metric_type=MetricType.HEART_RATE,
        value_json={"bpm": pulse},
        source=record.source,
        recorded_at=record.recorded_at,
    )


def get_latest_metrics_for_subject(subject):
    latest = {}
    for record in MetricRecord.objects.filter(subject=subject).order_by("-recorded_at"):
        if record.metric_type not in latest:
            latest[record.metric_type] = record
        if MetricType.HEART_RATE not in latest and record.metric_type == MetricType.BLOOD_PRESSURE:
            heart_rate_record = _build_synthetic_heart_rate_record(record)
            if heart_rate_record is not None:
                latest[MetricType.HEART_RATE] = heart_rate_record
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
    start_at = timezone.make_aware(
        datetime.combine(start_date, time.min),
        timezone.get_current_timezone(),
    )
    records = MetricRecord.objects.filter(subject=subject, recorded_at__gte=start_at).order_by("recorded_at")

    steps_map = defaultdict(int)
    bp_points = []
    heart_rate_points = []
    seen_heart_rate_points = set()
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
            pulse = record.value_json.get("pulse")
            heart_rate_key = (record.recorded_at.isoformat(), pulse)
            if pulse is not None and heart_rate_key not in seen_heart_rate_points:
                heart_rate_points.append(
                    {
                        "date": day.strftime("%d.%m"),
                        "bpm": pulse,
                    }
                )
                seen_heart_rate_points.add(heart_rate_key)
        if record.metric_type == MetricType.HEART_RATE:
            bpm = record.value_json.get("bpm")
            heart_rate_key = (record.recorded_at.isoformat(), bpm)
            if bpm is not None and heart_rate_key not in seen_heart_rate_points:
                heart_rate_points.append(
                    {
                        "date": day.strftime("%d.%m"),
                        "bpm": bpm,
                    }
                )
                seen_heart_rate_points.add(heart_rate_key)

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
        "heart_rate_json": json.dumps(heart_rate_points[-7:], ensure_ascii=False),
    }


def get_user_challenges(user):
    return (
        Challenge.objects.filter(group__owner=user)
        .prefetch_related("participants")
        .order_by("-created_at")[:5]
    )
