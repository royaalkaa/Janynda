from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponse
from django.core.mail import send_mail
from django.conf import settings

from .models import Notification


@login_required
def notification_list_view(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by("-created_at")
    base_template = (
        "base/subject.html"
        if request.user.is_subject and not request.user.is_observer
        else "base/observer.html"
    )
    return render(
        request,
        "notifications/list.html",
        {
            "notifications": notifications[:50],
            "base_template": base_template,
        },
    )


@login_required
@require_POST
def notification_read_view(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    redirect_to = request.META.get("HTTP_REFERER")
    if not redirect_to or not url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        redirect_to = reverse("notifications-list")
    return redirect(redirect_to)


@login_required
@require_POST
def notification_read_all_view(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )
    return redirect("notifications-list")


@login_required
@require_POST
def sos_trigger_view(request):
    """SOS сигнал: создаёт CRITICAL уведомление и оповещает наблюдателей."""
    user = request.user
    profile = getattr(user, "profile", None)
    emergency_contact = profile.emergency_contact if profile else ""

    # Уведомление себе
    Notification.objects.create(
        recipient=user,
        title="SOS сигнал отправлен",
        body="Вы активировали SOS. Ваши наблюдатели уведомлены.",
        severity=Notification.Severity.CRITICAL,
        category=Notification.Category.SYSTEM,
    )

    # Уведомить всех наблюдателей этого субъекта
    if user.is_subject:
        from apps.family.models import FamilyMembership
        for m in FamilyMembership.objects.filter(subject=user).select_related("observer"):
            Notification.objects.create(
                recipient=m.observer,
                title=f"🆘 SOS от {user.get_display_name()}",
                body=f"{user.get_display_name()} нажал(а) кнопку SOS. Требуется срочная помощь!",
                severity=Notification.Severity.CRITICAL,
                category=Notification.Category.SYSTEM,
                related_subject=user,
            )

    # Email на контакт экстренной помощи
    if emergency_contact:
        send_mail(
            subject=f"[SOS] {user.get_display_name()} нуждается в помощи",
            message=(
                f"Пользователь {user.get_display_name()} нажал кнопку SOS "
                f"в приложении Janynda.\n\nПожалуйста, свяжитесь с ним немедленно."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[emergency_contact],
            fail_silently=True,
        )

    return HttpResponse(
        '<div class="j-sos-sent"><i class="bi bi-check-circle-fill"></i> Помощь вызвана!</div>',
        content_type="text/html",
    )
