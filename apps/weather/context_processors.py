from .models import WeatherCache


def current_weather(request):
    return {"current_weather": WeatherCache.objects.order_by("-fetched_at").first()}
