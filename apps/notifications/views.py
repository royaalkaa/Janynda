from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Notification


def _get_post_action_redirect(request):
    referer = request.META.get("HTTP_REFERER")
    allowed_hosts = set(settings.ALLOWED_HOSTS)
    allowed_hosts.add(request.get_host())

    if referer and url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts=allowed_hosts,
        require_https=request.is_secure(),
    ):
        return referer

    return reverse("notifications-list")


@login_required
def notification_list_view(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by("-created_at")
    return render(request, "notifications/list.html", {"notifications": notifications[:50]})


@login_required
@require_POST
def notification_read_view(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    return redirect(_get_post_action_redirect(request))


@login_required
@require_POST
def notification_read_all_view(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )
    return redirect(_get_post_action_redirect(request))
