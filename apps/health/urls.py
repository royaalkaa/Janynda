from django.urls import path

from .views import metric_history_view, quick_entry_view


urlpatterns = [
    path("quick-entry/<slug:metric_type>/", quick_entry_view, name="health-quick-entry"),
    path("history/", metric_history_view, name="health-history"),
    path("history/<int:subject_id>/", metric_history_view, name="health-history-subject"),
]
