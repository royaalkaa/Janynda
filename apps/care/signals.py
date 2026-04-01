from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LocationPing
from .services import get_or_create_location_settings, handle_zone_crossing_for_ping


@receiver(post_save, sender=LocationPing)
def location_ping_created(sender, instance, created, **kwargs):
    if not created:
        return
    settings_obj = get_or_create_location_settings(instance.subject)
    settings_obj.register_share()
    handle_zone_crossing_for_ping(instance)
