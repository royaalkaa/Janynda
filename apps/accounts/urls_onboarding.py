from django.urls import path

from .views import onboarding_start_redirect, onboarding_step_view


urlpatterns = [
    path("", onboarding_start_redirect, name="onboarding-start"),
    path("step/<int:step>/", onboarding_step_view, name="onboarding-step"),
]
