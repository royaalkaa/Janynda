from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.services import attach_subject_to_observer
from apps.notifications.models import NotificationSettings


User = get_user_model()


class UserLifecycleTests(TestCase):
    def test_user_creation_creates_profile_and_notification_settings(self):
        user = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pass12345",
        )

        self.assertTrue(hasattr(user, "profile"))
        self.assertTrue(hasattr(user, "notification_settings"))
        self.assertIsInstance(user.notification_settings, NotificationSettings)

    def test_signup_with_duplicate_email_shows_form_error(self):
        User.objects.create_user(
            username="existing-user",
            email="admin@admin.kz",
            password="pass12345",
        )

        response = self.client.post(
            reverse("signup"),
            {
                "email": "admin@admin.kz",
                "first_name": "Admin",
                "last_name": "Admin",
                "phone": "+7 777 777 77 77",
                "role": User.Role.BOTH,
                "password1": "123456qwertyD",
                "password2": "123456qwertyD",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Пользователь с таким email уже существует.")


class AttachSubjectServiceTests(TestCase):
    def test_attach_subject_creates_membership_and_magic_link(self):
        observer = User.objects.create_user(
            username="observer",
            email="observer@example.com",
            password="pass12345",
            role=User.Role.OBSERVER,
            onboarding_completed=True,
        )

        membership = attach_subject_to_observer(
            observer,
            group_name="Семья Тест",
            relative_name="Мама Тест",
            relation="mother",
            relative_email="mama@example.com",
            can_view_location=True,
        )

        self.assertEqual(membership.group.name, "Семья Тест")
        self.assertEqual(membership.subject.email, "mama@example.com")
        self.assertEqual(membership.magic_link.user, membership.subject)
        self.assertTrue(membership.magic_link.is_valid)
        self.assertTrue(membership.can_view_location)
