from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.dashboard.services import get_latest_comment_for_subject


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
