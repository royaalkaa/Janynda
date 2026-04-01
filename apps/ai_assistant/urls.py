from django.urls import path

from .views import ai_assistant_view, mark_voice_messages_read_view, voice_command_action_view


urlpatterns = [
    path("", ai_assistant_view, name="ai-assistant"),
    path("voice-command/", voice_command_action_view, name="ai-voice-command"),
    path("voice-messages/read/", mark_voice_messages_read_view, name="ai-voice-messages-read"),
]
