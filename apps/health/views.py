from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.accounts.models import User
from apps.family.models import FamilyMembership

from .forms import METRIC_FORM_MAP
from .models import MetricRecord, MetricType


def _get_target_subject(request_user, subject_id=None):
    if subject_id:
        subject = get_object_or_404(User, pk=subject_id)
        allowed = FamilyMembership.objects.filter(observer=request_user, subject=subject).exists()
        if subject != request_user and not allowed:
            raise Http404
        return subject
    return request_user


@login_required
def quick_entry_view(request, metric_type):
    if metric_type not in METRIC_FORM_MAP:
        raise Http404

    form_class = METRIC_FORM_MAP[metric_type]
    form = form_class(request.POST or None)
    subject = _get_target_subject(request.user, request.POST.get("subject_id") or None)

    if request.method == "POST" and form.is_valid():
        payload = build_payload(metric_type, form.cleaned_data)
        record = MetricRecord.objects.create(
            subject=subject,
            metric_type=metric_type,
            value_json=payload,
            source=MetricRecord.Source.MAGIC_LINK if request.path.startswith("/entry/") else MetricRecord.Source.MANUAL,
        )
        return render(
            request,
            "health/partials/quick_entry_result.html",
            {"record": record, "subject": subject},
        )

    return render(
        request,
        "health/partials/quick_entry_result.html",
        {"form": form, "metric_type": metric_type, "subject": subject},
        status=400,
    )


def build_payload(metric_type, cleaned_data):
    if metric_type == MetricType.BLOOD_PRESSURE:
        return {
            "systolic": cleaned_data["systolic"],
            "diastolic": cleaned_data["diastolic"],
            "pulse": cleaned_data.get("pulse"),
        }
    if metric_type == MetricType.HEART_RATE:
        return {"bpm": cleaned_data["bpm"]}
    if metric_type == MetricType.STEPS:
        return {"steps": cleaned_data["steps"]}
    return cleaned_data


@login_required
def metric_history_view(request, subject_id=None):
    subject = _get_target_subject(request.user, subject_id)
    metric_type = request.GET.get("metric_type")
    records = MetricRecord.objects.filter(subject=subject)
    if metric_type:
        records = records.filter(metric_type=metric_type)
    records = records.order_by("-recorded_at")[:50]

    base_template = "base/subject.html" if subject == request.user and request.user.is_subject else "base/observer.html"
    return render(
        request,
        "health/history.html",
        {
            "subject": subject,
            "records": records,
            "selected_metric_type": metric_type,
            "metric_choices": MetricType.choices,
            "base_template": base_template,
        },
    )
