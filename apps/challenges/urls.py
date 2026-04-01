from django.urls import path

from .views import challenge_list_view


urlpatterns = [
    path("", challenge_list_view, name="challenge-list"),
]
