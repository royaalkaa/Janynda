from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Challenge


@login_required
def challenge_list_view(request):
    challenges = (
        Challenge.objects.filter(group__owner=request.user)
        .prefetch_related("participants__user")
        .order_by("-created_at")
    )
    return render(request, "challenges/list.html", {"challenges": challenges[:20]})
