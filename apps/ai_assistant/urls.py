from django.urls import path

from .views import ai_assistant_view


urlpatterns = [
    path("", ai_assistant_view, name="ai-assistant"),
]
