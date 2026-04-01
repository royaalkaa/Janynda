from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class DashboardLayoutTests(TestCase):
    def test_both_role_user_gets_observer_sidebar_on_subject_dashboard(self):
        user = User.objects.create_user(
            username="both-user",
            email="both@example.com",
            password="pass12345",
            onboarding_completed=True,
            role=User.Role.BOTH,
        )
        self.client.login(username=user.email, password="pass12345")

        response = self.client.get(reverse("subject-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Наблюдающий режим")
        self.assertContains(response, "j-sidebar")
