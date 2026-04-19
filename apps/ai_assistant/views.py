from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.family.models import FamilyMembership
from apps.dashboard.services import get_latest_comment_for_subject
from .services import handle_voice_command


@login_required
def ai_assistant_view(request):
    base_template = (
        "base/subject.html"
        if request.user.is_subject and not request.user.is_observer
        else "base/observer.html"
    )
    subject = request.user
    if request.user.is_observer and request.user.observing.select_related("subject").exists():
        first_link = request.user.observing.select_related("subject").first()
        subject = first_link.subject or request.user

    comment = get_latest_comment_for_subject(subject) if subject else None
    return render(
        request,
        "ai/chat.html",
        {"subject": subject, "comment": comment, "base_template": base_template},
    )


def _get_target_subject(request_user, subject_id=None):
    if not subject_id:
        return request_user

    subject = get_object_or_404(User, pk=subject_id)
    allowed = FamilyMembership.objects.filter(observer=request_user, subject=subject).exists()
    if subject != request_user and not allowed:
        raise Http404
    return subject


@login_required
@require_POST
def ai_voice_command_view(request):
    subject = _get_target_subject(request.user, request.POST.get("subject_id") or None)
    transcript = (request.POST.get("transcript") or request.POST.get("confirmation_text") or "").strip()
    log = handle_voice_command(
        actor=request.user,
        subject=subject,
        transcript=transcript,
        confirmation_log_id=request.POST.get("confirmation_log_id") or None,
        confirmation=request.POST.get("confirmation") or None,
    )
    return JsonResponse(
        {
            "log_id": log.pk,
            "response": log.response_text,
            "action_type": log.action_type,
            "requires_confirmation": log.requires_confirmation and not log.confirmed,
            "confirmed": log.confirmed,
        }
    )
