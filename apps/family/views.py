from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.accounts.services import attach_subject_to_observer

from .forms import FamilyMemberForm


@login_required
def family_overview_view(request):
    memberships = (
        request.user.observing.select_related("group", "subject", "magic_link")
        .order_by("created_at")
    )
    group = request.user.owned_groups.order_by("created_at").first()

    if request.method == "POST":
        form = FamilyMemberForm(request.POST)
        if form.is_valid():
            membership = attach_subject_to_observer(
                request.user,
                group_name=form.cleaned_data.get("group_name"),
                relative_name=form.cleaned_data["subject_name"],
                relation=form.cleaned_data["relation"],
                relative_email=form.cleaned_data.get("subject_email"),
                can_view_location=form.cleaned_data.get("can_view_location", False),
            )
            messages.success(
                request,
                f"{membership.get_subject_display_name()} добавлен. Можно отправить magic link.",
            )
            return redirect("family-overview")
    else:
        form = FamilyMemberForm(
            initial={"group_name": group.name if group else f"Семья {request.user.get_display_name()}"}
        )

    invite_rows = []
    for membership in memberships:
        invite_url = None
        if membership.magic_link:
            invite_url = request.build_absolute_uri(
                reverse("magic-entry", kwargs={"token": membership.magic_link.token})
            )
        invite_rows.append({"membership": membership, "invite_url": invite_url})

    return render(
        request,
        "family/manage.html",
        {"form": form, "group": group, "invite_rows": invite_rows},
    )
