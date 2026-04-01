from django.urls import path

from .views import dashboard_home_view, observer_dashboard_view, subject_dashboard_view


urlpatterns = [
    path("", dashboard_home_view, name="dashboard-home"),
    path("observer/", observer_dashboard_view, name="observer-dashboard"),
    path("subject/", subject_dashboard_view, name="subject-dashboard"),
]
