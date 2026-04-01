from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.care.services import get_accessible_subject, get_base_template, get_related_subjects
from apps.dashboard.services import get_latest_comment_for_subject

from .models import VoiceCommandLog
from .services import handle_voice_command

@login_required
def ai_assistant_view(request):
    subject = get_accessible_subject(
        request.user,
        request.GET.get("subject_id"),
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )

    comment = get_latest_comment_for_subject(subject) if subject else None
    return render(
        request,
        "ai/chat.html",
        {
            "subject": subject,
            "comment": comment,
            "base_template": get_base_template(request.user, subject),
            "voice_logs": VoiceCommandLog.objects.filter(subject=subject).select_related("user")[:8],
            "unread_system_voice_logs": [
                {"id": item.id, "response_text": item.response_text}
                for item in VoiceCommandLog.objects.filter(
                    subject=subject,
                    is_system_message=True,
                    is_read=False,
                ).order_by("created_at")
            ],
            "subject_choices": get_related_subjects(request.user),
        },
    )


@login_required
@require_POST
def voice_command_action_view(request):
    subject = get_accessible_subject(
        request.user,
        request.POST.get("subject_id"),
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )
    transcript = request.POST.get("transcript", "").strip() or request.POST.get("confirmation_text", "").strip()
    confirmation = request.POST.get("confirmation")
    confirmation_log_id = request.POST.get("confirmation_log_id")
    if not transcript and not confirmation:
        return JsonResponse({"ok": False, "error": "Нужен текст команды."}, status=400)

    command = handle_voice_command(
        actor=request.user,
        subject=subject,
        transcript=transcript or "Подтверждение",
        confirmation=confirmation,
        confirmation_log_id=confirmation_log_id,
    )
    return JsonResponse(
        {
            "ok": True,
            "response": command.response_text,
            "action_type": command.action_type,
            "subject": subject.get_display_name(),
            "created_at": command.created_at.strftime("%d.%m.%Y %H:%M"),
            "requires_confirmation": command.requires_confirmation,
            "confirmed": command.confirmed,
            "log_id": command.id,
        }
    )


@login_required
@require_POST
def mark_voice_messages_read_view(request):
    ids = request.POST.getlist("ids[]") or request.POST.getlist("ids")
    VoiceCommandLog.objects.filter(
        is_system_message=True,
        pk__in=ids,
    ).filter(
        models.Q(user=request.user)
        | models.Q(subject=request.user)
        | models.Q(subject__being_observed__observer=request.user)
    ).distinct().update(is_read=True)
    return JsonResponse({"ok": True})
