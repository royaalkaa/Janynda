from django.urls import path

from .views import family_overview_view


urlpatterns = [
    path("", family_overview_view, name="family-overview"),
]
