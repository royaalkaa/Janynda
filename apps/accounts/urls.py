from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import UserLoginView, signup_view


urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("signup/", signup_view, name="signup"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
