from django.urls import path

from .views import ai_assistant_view, ai_voice_command_view


urlpatterns = [
    path("", ai_assistant_view, name="ai-assistant"),
    path("voice-command/", ai_voice_command_view, name="ai-voice-command"),
]
