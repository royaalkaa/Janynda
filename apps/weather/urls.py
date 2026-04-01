from django.urls import path

from .views import weather_index_view


urlpatterns = [
    path("", weather_index_view, name="weather-index"),
]
