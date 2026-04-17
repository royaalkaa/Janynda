from django.urls import path

from .views import (
    notification_list_view,
    notification_read_all_view,
    notification_read_view,
    sos_trigger_view,
)


urlpatterns = [
    path("", notification_list_view, name="notifications-list"),
    path("<int:pk>/read/", notification_read_view, name="notification-read"),
    path("read-all/", notification_read_all_view, name="notification-read-all"),
    path("sos/", sos_trigger_view, name="sos-trigger"),
]
