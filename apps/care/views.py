from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.notifications.models import Notification

from .forms import (
    DailyPlanItemForm,
    LocationPingForm,
    LocationSharingSettingsForm,
    SafeZoneForm,
    WearableDailySummaryForm,
    WearableDeviceForm,
)
from .models import CommunityPlace, DailyPlanItem, FavoritePlace, SafeZone
from .services import (
    RECOMMENDED_SLEEP_HOURS,
    RECOMMENDED_STEPS,
    can_manage_subject,
    create_notification,
    get_accessible_subject,
    get_base_template,
    get_completed_task_history,
    get_featured_places,
    get_goal_indicator,
    get_last_location_ping,
    get_latest_wearable_summary,
    get_or_create_location_settings,
    get_place_suggestions,
    get_plan_summary,
    get_plan_window,
    get_recent_location_pings,
    get_related_subjects,
    get_wearable_stats,
    serialize_location_pings,
    serialize_safe_zones,
)


def _resolve_target_date(request):
    requested_date = parse_date(request.GET.get("date", "")) if request.GET.get("date") else None
    return requested_date or timezone.localdate()


def _plan_redirect(subject, target_date):
    if subject:
        return f"{reverse('care-plan-subject', args=[subject.id])}?date={target_date.isoformat()}"
    return f"{reverse('care-plan')}?date={target_date.isoformat()}"


def _subject_route(name_self, name_subject, subject, current_user):
    if subject != current_user:
        return reverse(name_subject, args=[subject.id])
    return reverse(name_self)


def _subject_query(subject, current_user):
    if subject != current_user:
        return f"subject_id={subject.id}"
    return ""


@login_required
def daily_plan_view(request, subject_id=None):
    subject = get_accessible_subject(
        request.user,
        subject_id,
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )
    target_date = _resolve_target_date(request)

    if request.method == "POST":
        form = DailyPlanItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.subject = subject
            item.created_by = request.user
            item.save()
            form.sync_reminders(item)
            messages.success(request, "Задача сохранена в план дня.")
            return redirect(_plan_redirect(subject if subject != request.user else None, item.scheduled_date))
    else:
        form = DailyPlanItemForm(initial={"scheduled_date": target_date})

    _, plan_map = get_plan_window(subject, target_date, days=5)
    summary = get_plan_summary(subject, target_date)

    return render(
        request,
        "care/daily_plan.html",
        {
            "subject": subject,
            "plan_form": form,
            "target_date": target_date,
            "day_items": summary["items"],
            "summary": summary,
            "plan_map": plan_map,
            "base_template": get_base_template(request.user, subject),
            "subject_choices": get_related_subjects(request.user),
        },
    )


@login_required
def edit_task(request, task_id):
    task = get_object_or_404(DailyPlanItem.objects.select_related("subject"), pk=task_id)
    if not can_manage_subject(request.user, task.subject):
        raise Http404

    if request.method == "POST":
        form = DailyPlanItemForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save()
            form.sync_reminders(task)
            messages.success(request, "Задача обновлена.")
            return redirect(_plan_redirect(task.subject if task.subject != request.user else None, task.scheduled_date))
    else:
        form = DailyPlanItemForm(instance=task)

    return render(
        request,
        "care/task_edit.html",
        {
            "subject": task.subject,
            "task": task,
            "plan_form": form,
            "base_template": get_base_template(request.user, task.subject),
            "subject_choices": get_related_subjects(request.user),
        },
    )


@login_required
@require_POST
def delete_task(request, task_id):
    task = get_object_or_404(DailyPlanItem.objects.select_related("subject"), pk=task_id)
    if not can_manage_subject(request.user, task.subject):
        raise Http404

    subject = task.subject
    target_date = task.scheduled_date
    task.delete()
    messages.success(request, "Задача удалена.")
    return redirect(_plan_redirect(subject if subject != request.user else None, target_date))


@login_required
def task_history(request):
    subject = get_accessible_subject(
        request.user,
        request.GET.get("subject_id"),
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )
    date_from = parse_date(request.GET.get("date_from", "")) if request.GET.get("date_from") else None
    date_to = parse_date(request.GET.get("date_to", "")) if request.GET.get("date_to") else None

    return render(
        request,
        "care/task_history.html",
        {
            "subject": subject,
            "history_items": get_completed_task_history(subject, date_from=date_from, date_to=date_to),
            "date_from": date_from,
            "date_to": date_to,
            "base_template": get_base_template(request.user, subject),
            "subject_choices": get_related_subjects(request.user),
        },
    )


@login_required
@require_POST
def daily_plan_toggle_view(request, pk):
    item = get_object_or_404(DailyPlanItem.objects.select_related("subject"), pk=pk)
    if not can_manage_subject(request.user, item.subject):
        raise Http404

    if item.is_completed:
        item.mark_pending()
        messages.success(request, "Задача снова в статусе «нужно сделать».")
    else:
        item.mark_completed(request.user)
        messages.success(request, "Задача отмечена как выполненная.")

    return redirect(_plan_redirect(item.subject if item.subject != request.user else None, item.scheduled_date))


@login_required
def places_view(request):
    subject = get_accessible_subject(
        request.user,
        request.GET.get("subject_id"),
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )
    settings_obj = get_or_create_location_settings(subject)
    city = request.GET.get("city", "").strip() or settings_obj.city or "Алматы"
    category = request.GET.get("category", "").strip() or None
    favorites_only = request.GET.get("favorites") == "1"
    places = get_place_suggestions(
        city=city,
        category=category,
        subject=subject,
        favorites_only=favorites_only,
    )

    return render(
        request,
        "care/places.html",
        {
            "subject": subject,
            "places": places,
            "featured_places": [] if favorites_only else get_featured_places(city=city, subject=subject),
            "selected_city": city,
            "selected_category": category or "",
            "favorites_only": favorites_only,
            "place_categories": [("", "Все категории"), *list(CommunityPlace.Category.choices)],
            "places_map_data": [place for place in places if place.get("latitude") and place.get("longitude")],
            "base_template": get_base_template(request.user, subject),
            "subject_choices": get_related_subjects(request.user),
            "subject_query": _subject_query(subject, request.user),
        },
    )


@login_required
@require_POST
def toggle_favorite(request, place_id):
    subject = get_accessible_subject(
        request.user,
        request.POST.get("subject_id"),
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )
    if not can_manage_subject(request.user, subject):
        raise Http404

    place = get_object_or_404(CommunityPlace, pk=place_id)
    favorite, created = FavoritePlace.objects.get_or_create(subject=subject, place=place)
    if not created:
        favorite.delete()
        messages.success(request, "Место убрано из избранного.")
    else:
        messages.success(request, "Место добавлено в избранное.")

    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)
    redirect_url = reverse("care-places")
    query = _subject_query(subject, request.user)
    if query:
        redirect_url = f"{redirect_url}?{query}"
    return redirect(redirect_url)


@login_required
def location_view(request, subject_id=None):
    subject = get_accessible_subject(
        request.user,
        subject_id,
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )
    settings_obj = get_or_create_location_settings(subject)
    period = request.GET.get("period", "today")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "settings":
            settings_form = LocationSharingSettingsForm(request.POST, instance=settings_obj)
            ping_form = LocationPingForm()
            if settings_form.is_valid():
                settings_obj = settings_form.save()
                if settings_obj.tracking_enabled:
                    settings_obj.register_consent()
                messages.success(request, "Настройки геолокации сохранены.")
                return redirect(_subject_route("care-location", "care-location-subject", subject, request.user))
        else:
            settings_form = LocationSharingSettingsForm(instance=settings_obj)
            ping_form = LocationPingForm(request.POST)
            if ping_form.is_valid():
                ping = ping_form.save(commit=False)
                ping.subject = subject
                ping.created_by = request.user
                ping.save()
                messages.success(request, "Текущее местоположение обновлено.")
                return redirect(_subject_route("care-location", "care-location-subject", subject, request.user))
    else:
        settings_form = LocationSharingSettingsForm(instance=settings_obj)
        ping_form = LocationPingForm()

    recent_locations = get_recent_location_pings(subject, period=period)
    safe_zones = subject.safe_zones.order_by("-is_home", "name")

    return render(
        request,
        "care/location.html",
        {
            "subject": subject,
            "settings_form": settings_form,
            "ping_form": ping_form,
            "location_settings": settings_obj,
            "last_location": get_last_location_ping(subject),
            "recent_locations": recent_locations,
            "period": period,
            "safe_zones": safe_zones,
            "location_map_data": serialize_location_pings(list(recent_locations)[::-1]),
            "safe_zones_map_data": serialize_safe_zones(safe_zones),
            "base_template": get_base_template(request.user, subject),
            "subject_choices": get_related_subjects(request.user),
            "subject_query": _subject_query(subject, request.user),
        },
    )


@login_required
def safe_zones(request):
    subject = get_accessible_subject(
        request.user,
        request.GET.get("subject_id") or request.POST.get("subject_id"),
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )
    if not can_manage_subject(request.user, subject):
        raise Http404

    edit_zone = None
    if request.GET.get("zone_id"):
        edit_zone = get_object_or_404(SafeZone, pk=request.GET["zone_id"], subject=subject)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "delete":
            zone = get_object_or_404(SafeZone, pk=request.POST.get("zone_id"), subject=subject)
            zone.delete()
            messages.success(request, "Безопасная зона удалена.")
            return redirect(f"{reverse('safe_zones')}?{_subject_query(subject, request.user)}")

        instance = None
        if request.POST.get("zone_id"):
            instance = get_object_or_404(SafeZone, pk=request.POST["zone_id"], subject=subject)
        form = SafeZoneForm(request.POST, instance=instance)
        if form.is_valid():
            zone = form.save(commit=False)
            zone.subject = subject
            if zone.is_home:
                subject.safe_zones.exclude(pk=zone.pk).update(is_home=False)
            zone.save()
            settings_obj = get_or_create_location_settings(subject)
            if zone.is_home:
                settings_obj.home_latitude = zone.latitude
                settings_obj.home_longitude = zone.longitude
                settings_obj.save(update_fields=["home_latitude", "home_longitude"])
            messages.success(request, "Безопасная зона сохранена.")
            return redirect(f"{reverse('safe_zones')}?{_subject_query(subject, request.user)}")
    else:
        form = SafeZoneForm(instance=edit_zone)

    zones = subject.safe_zones.order_by("-is_home", "name")
    return render(
        request,
        "care/safe_zones.html",
        {
            "subject": subject,
            "zone_form": form,
            "zones": zones,
            "edit_zone": edit_zone,
            "safe_zones_map_data": serialize_safe_zones(zones),
            "base_template": get_base_template(request.user, subject),
            "subject_choices": get_related_subjects(request.user),
            "subject_query": _subject_query(subject, request.user),
        },
    )


@login_required
@require_POST
def emergency_sos(request):
    subject = get_accessible_subject(
        request.user,
        request.POST.get("subject_id"),
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )
    if not can_manage_subject(request.user, subject):
        raise Http404

    settings_obj = get_or_create_location_settings(subject)
    latitude = request.POST.get("latitude") or settings_obj.home_latitude
    longitude = request.POST.get("longitude") or settings_obj.home_longitude
    last_location = get_last_location_ping(subject)
    latitude = latitude or getattr(last_location, "latitude", None)
    longitude = longitude or getattr(last_location, "longitude", None)
    if latitude is None or longitude is None:
        messages.error(request, "Для SOS нужны координаты. Сначала сохраните хотя бы одну точку.")
        return redirect(_subject_route("care-location", "care-location-subject", subject, request.user))

    ping = subject.location_pings.create(
        created_by=request.user,
        latitude=latitude,
        longitude=longitude,
        source="manual",
        note="SOS сигнал",
        is_emergency=True,
    )

    title = "SOS сигнал"
    body = (
        f"{subject.get_display_name()} отправил(а) сигнал SOS. "
        f"Координаты: {latitude}, {longitude}."
    )
    recipients = [subject, *subject.being_observed.select_related("observer")]
    sent_to = set()
    for item in recipients:
        recipient = item if hasattr(item, "id") else item.observer
        if hasattr(item, "observer"):
            if not item.can_view_location:
                continue
            recipient = item.observer
        if recipient.id in sent_to:
            continue
        sent_to.add(recipient.id)
        create_notification(
            recipient=recipient,
            title=title,
            body=body,
            severity=Notification.Severity.CRITICAL,
            category=Notification.Category.SYSTEM,
            related_subject=subject,
        )
    messages.success(request, "SOS сигнал отправлен.")
    return redirect(_subject_route("care-location", "care-location-subject", subject, request.user))


@login_required
def wearables_view(request, subject_id=None):
    subject = get_accessible_subject(
        request.user,
        subject_id,
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "device":
            device_form = WearableDeviceForm(request.POST)
            summary_form = WearableDailySummaryForm(subject=subject)
            if device_form.is_valid():
                device = device_form.save(commit=False)
                device.subject = subject
                device.save()
                messages.success(request, "Браслет добавлен.")
                return redirect(_subject_route("care-wearables", "care-wearables-subject", subject, request.user))
        else:
            device_form = WearableDeviceForm()
            summary_form = WearableDailySummaryForm(request.POST, subject=subject)
            if summary_form.is_valid():
                summary = summary_form.save(commit=False)
                summary.imported_by = request.user
                summary.save()
                summary.device.register_sync()
                messages.success(request, "Сводка с браслета сохранена.")
                return redirect(_subject_route("care-wearables", "care-wearables-subject", subject, request.user))
    else:
        device_form = WearableDeviceForm()
        summary_form = WearableDailySummaryForm(
            subject=subject,
            initial={"summary_date": timezone.localdate()},
        )

    devices = subject.wearable_devices.prefetch_related("daily_summaries").order_by("-is_active", "nickname")

    return render(
        request,
        "care/wearables.html",
        {
            "subject": subject,
            "device_form": device_form,
            "summary_form": summary_form,
            "devices": devices,
            "latest_summary": get_latest_wearable_summary(subject),
            "base_template": get_base_template(request.user, subject),
            "subject_choices": get_related_subjects(request.user),
        },
    )


@login_required
def wearables_stats(request):
    subject = get_accessible_subject(
        request.user,
        request.GET.get("subject_id"),
        default_to_first_observed=request.user.is_observer and not request.user.is_subject,
    )
    period = request.GET.get("period", "week")
    summaries, aggregates, chart_data = get_wearable_stats(subject, period=period)
    latest_summary = get_latest_wearable_summary(subject)
    latest_steps = latest_summary.steps if latest_summary else None
    latest_sleep = float(latest_summary.sleep_hours) if latest_summary and latest_summary.sleep_hours else None

    return render(
        request,
        "care/wearables_stats.html",
        {
            "subject": subject,
            "period": period,
            "summaries": summaries,
            "aggregates": aggregates,
            "chart_data": chart_data,
            "latest_summary": latest_summary,
            "recommended_steps": RECOMMENDED_STEPS,
            "recommended_sleep_hours": RECOMMENDED_SLEEP_HOURS,
            "steps_indicator": get_goal_indicator(latest_steps, RECOMMENDED_STEPS),
            "sleep_indicator": get_goal_indicator(latest_sleep, RECOMMENDED_SLEEP_HOURS),
            "base_template": get_base_template(request.user, subject),
            "subject_choices": get_related_subjects(request.user),
            "subject_query": _subject_query(subject, request.user),
        },
    )
