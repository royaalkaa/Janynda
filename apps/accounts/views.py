from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    LoginForm,
    OnboardingFamilyForm,
    OnboardingPreferencesForm,
    OnboardingProfileForm,
    OnboardingRoleForm,
    SignUpForm,
)
from .models import MagicLink
from .services import finalize_onboarding


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard-home")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
            except ValidationError:
                pass
            else:
                login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
                messages.success(request, "Аккаунт создан. Давайте настроим Janynda под вас.")
                return redirect("onboarding-step", step=1)
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


ONBOARDING_STEPS = {
    1: {
        "form_class": OnboardingRoleForm,
        "title": "Какой сценарий для вас основной?",
        "subtitle": "От этого зависит стартовый интерфейс: наблюдение за близкими или быстрый ввод для себя.",
    },
    2: {
        "form_class": OnboardingProfileForm,
        "title": "Базовый профиль здоровья",
        "subtitle": "Нужен для персональных порогов и более понятных подсказок на дашборде.",
    },
    3: {
        "form_class": OnboardingFamilyForm,
        "title": "Добавьте первого родственника",
        "subtitle": "После этого вы сразу увидите, как работает семейный мониторинг и magic link.",
    },
    4: {
        "form_class": OnboardingPreferencesForm,
        "title": "Последние настройки перед стартом",
        "subtitle": "Напоминания, приоритетная метрика и цель по шагам помогут быстрее получить первый результат.",
    },
}


def _get_initial_for_step(user, step):
    profile = user.profile
    notification_settings = getattr(user, "notification_settings", None)
    if step == 1:
        return {"role": user.role}
    if step == 2:
        return {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "date_of_birth": profile.date_of_birth,
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
        }
    if step == 3:
        return request_session_family_defaults(user)
    if step == 4:
        return {
            "reminder_time": getattr(notification_settings, "reminder_time", time(20, 0)),
            "health_alerts": getattr(notification_settings, "health_alerts", True),
            "weather_alerts": getattr(notification_settings, "weather_alerts", True),
            "daily_steps_goal": 8000,
        }
    return {}


def request_session_family_defaults(user):
    group = user.owned_groups.order_by("created_at").first()
    first_membership = user.observing.select_related("subject").order_by("created_at").first()
    return {
        "group_name": group.name if group else f"Семья {user.get_display_name()}",
        "relative_name": first_membership.subject_name if first_membership else "",
        "relation": first_membership.relation if first_membership else "",
        "relative_email": first_membership.subject_email if first_membership else "",
    }


@login_required
def onboarding_start_redirect(request):
    if request.user.onboarding_completed:
        return redirect("dashboard-home")
    return redirect("onboarding-step", step=1)


@login_required
def onboarding_step_view(request, step):
    if step not in ONBOARDING_STEPS:
        raise Http404

    config = ONBOARDING_STEPS[step]
    form_class = config["form_class"]

    if step == 3:
        form = form_class(
            request.POST or None,
            initial=_get_initial_for_step(request.user, step),
            role=request.user.role,
        )
    else:
        form = form_class(request.POST or None, initial=_get_initial_for_step(request.user, step))

    if request.method == "POST" and form.is_valid():
        if step == 1:
            request.user.role = form.cleaned_data["role"]
            request.user.save(update_fields=["role"])
        elif step == 2:
            request.user.first_name = form.cleaned_data["first_name"]
            request.user.last_name = form.cleaned_data["last_name"]
            request.user.phone = form.cleaned_data["phone"]
            request.user.save(update_fields=["first_name", "last_name", "phone"])

            profile = request.user.profile
            profile.date_of_birth = form.cleaned_data["date_of_birth"]
            profile.height_cm = form.cleaned_data["height_cm"]
            profile.weight_kg = form.cleaned_data["weight_kg"]
            profile.save(update_fields=["date_of_birth", "height_cm", "weight_kg"])
        elif step == 3:
            request.session["onboarding_family"] = form.cleaned_data
        elif step == 4:
            finalize_onboarding(
                request.user,
                family_data=request.session.get("onboarding_family", {}),
                preferences_data=form.cleaned_data,
            )
            request.session.pop("onboarding_family", None)
            messages.success(request, "Janynda готов. Можно переходить к дашборду.")
            return redirect("dashboard-home")

        return redirect("onboarding-step", step=min(step + 1, 4))

    return render(
        request,
        "onboarding/step.html",
        {
            "form": form,
            "step": step,
            "steps": ONBOARDING_STEPS,
            "title": config["title"],
            "subtitle": config["subtitle"],
            "is_last_step": step == max(ONBOARDING_STEPS),
        },
    )


def magic_entry_view(request, token):
    link = get_object_or_404(MagicLink.objects.select_related("user"), token=token)
    if not link.is_valid:
        return render(request, "accounts/magic_invalid.html", {"link": link}, status=410)

    login(request, link.user, backend=settings.AUTHENTICATION_BACKENDS[0])
    messages.success(request, "Вход выполнен. Можно быстро внести показатели.")
    return redirect("subject-dashboard")
