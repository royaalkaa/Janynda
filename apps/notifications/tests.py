from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.notifications.models import Notification


User = get_user_model()


class NotificationRedirectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="observer",
            email="observer@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.OBSERVER,
        )
        self.client.login(username=self.user.email, password="pass12345")
        self.notification = Notification.objects.create(
            recipient=self.user,
            title="Тест",
            body="Пора проверить показатели.",
        )

    def test_read_view_rejects_external_referer(self):
        response = self.client.post(
            reverse("notification-read", args=[self.notification.pk]),
            HTTP_REFERER="https://evil.example/phishing",
        )

        self.notification.refresh_from_db()

        self.assertTrue(self.notification.is_read)
        self.assertRedirects(response, reverse("notifications-list"))

    def test_read_view_preserves_internal_referer(self):
        response = self.client.post(
            reverse("notification-read", args=[self.notification.pk]),
            HTTP_REFERER="http://testserver/weather/",
        )

        self.assertRedirects(
            response,
            "http://testserver/weather/",
            fetch_redirect_response=False,
        )
