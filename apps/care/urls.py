from django.urls import path

from . import views


urlpatterns = [
    path("plan/", views.daily_plan_view, name="care-plan"),
    path("plan/<int:subject_id>/", views.daily_plan_view, name="care-plan-subject"),
    path("plan/item/<int:pk>/toggle/", views.daily_plan_toggle_view, name="care-plan-toggle"),
    path("tasks/history/", views.task_history, name="task_history"),
    path("tasks/<int:task_id>/edit/", views.edit_task, name="task_edit"),
    path("tasks/<int:task_id>/delete/", views.delete_task, name="task_delete"),
    path("places/", views.places_view, name="care-places"),
    path("places/<int:place_id>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("location/", views.location_view, name="care-location"),
    path("location/<int:subject_id>/", views.location_view, name="care-location-subject"),
    path("location/safe-zones/", views.safe_zones, name="safe_zones"),
    path("location/sos/", views.emergency_sos, name="emergency_sos"),
    path("wearables/", views.wearables_view, name="care-wearables"),
    path("wearables/<int:subject_id>/", views.wearables_view, name="care-wearables-subject"),
    path("wearables/stats/", views.wearables_stats, name="wearables_stats"),
]
