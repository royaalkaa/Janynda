from django.urls import path

from .views import magic_entry_view


urlpatterns = [
    path("", magic_entry_view, name="magic-entry"),
]
