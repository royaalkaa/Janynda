import re
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from apps.care.models import DailyPlanItem
from apps.care.services import RECOMMENDED_SLEEP_HOURS, RECOMMENDED_STEPS, get_day_plan, get_latest_wearable_summary
from apps.health.models import MetricRecord, MetricType

from .models import VoiceCommandLog


VOICE_ASSISTANT_EXAMPLE_GROUPS = [
    {
        "title": "План и напоминания",
        "examples": [
            "Что у меня сегодня по плану?",
            "Когда мне к врачу?",
            "Какое лекарство сейчас принимать?",
            "Сколько воды я выпил сегодня?",
        ],
    },
    {
        "title": "Быстрые отметки",
        "examples": [
            "Я выпил лекарство кардиомагнил",
            "Я был у врача",
            "Давление 120/80",
            "Пульс 72",
            "Шаги 6400",
        ],
    },
    {
        "title": "Вопросы про здоровье",
        "examples": [
            "Давление 150 на 95 это нормально?",
            "Пульс 48 это опасно?",
            "Сколько воды лучше выпить сегодня?",
            "Как улучшить сон?",
            "Сколько шагов мне полезно пройти?",
        ],
    },
]

VOICE_ASSISTANT_KNOWLEDGE_TOPICS = [
    "давление, пульс, вода, сон, шаги и прогулки",
    "расписание лекарств, ближайший визит к врачу и план дня",
    "простые бытовые советы по самоконтролю без постановки диагноза",
    "предупреждение, когда показатели выглядят тревожно и стоит связаться с врачом",
]

HEALTH_KEYWORDS = (
    "давлен",
    "пульс",
    "сердц",
    "вода",
    "сон",
    "шаг",
    "прогул",
    "лекар",
    "таблет",
    "врач",
    "поликлин",
    "карди",
    "сахар",
    "кислород",
    "температур",
    "самочув",
    "голов",
    "слабост",
)

ASSESSMENT_HINTS = (
    "?",
    "норм",
    "норма",
    "опас",
    "высок",
    "низк",
    "плох",
    "хорош",
    "это",
    "стоит ли",
)


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


def _parse_blood_pressure(normalized_text):
    match = re.search(r"(\d{2,3})\s*(?:/|на)\s*(\d{2,3})", normalized_text)
    if not match:
        return None
    return tuple(map(int, match.groups()))


def _parse_heart_rate(normalized_text):
    match = re.search(r"пульс\s+(\d{2,3})", normalized_text)
    if not match:
        return None
    return int(match.group(1))


def _parse_steps(normalized_text):
    match = re.search(r"шаг[аиов]*\s+(\d{3,6})", normalized_text)
    if not match:
        return None
    return int(match.group(1))


def _is_assessment_question(normalized_text):
    if "это нормально" in normalized_text:
        return True
    return any(hint in normalized_text for hint in ASSESSMENT_HINTS)


def _extract_metric_payload(normalized_text):
    pressure = _parse_blood_pressure(normalized_text)
    if pressure and "давлен" in normalized_text and not _is_assessment_question(normalized_text):
        systolic, diastolic = pressure
        return {
            "kind": "metric",
            "metric_type": MetricType.BLOOD_PRESSURE,
            "value": {"systolic": systolic, "diastolic": diastolic},
        }

    heart_rate = _parse_heart_rate(normalized_text)
    if heart_rate and not _is_assessment_question(normalized_text):
        return {
            "kind": "metric",
            "metric_type": MetricType.HEART_RATE,
            "value": {"bpm": heart_rate},
        }

    steps = _parse_steps(normalized_text)
    if steps:
        return {
            "kind": "metric",
            "metric_type": MetricType.STEPS,
            "value": {"steps": steps},
        }
    return None


def _extract_health_assessment(normalized_text):
    pressure = _parse_blood_pressure(normalized_text)
    pressure_context_words = ("давлен", "стало", "после", "лекар", "таблет", "самочув", "слаб", "голов")
    if pressure and _is_assessment_question(normalized_text) and any(
        word in normalized_text for word in pressure_context_words
    ):
        systolic, diastolic = pressure
        return {
            "metric_type": MetricType.BLOOD_PRESSURE,
            "value": {"systolic": systolic, "diastolic": diastolic},
        }

    heart_rate = _parse_heart_rate(normalized_text)
    if heart_rate and _is_assessment_question(normalized_text):
        return {
            "metric_type": MetricType.HEART_RATE,
            "value": {"bpm": heart_rate},
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


def _looks_like_medication_log_command(normalized_text):
    if not any(keyword in normalized_text for keyword in ["лекар", "таблет"]):
        return False
    return any(
        verb in normalized_text
        for verb in ["выпил", "выпила", "принял", "приняла", "отметь", "отметил", "запиши", "записать"]
    )


def _looks_like_doctor_log_command(normalized_text):
    return any(
        phrase in normalized_text
        for phrase in [
            "был у врача",
            "была у врача",
            "был у доктора",
            "была у доктора",
            "ходил к врачу",
            "сходил к врачу",
            "посетил врача",
            "посетила врача",
        ]
    )


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


def _create_answer_log(*, actor, subject, transcript, response_text, payload=None):
    return VoiceCommandLog.objects.create(
        user=actor,
        subject=subject,
        transcript=transcript,
        response_text=response_text,
        action_type=VoiceCommandLog.ActionType.ANSWER,
        payload=payload or {},
        confirmed=True,
    )


def _get_threshold_label(severity, metric_type):
    if severity == "critical":
        if metric_type == MetricType.BLOOD_PRESSURE:
            return "выглядит тревожно и требует внимания"
        return "выглядит тревожно"
    if severity == "warning":
        return "выше или ниже комфортного диапазона"
    return "пока выглядит в пределах целевого диапазона"


def _build_blood_pressure_assessment(subject, systolic, diastolic):
    record = MetricRecord(
        subject=subject,
        metric_type=MetricType.BLOOD_PRESSURE,
        value_json={"systolic": systolic, "diastolic": diastolic},
    )
    severity = record.get_severity()
    response = (
        f"Давление {systolic}/{diastolic} {_get_threshold_label(severity, MetricType.BLOOD_PRESSURE)} "
        f"для профиля в приложении."
    )
    if severity == "critical":
        response += " Если есть сильная головная боль, боль в груди, одышка или слабость, лучше срочно связаться с врачом или вызвать помощь."
    elif severity == "warning":
        response += " Полезно спокойно посидеть 5–10 минут и перемерить давление ещё раз."
    else:
        response += " Продолжайте обычный контроль и отмечайте самочувствие."
    return response


def _build_heart_rate_assessment(subject, bpm):
    record = MetricRecord(
        subject=subject,
        metric_type=MetricType.HEART_RATE,
        value_json={"bpm": bpm},
    )
    severity = record.get_severity()
    response = f"Пульс {bpm} {_get_threshold_label(severity, MetricType.HEART_RATE)}."
    if severity == "critical":
        response += " Если есть слабость, головокружение, боль в груди или одышка, лучше не откладывать обращение за медицинской помощью."
    elif severity == "warning":
        response += " Стоит проверить пульс повторно в покое и при необходимости обсудить это с врачом."
    else:
        response += " Для оценки в динамике удобно продолжать регулярные записи."
    return response


def _get_goal_value(subject, metric_type, fallback_value):
    goal = (
        subject.health_goals.filter(metric_type=metric_type, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not goal:
        return fallback_value
    if isinstance(goal.target_value, Decimal) and goal.target_value == goal.target_value.to_integral():
        return int(goal.target_value)
    return goal.target_value


def _build_local_health_fallback(subject, normalized_text):
    if "умеешь" in normalized_text or "пример" in normalized_text:
        flattened = [example for group in VOICE_ASSISTANT_EXAMPLE_GROUPS for example in group["examples"][:2]]
        return "Я умею отвечать про план, лекарства, врача, воду, давление, пульс, сон и шаги. Например: " + "; ".join(flattened[:6]) + "."

    if "давлен" in normalized_text:
        return "Назовите давление в формате 120/80, и я скажу, выглядит ли оно нормальным для профиля в приложении."

    if "пульс" in normalized_text:
        return "Можно спросить, например: «Пульс 72 это нормально?» или просто записать «Пульс 72»."

    if "вода" in normalized_text:
        water_goal = _get_goal_value(subject, MetricType.WATER, 1500)
        return f"Ориентир по воде сейчас около {water_goal} мл в день. Удобно делить объём на 5–6 небольших приёмов в течение дня."

    if "сон" in normalized_text:
        return f"В приложении ориентир по сну — около {RECOMMENDED_SLEEP_HOURS} часов. Полезно ложиться примерно в одно и то же время и избегать тяжёлой еды поздно вечером."

    if "шаг" in normalized_text or "прогул" in normalized_text:
        steps_goal = _get_goal_value(subject, MetricType.STEPS, RECOMMENDED_STEPS)
        return f"Текущий ориентир по активности — около {steps_goal} шагов в день, но лучше наращивать прогулки постепенно и в комфортном темпе."

    if "лекар" in normalized_text or "таблет" in normalized_text:
        return "Я могу подсказать ближайший приём лекарства по плану или отметить голосом, что лекарство уже принято."

    return (
        "Я могу помочь с планом дня, лекарствами, визитами к врачу, водой, сном, шагами, "
        "давлением и пульсом. Если зададите вопрос свободно, постараюсь ответить кратко и по делу."
    )


def _format_latest_metric(subject, metric_type):
    record = (
        MetricRecord.objects.filter(subject=subject, metric_type=metric_type)
        .order_by("-recorded_at")
        .first()
    )
    if not record:
        return None
    return f"{record.get_metric_type_display()}: {record.get_display_value()} ({timezone.localtime(record.recorded_at):%d.%m %H:%M})"


def _build_subject_context(subject):
    profile = getattr(subject, "profile", None)
    context_lines = [
        f"Подопечный: {subject.get_display_name()}",
        f"Возраст: {profile.age if profile and profile.age is not None else 'не указан'}",
        f"Хронические состояния: {', '.join(profile.chronic_conditions) if profile and profile.chronic_conditions else 'не указаны'}",
        f"Медицинские заметки: {profile.medical_notes if profile and profile.medical_notes else 'нет'}",
    ]

    latest_metric_lines = [
        _format_latest_metric(subject, MetricType.BLOOD_PRESSURE),
        _format_latest_metric(subject, MetricType.HEART_RATE),
        _format_latest_metric(subject, MetricType.STEPS),
        _format_latest_metric(subject, MetricType.WATER),
        _format_latest_metric(subject, MetricType.SLEEP),
    ]
    latest_metric_lines = [line for line in latest_metric_lines if line]
    if latest_metric_lines:
        context_lines.append("Последние метрики: " + " | ".join(latest_metric_lines))

    today_items = list(get_day_plan(subject, timezone.localdate())[:5])
    if today_items:
        context_lines.append(
            "План на сегодня: "
            + "; ".join(
                f"{item.title} ({item.time_label}, {'выполнено' if item.is_completed else 'нужно сделать'})"
                for item in today_items
            )
        )

    nearest_medicine = _find_nearest_task(subject, DailyPlanItem.Category.MEDICATION)
    if nearest_medicine:
        context_lines.append(
            "Ближайшее лекарство: "
            f"{nearest_medicine.title} {nearest_medicine.medicine_name or ''} "
            f"{nearest_medicine.scheduled_date:%d.%m.%Y} {nearest_medicine.time_label}"
        )

    nearest_doctor = _find_nearest_task(subject, DailyPlanItem.Category.DOCTOR_VISIT)
    if nearest_doctor:
        context_lines.append(
            "Ближайший врач: "
            f"{nearest_doctor.title} {nearest_doctor.doctor_specialty or ''} "
            f"{nearest_doctor.scheduled_date:%d.%m.%Y} {nearest_doctor.time_label}"
        )

    wearable_summary = get_latest_wearable_summary(subject)
    if wearable_summary:
        context_lines.append(
            "Последняя сводка браслета: "
            f"{wearable_summary.steps} шагов, пульс {wearable_summary.average_heart_rate or '—'}, "
            f"сон {wearable_summary.sleep_hours or '—'} ч."
        )

    return "\n".join(context_lines)


def _request_openai_health_answer(subject, transcript):
    if not settings.OPENAI_API_KEY:
        return ""

    try:
        from openai import OpenAI
    except ImportError:
        return ""

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    system_prompt = (
        "Ты голосовой помощник Janynda для пожилого человека и его семьи. "
        "Отвечай по-русски, очень коротко, простыми фразами и без канцелярита. "
        "Ты можешь говорить про давление, пульс, лекарства, воду, сон, шаги, прогулки, план дня и визиты к врачу. "
        "Не ставь диагноз и не назначай лечение. Если видишь потенциально опасную ситуацию, мягко советуй связаться с врачом, "
        "а при выраженных симптомах — срочно обратиться за неотложной помощью. "
        "Если вопрос требует чисел, опирайся на контекст пользователя и не выдумывай отсутствующие данные."
    )
    user_prompt = f"Контекст:\n{_build_subject_context(subject)}\n\nВопрос пользователя:\n{transcript}"
    try:
        completion = client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=220,
        )
    except Exception:
        return ""

    response_text = (completion.choices[0].message.content or "").strip()
    return response_text


def _build_health_answer(subject, transcript, normalized_text):
    assessment = _extract_health_assessment(normalized_text)
    if assessment:
        if assessment["metric_type"] == MetricType.BLOOD_PRESSURE:
            value = assessment["value"]
            return _build_blood_pressure_assessment(subject, value["systolic"], value["diastolic"]), {
                "source": "local-thresholds",
                "metric_type": MetricType.BLOOD_PRESSURE,
                "value": value,
            }
        if assessment["metric_type"] == MetricType.HEART_RATE:
            value = assessment["value"]
            return _build_heart_rate_assessment(subject, value["bpm"]), {
                "source": "local-thresholds",
                "metric_type": MetricType.HEART_RATE,
                "value": value,
            }

    ai_response = _request_openai_health_answer(subject, transcript)
    if ai_response:
        return ai_response, {"source": "openai", "model": settings.OPENAI_CHAT_MODEL}

    return _build_local_health_fallback(subject, normalized_text), {"source": "local-fallback"}


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
        plan_item = _match_today_item(subject, DailyPlanItem.Category.MEDICATION, medicine_name=medicine_name)
        if not plan_item:
            plan_item = _match_today_item(subject, DailyPlanItem.Category.MEDICATION)
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
        return _create_answer_log(
            actor=actor,
            subject=subject,
            transcript=transcript,
            response_text=_build_medicine_answer(subject),
        )

    if "когда к врачу" in normalized_text:
        return _create_answer_log(
            actor=actor,
            subject=subject,
            transcript=transcript,
            response_text=_build_doctor_answer(subject),
        )

    if "сколько воды" in normalized_text:
        return _create_answer_log(
            actor=actor,
            subject=subject,
            transcript=transcript,
            response_text=_build_water_answer(subject),
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

    health_assessment = _extract_health_assessment(normalized_text)
    if health_assessment:
        assessment_response, payload = _build_health_answer(subject, transcript, normalized_text)
        return _create_answer_log(
            actor=actor,
            subject=subject,
            transcript=transcript,
            response_text=assessment_response,
            payload=payload,
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

    if _looks_like_medication_log_command(normalized_text):
        medicine_name = _extract_medicine_name(normalized_text)
        return _create_confirmation_log(
            actor=actor,
            subject=subject,
            transcript=transcript,
            action_type=VoiceCommandLog.ActionType.MEDICATION_LOG,
            payload={"kind": "medication", "medicine_name": medicine_name},
        )

    if _looks_like_doctor_log_command(normalized_text):
        return _create_confirmation_log(
            actor=actor,
            subject=subject,
            transcript=transcript,
            action_type=VoiceCommandLog.ActionType.DOCTOR_LOG,
            payload={"kind": "doctor"},
        )

    if any(keyword in normalized_text for keyword in HEALTH_KEYWORDS):
        assessment_response, payload = _build_health_answer(subject, transcript, normalized_text)
        return _create_answer_log(
            actor=actor,
            subject=subject,
            transcript=transcript,
            response_text=assessment_response,
            payload=payload,
        )

    return VoiceCommandLog.objects.create(
        user=actor,
        subject=subject,
        transcript=transcript,
        response_text=(
            "Я могу помочь с планом, лекарствами, визитами к врачу, водой, сном, шагами, "
            "давлением и пульсом. Скажите, например: «Что у меня сегодня по плану?»."
        ),
        action_type=VoiceCommandLog.ActionType.UNSUPPORTED,
        payload={},
        confirmed=True,
    )
