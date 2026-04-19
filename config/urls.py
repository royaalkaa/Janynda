from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("rosetta/", include("rosetta.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("onboarding/", include("apps.accounts.urls_onboarding")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("family/", include("apps.family.urls")),
    path("health/", include("apps.health.urls")),
    path("challenges/", include("apps.challenges.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("weather/", include("apps.weather.urls")),
    path("ai/", include("apps.ai_assistant.urls")),
    path("care/", include("apps.care.urls")),
    path("payment/", include("apps.payment.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("entry/<uuid:token>/", include("apps.accounts.urls_magic")),
    path("", include("apps.dashboard.urls_landing")),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
