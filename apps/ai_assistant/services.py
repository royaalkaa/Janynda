import re

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from apps.care.models import DailyPlanItem
from apps.care.services import get_day_plan
from apps.health.models import MetricRecord, MetricType

from .models import VoiceCommandLog


def _create_completed_plan_item(subject, actor, *, title, category, **extra_fields):
    return DailyPlanItem.objects.create(
        subject=subject,
        created_by=actor,
        completed_by=actor,
        title=title,
        scheduled_date=timezone.localdate(),
        category=category,
        is_completed=True,
        completed_at=timezone.now(),
        via_voice=True,
        **extra_fields,
    )


def _match_today_item(subject, category, *, medicine_name=None):
    queryset = DailyPlanItem.objects.filter(
        subject=subject,
        scheduled_date=timezone.localdate(),
        category=category,
        is_completed=False,
    ).order_by("scheduled_time", "created_at")
    if medicine_name:
        queryset = queryset.filter(
            models.Q(medicine_name__icontains=medicine_name) | models.Q(title__icontains=medicine_name)
        )
    return queryset.first()


def _build_today_plan_answer(subject):
    today_items = list(get_day_plan(subject, timezone.localdate()))
    if not today_items:
        return VoiceCommandLog.ActionType.PLAN_QUERY, "На сегодня задач пока нет.", {"count": 0}

    pending_items = [item.title for item in today_items if not item.is_completed]
    completed_count = len(today_items) - len(pending_items)
    if pending_items:
        answer = (
            f"На сегодня {len(today_items)} задач. Уже выполнено {completed_count}. "
            f"Осталось: {', '.join(pending_items[:4])}."
        )
    else:
        answer = f"На сегодня {len(today_items)} задач, и все они уже выполнены."
    return VoiceCommandLog.ActionType.PLAN_QUERY, answer, {"count": len(today_items)}


def _find_nearest_task(subject, category):
    return (
        DailyPlanItem.objects.filter(
            subject=subject,
            category=category,
            is_completed=False,
            scheduled_date__gte=timezone.localdate(),
        )
        .order_by("scheduled_date", "scheduled_time", "created_at")
        .first()
    )


def _build_medicine_answer(subject):
    item = _find_nearest_task(subject, DailyPlanItem.Category.MEDICATION)
    if not item:
        return "Сейчас нет ближайшего лекарства в плане."
    details = []
    if item.medicine_name:
        details.append(item.medicine_name)
    if item.medicine_dosage:
        details.append(item.medicine_dosage)
    detail_text = f" ({', '.join(details)})" if details else ""
    return (
        f"Ближайшее лекарство: {item.title}{detail_text}. "
        f"{item.scheduled_date:%d.%m.%Y} {item.scheduled_time.strftime('%H:%M') if item.scheduled_time else 'без времени'}."
    )


def _build_doctor_answer(subject):
    item = _find_nearest_task(subject, DailyPlanItem.Category.DOCTOR_VISIT)
    if not item:
        return "Ближайших визитов к врачу в плане нет."
    details = []
    if item.doctor_specialty:
        details.append(item.doctor_specialty)
    if item.doctor_address:
        details.append(item.doctor_address)
    detail_text = f" ({', '.join(details)})" if details else ""
    return (
        f"Следующий визит к врачу: {item.title}{detail_text}. "
        f"{item.scheduled_date:%d.%m.%Y} {item.scheduled_time.strftime('%H:%M') if item.scheduled_time else 'без времени'}."
    )


def _build_water_answer(subject):
    today = timezone.localdate()
    task_total = (
        DailyPlanItem.objects.filter(
            subject=subject,
            category=DailyPlanItem.Category.WATER,
            scheduled_date=today,
            is_completed=True,
        ).aggregate(total=Sum("water_amount_ml"))["total"]
        or 0
    )
    metric_total = 0
    for record in MetricRecord.objects.filter(
        subject=subject,
        metric_type=MetricType.WATER,
        recorded_at__date=today,
    ):
        metric_total += int(record.value_json.get("ml", 0) or 0)
    total = task_total + metric_total
    if total:
        return f"Сегодня отмечено {total} мл воды."
    return "Сегодня вода ещё не отмечалась."


def _extract_metric_payload(normalized_text):
    pressure_match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", normalized_text)
    if "давлен" in normalized_text and pressure_match:
        systolic, diastolic = map(int, pressure_match.groups())
        return {
            "kind": "metric",
            "metric_type": MetricType.BLOOD_PRESSURE,
            "value": {"systolic": systolic, "diastolic": diastolic},
        }

    heart_rate_match = re.search(r"пульс\s+(\d{2,3})", normalized_text)
    if heart_rate_match:
        bpm = int(heart_rate_match.group(1))
        return {
            "kind": "metric",
            "metric_type": MetricType.HEART_RATE,
            "value": {"bpm": bpm},
        }

    steps_match = re.search(r"шаг[аиов]*\s+(\d{3,6})", normalized_text)
    if steps_match:
        steps = int(steps_match.group(1))
        return {
            "kind": "metric",
            "metric_type": MetricType.STEPS,
            "value": {"steps": steps},
        }
    return None


def _extract_medicine_name(normalized_text):
    match = re.search(r"(?:лекарств[оа]|таблетк[ауи]?)(.*)", normalized_text)
    if not match:
        return ""
    medicine_name = match.group(1).strip(" .,:;!?")
    prefixes = ("выпил", "принял", "я", "сейчас", "сегодня")
    parts = [part for part in medicine_name.split() if part not in prefixes]
    return " ".join(parts).strip()


def _get_pending_confirmation(actor, subject, confirmation_log_id=None):
    queryset = VoiceCommandLog.objects.filter(
        user=actor,
        subject=subject,
        requires_confirmation=True,
        confirmed=False,
        is_system_message=False,
    )
    if confirmation_log_id:
        queryset = queryset.filter(pk=confirmation_log_id)
    return queryset.order_by("-created_at").first()


def _create_confirmation_log(*, actor, subject, transcript, action_type, payload):
    return VoiceCommandLog.objects.create(
        user=actor,
        subject=subject,
        transcript=transcript,
        response_text=f"Вы сказали: {transcript}. Подтвердить?",
        action_type=action_type,
        payload=payload,
        requires_confirmation=True,
        confirmed=False,
    )


def _execute_pending_payload(actor, subject, payload):
    kind = payload.get("kind")
    if kind == "metric":
        MetricRecord.objects.create(
            subject=subject,
            metric_type=payload["metric_type"],
            value_json=payload["value"],
            source=MetricRecord.Source.MANUAL,
        )
        if payload["metric_type"] == MetricType.BLOOD_PRESSURE:
            v = payload["value"]
            return VoiceCommandLog.ActionType.METRIC_LOG, f"Записал давление {v['systolic']}/{v['diastolic']}.", payload
        if payload["metric_type"] == MetricType.HEART_RATE:
            return VoiceCommandLog.ActionType.METRIC_LOG, f"Записал пульс {payload['value']['bpm']}.", payload
        if payload["metric_type"] == MetricType.STEPS:
            return VoiceCommandLog.ActionType.METRIC_LOG, f"Записал {payload['value']['steps']} шагов.", payload

    if kind == "medication":
        medicine_name = payload.get("medicine_name", "")
        plan_item = (
            DailyPlanItem.objects.filter(
                subject=subject,
                scheduled_date=timezone.localdate(),
                category=DailyPlanItem.Category.MEDICATION,
                is_completed=False,
            )
            .order_by("scheduled_time", "created_at")
            .first()
        )
        if plan_item:
            if medicine_name and not plan_item.medicine_name:
                plan_item.medicine_name = medicine_name
                plan_item.save(update_fields=["medicine_name"])
            plan_item.mark_completed(actor)
            return (
                VoiceCommandLog.ActionType.PLAN_COMPLETE,
                f"Отметил задачу «{plan_item.title}» как выполненную.",
                {"plan_item_id": plan_item.id, "medicine_name": medicine_name},
            )
        plan_item = _create_completed_plan_item(
            subject,
            actor,
            title=f"Лекарство принято{f': {medicine_name}' if medicine_name else ''}",
            category=DailyPlanItem.Category.MEDICATION,
            medicine_name=medicine_name,
        )
        return (
            VoiceCommandLog.ActionType.MEDICATION_LOG,
            f"Отметил, что лекарство{f' {medicine_name}' if medicine_name else ''} принято.",
            {"plan_item_id": plan_item.id, "medicine_name": medicine_name},
        )

    if kind == "doctor":
        plan_item = (
            DailyPlanItem.objects.filter(
                subject=subject,
                scheduled_date=timezone.localdate(),
                category=DailyPlanItem.Category.DOCTOR_VISIT,
                is_completed=False,
            )
            .order_by("scheduled_time", "created_at")
            .first()
        )
        if plan_item:
            plan_item.mark_completed(actor)
            return (
                VoiceCommandLog.ActionType.PLAN_COMPLETE,
                f"Отметил визит «{plan_item.title}» как завершённый.",
                {"plan_item_id": plan_item.id},
            )
        plan_item = _create_completed_plan_item(
            subject,
            actor,
            title="Визит к врачу состоялся",
            category=DailyPlanItem.Category.DOCTOR_VISIT,
        )
        return (
            VoiceCommandLog.ActionType.DOCTOR_LOG,
            "Отметил, что сегодня был визит к врачу.",
            {"plan_item_id": plan_item.id},
        )

    return VoiceCommandLog.ActionType.UNSUPPORTED, "Не удалось выполнить команду.", payload


def _confirm_pending_command(actor, subject, pending_log):
    action_type, response_text, payload = _execute_pending_payload(actor, subject, pending_log.payload)
    pending_log.requires_confirmation = False
    pending_log.confirmed = True
    pending_log.save(update_fields=["requires_confirmation", "confirmed"])
    return VoiceCommandLog.objects.create(
        user=actor,
        subject=subject,
        transcript=pending_log.transcript,
        response_text=response_text,
        action_type=action_type,
        payload=payload,
        confirmed=True,
    )


def _cancel_pending_command(actor, subject, pending_log=None, transcript="Отмена"):
    if pending_log:
        pending_log.requires_confirmation = False
        pending_log.payload = {**pending_log.payload, "cancelled": True}
        pending_log.save(update_fields=["requires_confirmation", "payload"])
    return VoiceCommandLog.objects.create(
        user=actor,
        subject=subject,
        transcript=transcript,
        response_text="Действие отменено.",
        action_type=VoiceCommandLog.ActionType.CANCELLED,
        payload={},
        confirmed=True,
    )


def handle_voice_command(*, actor, subject, transcript, confirmation_log_id=None, confirmation=None):
    normalized_text = transcript.lower().strip()
    pending_log = _get_pending_confirmation(actor, subject, confirmation_log_id)

    if confirmation == "yes":
        if not pending_log:
            return VoiceCommandLog.objects.create(
                user=actor,
                subject=subject,
                transcript=transcript,
                response_text="Нет команды, ожидающей подтверждения.",
                action_type=VoiceCommandLog.ActionType.UNSUPPORTED,
                payload={},
                confirmed=True,
            )
        return _confirm_pending_command(actor, subject, pending_log)

    if confirmation == "no" or normalized_text in {"отмена", "назад"}:
        return _cancel_pending_command(actor, subject, pending_log, transcript=transcript)

    if "какое лекар" in normalized_text:
        return VoiceCommandLog.objects.create(
            user=actor,
            subject=subject,
            transcript=transcript,
            response_text=_build_medicine_answer(subject),
            action_type=VoiceCommandLog.ActionType.ANSWER,
            payload={},
            confirmed=True,
        )

    if "когда к врачу" in normalized_text:
        return VoiceCommandLog.objects.create(
            user=actor,
            subject=subject,
            transcript=transcript,
            response_text=_build_doctor_answer(subject),
            action_type=VoiceCommandLog.ActionType.ANSWER,
            payload={},
            confirmed=True,
        )

    if "сколько воды" in normalized_text:
        return VoiceCommandLog.objects.create(
            user=actor,
            subject=subject,
            transcript=transcript,
            response_text=_build_water_answer(subject),
            action_type=VoiceCommandLog.ActionType.ANSWER,
            payload={},
            confirmed=True,
        )

    if "сегодня" in normalized_text or "план" in normalized_text:
        action_type, response_text, payload = _build_today_plan_answer(subject)
        return VoiceCommandLog.objects.create(
            user=actor,
            subject=subject,
            transcript=transcript,
            response_text=response_text,
            action_type=action_type,
            payload=payload,
            confirmed=True,
        )

    metric_payload = _extract_metric_payload(normalized_text)
    if metric_payload:
        return _create_confirmation_log(
            actor=actor,
            subject=subject,
            transcript=transcript,
            action_type=VoiceCommandLog.ActionType.METRIC_LOG,
            payload=metric_payload,
        )

    if "лекар" in normalized_text or "таблет" in normalized_text:
        medicine_name = _extract_medicine_name(normalized_text)
        return _create_confirmation_log(
            actor=actor,
            subject=subject,
            transcript=transcript,
            action_type=VoiceCommandLog.ActionType.MEDICATION_LOG,
            payload={"kind": "medication", "medicine_name": medicine_name},
        )

    if any(word in normalized_text for word in ["врач", "поликлин", "доктор"]):
        return _create_confirmation_log(
            actor=actor,
            subject=subject,
            transcript=transcript,
            action_type=VoiceCommandLog.ActionType.DOCTOR_LOG,
            payload={"kind": "doctor"},
        )

    return VoiceCommandLog.objects.create(
        user=actor,
        subject=subject,
        transcript=transcript,
        response_text=(
            "Пока я умею отвечать на вопросы про план, лекарства, врача и воду, "
            "а также записывать давление, пульс и шаги."
        ),
        action_type=VoiceCommandLog.ActionType.UNSUPPORTED,
        payload={},
        confirmed=True,
    )
