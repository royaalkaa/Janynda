from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.models import NotificationSettings

from .models import User, UserProfile


@receiver(post_save, sender=User)
def create_related_user_models(sender, instance, created, **kwargs):
    if not created:
        return

    UserProfile.objects.get_or_create(user=instance)
    NotificationSettings.objects.get_or_create(user=instance)
