from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import WeatherCache


@login_required
def weather_index_view(request):
    latest_weather = WeatherCache.objects.order_by("-fetched_at").first()
    return render(request, "weather/index.html", {"weather": latest_weather})
