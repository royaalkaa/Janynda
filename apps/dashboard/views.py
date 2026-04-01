from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.care.services import (
    get_featured_places,
    get_base_template,
    get_last_location_ping,
    get_latest_wearable_summary,
    get_plan_summary,
)
from apps.family.models import FamilyMembership
from apps.health.forms import BloodPressureEntryForm, HeartRateEntryForm, StepsEntryForm
from apps.weather.models import WeatherCache

from .services import (
    get_latest_comment_for_subject,
    get_latest_metrics_for_subject,
    get_observer_memberships_with_snapshots,
    get_subject_chart_payload,
    get_user_challenges,
)


def landing_view(request):
    return render(request, "dashboard/landing.html")


@login_required
def dashboard_home_view(request):
    if not request.user.onboarding_completed:
        return redirect("onboarding-step", step=1)

    if request.user.is_observer and request.user.observing.exists():
        return redirect("observer-dashboard")
    if request.user.is_subject:
        return redirect("subject-dashboard")
    return redirect("family-overview")


@login_required
def observer_dashboard_view(request):
    if not request.user.onboarding_completed:
        return redirect("onboarding-step", step=1)

    snapshots = get_observer_memberships_with_snapshots(request.user)
    focus_subject = snapshots[0]["membership"].subject if snapshots and snapshots[0]["membership"].subject else None
    challenge_list = get_user_challenges(request.user)
    weather = WeatherCache.objects.order_by("-fetched_at").first()
    ai_comment = get_latest_comment_for_subject(focus_subject) if focus_subject else None
    focus_plan_summary = get_plan_summary(focus_subject) if focus_subject else {"items": [], "total": 0, "completed": 0, "pending": 0}
    focus_last_location = get_last_location_ping(focus_subject) if focus_subject else None
    focus_wearable_summary = get_latest_wearable_summary(focus_subject) if focus_subject else None

    return render(
        request,
        "dashboard/observer_dashboard.html",
        {
            "snapshots": snapshots,
            "focus_subject": focus_subject,
            "weather": weather,
            "challenge_list": challenge_list,
            "ai_comment": ai_comment,
            "focus_plan_summary": focus_plan_summary,
            "focus_last_location": focus_last_location,
            "focus_wearable_summary": focus_wearable_summary,
            "featured_places": get_featured_places(),
        },
    )


@login_required
def subject_dashboard_view(request):
    if not request.user.onboarding_completed:
        return redirect("onboarding-step", step=1)

    latest_metrics = get_latest_metrics_for_subject(request.user)
    chart_payload = get_subject_chart_payload(request.user)
    ai_comment = get_latest_comment_for_subject(request.user)
    family_links = FamilyMembership.objects.filter(subject=request.user).select_related("observer")
    today_plan_summary = get_plan_summary(request.user)
    last_location = get_last_location_ping(request.user)
    wearable_summary = get_latest_wearable_summary(request.user)

    return render(
        request,
        "dashboard/subject_dashboard.html",
        {
            "base_template": get_base_template(request.user, request.user),
            "latest_metrics": latest_metrics,
            "blood_pressure_form": BloodPressureEntryForm(),
            "heart_rate_form": HeartRateEntryForm(),
            "steps_form": StepsEntryForm(),
            "chart_payload": chart_payload,
            "ai_comment": ai_comment,
            "family_links": family_links,
            "today_plan_summary": today_plan_summary,
            "last_location": last_location,
            "wearable_summary": wearable_summary,
            "featured_places": get_featured_places(),
        },
    )
