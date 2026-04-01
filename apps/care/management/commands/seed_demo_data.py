from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import MagicLink, User, UserProfile
from apps.ai_assistant.models import AIComment, VoiceCommandLog
from apps.care.models import (
    CommunityPlace,
    DailyPlanItem,
    FavoritePlace,
    LocationPing,
    SafeZone,
    TaskReminder,
    WearableDailySummary,
    WearableDevice,
)
from apps.care.services import get_or_create_location_settings
from apps.challenges.models import Challenge, ChallengeParticipant
from apps.family.models import FamilyGroup, FamilyMembership
from apps.health.models import HealthGoal, MetricRecord, MetricType
from apps.notifications.models import Notification
from apps.weather.models import WeatherCache


DEMO_PASSWORD = "demo12345"
SHOWCASE_EMAIL = "admin@admin.kz"
DEMO_EMAILS = [
    "admin@janynda.local",
    "observer@janynda.local",
    "daughter@janynda.local",
    "mother@janynda.local",
    "father@janynda.local",
]


class Command(BaseCommand):
    help = "Populate the database with a rich demo dataset for local development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo users and recreate the demo dataset from scratch.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset_demo_users()

        users = self._create_demo_users()
        showcase_user, showcase_created = self._get_or_create_showcase_user()
        self._seed_family(users)
        self._seed_places()
        self._seed_weather()
        self._seed_subject_data(users)
        self._seed_showcase_data(showcase_user)
        self.stdout.write(self.style.SUCCESS("Demo data loaded."))
        self.stdout.write("")
        self.stdout.write("Demo accounts:")
        self.stdout.write(f"  admin:    admin@janynda.local / {DEMO_PASSWORD}")
        self.stdout.write(f"  observer: observer@janynda.local / {DEMO_PASSWORD}")
        self.stdout.write(f"  daughter: daughter@janynda.local / {DEMO_PASSWORD}")
        self.stdout.write(f"  subject:  mother@janynda.local / {DEMO_PASSWORD}")
        self.stdout.write(f"  subject:  father@janynda.local / {DEMO_PASSWORD}")
        if showcase_created:
            self.stdout.write(f"  showcase: {SHOWCASE_EMAIL} / {DEMO_PASSWORD}")
        else:
            self.stdout.write(f"  showcase: {SHOWCASE_EMAIL} / текущий пароль пользователя")

    def _reset_demo_users(self):
        User.objects.filter(email__in=DEMO_EMAILS).delete()

    def _create_user(self, *, email, username, first_name, last_name, role, is_staff=False, is_superuser=False):
        user, _ = User.objects.update_or_create(
            email=email,
            defaults={
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
                "onboarding_completed": True,
            },
        )
        user.set_password(DEMO_PASSWORD)
        user.save()
        return user

    def _upsert_profile(self, user, **fields):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for field_name, value in fields.items():
            setattr(profile, field_name, value)
        profile.save()
        return profile

    def _get_or_create_showcase_user(self):
        user = User.objects.filter(email__iexact=SHOWCASE_EMAIL).first()
        created = False
        if user is None:
            user = User.objects.create_user(
                email=SHOWCASE_EMAIL,
                username="admin-kz-showcase",
                password=DEMO_PASSWORD,
                first_name="Admin",
                last_name="Admin",
                role=User.Role.BOTH,
                onboarding_completed=True,
            )
            created = True

        updated_fields = []
        if user.role != User.Role.BOTH:
            user.role = User.Role.BOTH
            updated_fields.append("role")
        if not user.onboarding_completed:
            user.onboarding_completed = True
            updated_fields.append("onboarding_completed")
        if not user.first_name:
            user.first_name = "Admin"
            updated_fields.append("first_name")
        if not user.last_name:
            user.last_name = "Admin"
            updated_fields.append("last_name")
        if not user.username:
            user.username = "admin-kz-showcase"
            updated_fields.append("username")
        if updated_fields:
            user.save(update_fields=updated_fields)

        self._upsert_profile(
            user,
            phone="+77777777777",
            date_of_birth=date(1958, 11, 3),
            gender=UserProfile.Gender.MALE,
            height_cm=Decimal("171.0"),
            weight_kg=Decimal("80.5"),
            blood_type="B+",
            chronic_conditions=[UserProfile.Condition.HYPERTENSION],
            emergency_contact="Семья Janynda",
            medical_notes="Шоукейс-профиль для демонстрации дашборда, AI и быстрого ввода метрик.",
        )
        return user, created

    def _create_demo_users(self):
        admin = self._create_user(
            email="admin@janynda.local",
            username="admin-demo",
            first_name="Demo",
            last_name="Admin",
            role=User.Role.BOTH,
            is_staff=True,
            is_superuser=True,
        )
        observer = self._create_user(
            email="observer@janynda.local",
            username="observer-demo",
            first_name="Айжан",
            last_name="Садыкова",
            role=User.Role.OBSERVER,
        )
        daughter = self._create_user(
            email="daughter@janynda.local",
            username="daughter-demo",
            first_name="Алина",
            last_name="Садыкова",
            role=User.Role.OBSERVER,
        )
        mother = self._create_user(
            email="mother@janynda.local",
            username="mother-demo",
            first_name="Гульмира",
            last_name="Садыкова",
            role=User.Role.SUBJECT,
        )
        father = self._create_user(
            email="father@janynda.local",
            username="father-demo",
            first_name="Серик",
            last_name="Садыков",
            role=User.Role.SUBJECT,
        )

        self._upsert_profile(
            observer,
            phone="+77010000001",
            emergency_contact="Алина Садыкова",
            medical_notes="Основной семейный наблюдатель.",
        )
        self._upsert_profile(
            daughter,
            phone="+77010000002",
            emergency_contact="Айжан Садыкова",
            medical_notes="Помогает вести календарь и уведомления.",
        )
        self._upsert_profile(
            mother,
            phone="+77010000003",
            date_of_birth=date(1954, 7, 18),
            gender=UserProfile.Gender.FEMALE,
            height_cm=Decimal("161.0"),
            weight_kg=Decimal("69.2"),
            blood_type="A+",
            chronic_conditions=[UserProfile.Condition.HYPERTENSION, UserProfile.Condition.HEART_DISEASE],
            emergency_contact="Айжан Садыкова",
            medical_notes="Нужно контролировать давление, воду и активность.",
        )
        self._upsert_profile(
            father,
            phone="+77010000004",
            date_of_birth=date(1951, 2, 2),
            gender=UserProfile.Gender.MALE,
            height_cm=Decimal("173.0"),
            weight_kg=Decimal("78.0"),
            blood_type="O+",
            chronic_conditions=[UserProfile.Condition.DIABETES],
            emergency_contact="Алина Садыкова",
            medical_notes="Нужно следить за шагами, сахаром и прогулками.",
        )
        self._upsert_profile(
            admin,
            phone="+77010000000",
            emergency_contact="Техподдержка",
            medical_notes="Демо-админ.",
        )

        return {
            "admin": admin,
            "observer": observer,
            "daughter": daughter,
            "mother": mother,
            "father": father,
        }

    def _seed_family(self, users):
        observer = users["observer"]
        daughter = users["daughter"]
        mother = users["mother"]
        father = users["father"]

        group = observer.owned_groups.filter(name="Семья Садыковых").first()
        if not group:
            group = FamilyGroup.objects.create(owner=observer, name="Семья Садыковых", invite_code="")

        memberships = [
            (observer, mother, "Мама", FamilyMembership.Relation.MOTHER, True),
            (observer, father, "Папа", FamilyMembership.Relation.FATHER, True),
            (daughter, mother, "Мама", FamilyMembership.Relation.MOTHER, True),
            (daughter, father, "Папа", FamilyMembership.Relation.FATHER, True),
        ]
        for observer_user, subject, label, relation, can_view_location in memberships:
            membership, _ = FamilyMembership.objects.update_or_create(
                group=group,
                observer=observer_user,
                subject_email=subject.email,
                defaults={
                    "subject": subject,
                    "subject_name": subject.get_display_name(),
                    "relation": relation,
                    "can_view_location": can_view_location,
                    "can_view_metrics": True,
                },
            )
            if not membership.magic_link or not membership.magic_link.is_valid:
                membership.magic_link = MagicLink.create_for_user(
                    subject,
                    MagicLink.Purpose.SUBJECT_ENTRY,
                    extra_data={"membership_id": membership.id},
                )
                membership.save(update_fields=["magic_link"])

        Challenge.objects.filter(group=group).delete()
        challenge = Challenge.objects.create(
            group=group,
            created_by=observer,
            title="Семейная прогулка недели",
            description="Набрать 60 000 шагов семьёй за неделю.",
            challenge_type=Challenge.ChallengeType.STEPS_TOTAL,
            target_value=Decimal("60000"),
            start_date=timezone.localdate() - timedelta(days=2),
            end_date=timezone.localdate() + timedelta(days=5),
        )
        ChallengeParticipant.objects.create(challenge=challenge, user=mother, current_value=Decimal("18200"))
        ChallengeParticipant.objects.create(challenge=challenge, user=father, current_value=Decimal("24400"))

    def _seed_places(self):
        places = [
            {
                "name": "Центр активного долголетия Алмалинского района",
                "category": CommunityPlace.Category.ACTIVE_LONGEVITY,
                "city": "Алматы",
                "address": "ул. Толе би, 135",
                "description": "ЛФК, танцы, лекции по памяти, шахматы, занятия по смартфону.",
                "phone": "+7 727 111 22 33",
                "working_hours": "Пн-Пт 09:00-18:00",
                "latitude": Decimal("43.255210"),
                "longitude": Decimal("76.913480"),
                "is_featured": True,
            },
            {
                "name": "Городская поликлиника №5",
                "category": CommunityPlace.Category.CLINIC,
                "city": "Алматы",
                "address": "ул. Жандосова, 6",
                "description": "Терапевт, кардиолог, ЭКГ, лаборатория.",
                "phone": "+7 727 222 33 44",
                "working_hours": "Пн-Пт 08:00-20:00",
                "latitude": Decimal("43.232742"),
                "longitude": Decimal("76.904210"),
                "is_featured": True,
            },
            {
                "name": "Социальная аптека у дома",
                "category": CommunityPlace.Category.PHARMACY,
                "city": "Алматы",
                "address": "пр. Абая, 101",
                "description": "Постоянные препараты, доставка и консультации по наличию.",
                "phone": "+7 727 333 44 55",
                "working_hours": "Ежедневно 08:00-22:00",
                "latitude": Decimal("43.240800"),
                "longitude": Decimal("76.905700"),
                "is_featured": True,
            },
            {
                "name": "Парк для прогулок и скандинавской ходьбы",
                "category": CommunityPlace.Category.PARK,
                "city": "Алматы",
                "address": "Парк 28 гвардейцев-панфиловцев",
                "description": "Тихие дорожки, лавочки, хороший маршрут на 20-30 минут.",
                "phone": "",
                "working_hours": "Ежедневно",
                "latitude": Decimal("43.258217"),
                "longitude": Decimal("76.954706"),
                "is_featured": True,
            },
            {
                "name": "Продуктовый Магнолия",
                "category": CommunityPlace.Category.GROCERY,
                "city": "Алматы",
                "address": "ул. Сатпаева, 30",
                "description": "Небольшой магазин рядом с домом, свежие продукты и вода.",
                "phone": "+7 727 444 55 66",
                "working_hours": "Ежедневно 08:00-23:00",
                "latitude": Decimal("43.236100"),
                "longitude": Decimal("76.927100"),
                "is_featured": False,
            },
            {
                "name": "Остановка у метро Алатау",
                "category": CommunityPlace.Category.TRANSPORT,
                "city": "Алматы",
                "address": "пр. Абая, пересечение с ул. Жарокова",
                "description": "Остановка автобуса и вход в метро.",
                "phone": "",
                "working_hours": "Круглосуточно",
                "latitude": Decimal("43.240667"),
                "longitude": Decimal("76.905248"),
                "is_featured": False,
            },
            {
                "name": "Клуб настольных игр и общения",
                "category": CommunityPlace.Category.SOCIAL_CLUB,
                "city": "Алматы",
                "address": "ул. Толе би, 58",
                "description": "Встречи, чтение, настольные игры и клуб памяти.",
                "phone": "+7 727 555 66 77",
                "working_hours": "Вт-Сб 11:00-18:00",
                "latitude": Decimal("43.254969"),
                "longitude": Decimal("76.928417"),
                "is_featured": False,
            },
            {
                "name": "Центр ЛФК и реабилитации",
                "category": CommunityPlace.Category.REHAB,
                "city": "Алматы",
                "address": "ул. Байзакова, 72",
                "description": "Реабилитационные упражнения, массаж и занятия для суставов.",
                "phone": "+7 727 666 77 88",
                "working_hours": "Пн-Сб 09:00-19:00",
                "latitude": Decimal("43.241550"),
                "longitude": Decimal("76.918420"),
                "is_featured": False,
            },
            {
                "name": "Районная социальная служба",
                "category": CommunityPlace.Category.SOCIAL_SERVICE,
                "city": "Алматы",
                "address": "ул. Ауэзова, 50",
                "description": "Помощь с документами, льготами и сопровождением.",
                "phone": "+7 727 777 88 99",
                "working_hours": "Пн-Пт 09:00-18:00",
                "latitude": Decimal("43.247800"),
                "longitude": Decimal("76.909900"),
                "is_featured": False,
            },
        ]
        for place in places:
            CommunityPlace.objects.update_or_create(
                name=place["name"],
                city=place["city"],
                defaults=place,
            )

    def _seed_weather(self):
        WeatherCache.objects.filter(city="Алматы", country="KZ").delete()
        WeatherCache.objects.create(
            city="Алматы",
            country="KZ",
            latitude=Decimal("43.238949"),
            longitude=Decimal("76.889709"),
            temperature_c=Decimal("23.40"),
            feels_like_c=Decimal("22.80"),
            humidity_pct=36,
            wind_speed_ms=Decimal("2.10"),
            pressure_hpa=1017,
            weather_main="Clear",
            weather_desc="ясно",
            weather_icon="01d",
            uv_index=Decimal("5.20"),
            visibility_m=10000,
            aqi=2,
            pm25=Decimal("11.40"),
            pm10=Decimal("17.20"),
            no2=Decimal("9.10"),
        )

    def _seed_subject_data(self, users):
        observer = users["observer"]
        daughter = users["daughter"]
        mother = users["mother"]
        father = users["father"]

        for user in [mother, father]:
            self._clear_subject_data(user)

        observer.notifications.filter(related_subject__in=[mother, father]).delete()
        daughter.notifications.filter(related_subject__in=[mother, father]).delete()

        self._seed_subject_metrics(mother, profile="mother")
        self._seed_subject_metrics(father, profile="father")
        self._seed_plan(mother, created_by=observer, doctor_address="Городская поликлиника №5")
        self._seed_plan(father, created_by=daughter, doctor_address="Центр ЛФК и реабилитации")
        self._seed_location(mother, created_by=mother)
        self._seed_location(father, created_by=father)
        self._seed_wearables(mother, imported_by=observer, provider=WearableDevice.Provider.XIAOMI, nickname="Mi Band мамы")
        self._seed_wearables(father, imported_by=daughter, provider=WearableDevice.Provider.FITBIT, nickname="Fitbit папы")
        self._seed_favorites(mother, father)
        self._seed_notifications(observer, daughter, mother, father)
        self._seed_ai_data(observer, mother, father)

    def _seed_showcase_data(self, showcase_user):
        self._clear_subject_data(showcase_user)
        self._seed_subject_metrics(showcase_user, profile="showcase")
        self._seed_plan(showcase_user, created_by=showcase_user, doctor_address="Медицинский центр на Навои, 124")
        self._seed_location(showcase_user, created_by=showcase_user)
        self._seed_wearables(
            showcase_user,
            imported_by=showcase_user,
            provider=WearableDevice.Provider.HUAWEI,
            nickname="Huawei Band admin",
        )
        self._seed_showcase_favorites(showcase_user)
        self._seed_showcase_notifications(showcase_user)
        self._seed_showcase_ai_data(showcase_user)

    def _clear_subject_data(self, user):
        user.metric_records.all().delete()
        user.daily_plan_items.all().delete()
        user.location_pings.all().delete()
        user.safe_zones.all().delete()
        user.wearable_devices.all().delete()
        user.favorite_places.all().delete()
        user.ai_comments.all().delete()
        user.voice_command_subject_logs.all().delete()
        user.notifications.all().delete()
        user.triggered_notifications.all().delete()
        user.health_goals.all().delete()

    def _seed_subject_metrics(self, subject, *, profile):
        today = timezone.localdate()

        HealthGoal.objects.update_or_create(
            subject=subject,
            metric_type=MetricType.STEPS,
            period=HealthGoal.Period.DAILY,
            defaults={"target_value": Decimal("8000"), "is_active": True},
        )
        HealthGoal.objects.update_or_create(
            subject=subject,
            metric_type=MetricType.WATER,
            period=HealthGoal.Period.DAILY,
            defaults={"target_value": Decimal("1500"), "is_active": True},
        )

        for offset in range(8):
            recorded_day = today - timedelta(days=offset)
            dt = timezone.make_aware(datetime.combine(recorded_day, time(9, 0)))
            if profile == "mother":
                steps = 4100 + (7 - offset) * 650
                systolic = 136 + offset
                diastolic = 84 + (offset % 3)
                heart_rate = 74 - (offset % 4)
                water = 1200 + (7 - offset) * 70
                sleep_hours = Decimal("6.5") + Decimal(offset % 3) / Decimal("10")
            elif profile == "showcase":
                steps = 6400 + (7 - offset) * 540
                systolic = 124 + (offset % 5)
                diastolic = 79 + (offset % 4)
                heart_rate = 68 + (offset % 4)
                water = 1450 + (7 - offset) * 55
                sleep_hours = Decimal("7.1") + Decimal(offset % 4) / Decimal("10")
            else:
                steps = 5200 + (7 - offset) * 720
                systolic = 128 + (offset % 4)
                diastolic = 78 + (offset % 2)
                heart_rate = 69 + (offset % 5)
                water = 1350 + (7 - offset) * 60
                sleep_hours = Decimal("7.0") + Decimal(offset % 4) / Decimal("10")

            MetricRecord.objects.create(
                subject=subject,
                metric_type=MetricType.STEPS,
                value_json={"steps": steps, "distance_m": steps * 0.72, "calories": round(steps * 0.04)},
                recorded_at=dt,
            )
            MetricRecord.objects.create(
                subject=subject,
                metric_type=MetricType.BLOOD_PRESSURE,
                value_json={"systolic": systolic, "diastolic": diastolic, "pulse": heart_rate},
                recorded_at=dt + timedelta(minutes=15),
            )
            MetricRecord.objects.create(
                subject=subject,
                metric_type=MetricType.HEART_RATE,
                value_json={"bpm": heart_rate},
                recorded_at=dt + timedelta(minutes=20),
            )
            MetricRecord.objects.create(
                subject=subject,
                metric_type=MetricType.WATER,
                value_json={"ml": water},
                recorded_at=dt + timedelta(hours=8),
            )
            MetricRecord.objects.create(
                subject=subject,
                metric_type=MetricType.SLEEP,
                value_json={"hours": float(sleep_hours), "quality": 4},
                recorded_at=dt - timedelta(hours=6),
            )

    def _seed_plan(self, subject, *, created_by, doctor_address):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        medicine_by_email = {
            "mother@janynda.local": "Бисопролол",
            "father@janynda.local": "Метформин",
            SHOWCASE_EMAIL: "Лозартан",
        }
        doctor_by_email = {
            "mother@janynda.local": "Кардиолог",
            "father@janynda.local": "Эндокринолог",
            SHOWCASE_EMAIL: "Терапевт",
        }

        medication = DailyPlanItem.objects.create(
            subject=subject,
            created_by=created_by,
            title="Утреннее лекарство",
            description="После завтрака и воды.",
            scheduled_date=today,
            scheduled_time=time(8, 30),
            duration_minutes=10,
            category=DailyPlanItem.Category.MEDICATION,
            priority=DailyPlanItem.Priority.HIGH,
            recurrence_type=DailyPlanItem.RecurrenceType.DAILY,
            medicine_name=medicine_by_email.get(subject.email, "Лекарство"),
            medicine_dosage="1 таблетка",
        )
        TaskReminder.objects.create(task=medication, remind_before_minutes=30)

        water = DailyPlanItem.objects.create(
            subject=subject,
            created_by=created_by,
            title="Стакан воды",
            description="Первый стакан воды за день.",
            scheduled_date=today,
            scheduled_time=time(9, 15),
            category=DailyPlanItem.Category.WATER,
            recurrence_type=DailyPlanItem.RecurrenceType.DAILY,
            water_amount_ml=250,
        )
        TaskReminder.objects.create(task=water, remind_before_minutes=10)

        DailyPlanItem.objects.create(
            subject=subject,
            created_by=created_by,
            title="Прогулка во дворе",
            description="20-30 минут спокойным темпом.",
            scheduled_date=today,
            scheduled_time=time(17, 30),
            duration_minutes=30,
            category=DailyPlanItem.Category.WALK,
            priority=DailyPlanItem.Priority.NORMAL,
        )
        DailyPlanItem.objects.create(
            subject=subject,
            created_by=created_by,
            title="Позвонить детям",
            description="Созвониться вечером и рассказать о самочувствии.",
            scheduled_date=today,
            scheduled_time=time(19, 0),
            category=DailyPlanItem.Category.SOCIAL,
        )
        DailyPlanItem.objects.create(
            subject=subject,
            created_by=created_by,
            title="Приём врача",
            description="Плановый осмотр и коррекция терапии.",
            scheduled_date=tomorrow,
            scheduled_time=time(11, 0),
            category=DailyPlanItem.Category.DOCTOR_VISIT,
            priority=DailyPlanItem.Priority.HIGH,
            doctor_specialty=doctor_by_email.get(subject.email, "Терапевт"),
            doctor_address=doctor_address,
        )
        DailyPlanItem.objects.create(
            subject=subject,
            created_by=created_by,
            title="Купить продукты",
            description="Хлеб, молоко, фрукты и вода.",
            scheduled_date=tomorrow,
            scheduled_time=time(15, 0),
            category=DailyPlanItem.Category.SHOPPING,
        )

        for offset in range(1, 4):
            completed_day = today - timedelta(days=offset)
            DailyPlanItem.objects.create(
                subject=subject,
                created_by=created_by,
                completed_by=created_by,
                title=f"Контроль давления {completed_day:%d.%m}",
                description="Запись давления в дневник.",
                scheduled_date=completed_day,
                scheduled_time=time(8, 45),
                category=DailyPlanItem.Category.HEALTH_CHECK,
                is_completed=True,
                completed_at=timezone.make_aware(datetime.combine(completed_day, time(8, 50))),
            )

    def _seed_location(self, subject, *, created_by):
        settings_obj = get_or_create_location_settings(subject)
        settings_obj.tracking_enabled = True
        settings_obj.share_with_family = True
        settings_obj.allow_manual_updates = True
        settings_obj.city = "Алматы"
        settings_obj.home_address = "пр. Абая, 101"
        settings_obj.home_latitude = Decimal("43.240800")
        settings_obj.home_longitude = Decimal("76.905700")
        settings_obj.emergency_contact_notes = "Если долго нет дома, сначала звонить дочери."
        settings_obj.max_absence_hours = 4
        settings_obj.tracking_consent_given_at = timezone.now() - timedelta(days=5)
        settings_obj.save()

        home_zone = SafeZone.objects.create(
            subject=subject,
            name="Дом",
            latitude=Decimal("43.240800"),
            longitude=Decimal("76.905700"),
            radius_meters=180,
            is_home=True,
        )
        SafeZone.objects.create(
            subject=subject,
            name="Поликлиника",
            latitude=Decimal("43.232742"),
            longitude=Decimal("76.904210"),
            radius_meters=220,
            is_home=False,
        )
        SafeZone.objects.create(
            subject=subject,
            name="Парк",
            latitude=Decimal("43.258217"),
            longitude=Decimal("76.954706"),
            radius_meters=350,
            is_home=False,
        )

        ping_points = [
            (Decimal("43.240800"), Decimal("76.905700"), "Дома", timezone.now() - timedelta(hours=6)),
            (Decimal("43.236100"), Decimal("76.927100"), "Продуктовый магазин", timezone.now() - timedelta(hours=4, minutes=30)),
            (Decimal("43.232742"), Decimal("76.904210"), "Поликлиника", timezone.now() - timedelta(hours=3)),
            (Decimal("43.240800"), Decimal("76.905700"), "Вернулась домой", timezone.now() - timedelta(hours=1)),
        ]
        for lat, lng, note, captured_at in ping_points:
            LocationPing.objects.create(
                subject=subject,
                created_by=created_by,
                latitude=lat,
                longitude=lng,
                source=LocationPing.Source.MANUAL,
                note=note,
                captured_at=captured_at,
            )
        settings_obj.register_share()

    def _seed_wearables(self, subject, *, imported_by, provider, nickname):
        device = WearableDevice.objects.create(
            subject=subject,
            provider=provider,
            nickname=nickname,
            external_id=f"{subject.username}-wearable",
            is_active=True,
        )

        today = timezone.localdate()
        for offset in range(7):
            summary_date = today - timedelta(days=offset)
            if subject.email == "mother@janynda.local":
                steps = 4300 + (6 - offset) * 630
                avg_hr = 72 - (offset % 4)
                hr_min = 58 - (offset % 2)
                hr_max = 102 + offset
                sleep = Decimal("6.8") + Decimal(offset % 3) / Decimal("10")
                active_minutes = 34 + offset * 3
            elif subject.email == SHOWCASE_EMAIL:
                steps = 7100 + (6 - offset) * 580
                avg_hr = 67 + (offset % 4)
                hr_min = 52
                hr_max = 99 + offset
                sleep = Decimal("7.2") + Decimal(offset % 3) / Decimal("10")
                active_minutes = 48 + offset * 3
            else:
                steps = 5600 + (6 - offset) * 700
                avg_hr = 69 + (offset % 3)
                hr_min = 54
                hr_max = 96 + offset
                sleep = Decimal("7.1") + Decimal(offset % 4) / Decimal("10")
                active_minutes = 42 + offset * 4

            WearableDailySummary.objects.create(
                device=device,
                imported_by=imported_by,
                summary_date=summary_date,
                steps=steps,
                average_heart_rate=avg_hr,
                heart_rate_min=hr_min,
                heart_rate_max=hr_max,
                sleep_hours=sleep,
                sleep_quality=WearableDailySummary.SleepQuality.GOOD if offset % 3 else WearableDailySummary.SleepQuality.FAIR,
                deep_sleep_hours=Decimal("2.1"),
                light_sleep_hours=max(Decimal("4.5"), sleep - Decimal("2.1")),
                active_minutes=active_minutes,
                distance_km=Decimal(steps) / Decimal("1500"),
                calories_kcal=240 + offset * 18,
            )
        device.register_sync()

    def _seed_favorites(self, mother, father):
        favorite_names = {
            mother.email: [
                "Центр активного долголетия Алмалинского района",
                "Городская поликлиника №5",
                "Социальная аптека у дома",
            ],
            father.email: [
                "Парк для прогулок и скандинавской ходьбы",
                "Центр ЛФК и реабилитации",
                "Продуктовый Магнолия",
            ],
        }
        for subject in [mother, father]:
            for name in favorite_names[subject.email]:
                place = CommunityPlace.objects.get(name=name)
                FavoritePlace.objects.get_or_create(subject=subject, place=place)

    def _seed_notifications(self, observer, daughter, mother, father):
        notifications = [
            (observer, mother, "Утреннее лекарство ещё не отмечено", "Пора проверить, выпила ли мама лекарство.", Notification.Severity.WARNING, Notification.Category.ENTRY_REMINDER),
            (observer, mother, "Сегодня хороший день для прогулки", "Погода спокойная, можно выйти на 20-30 минут.", Notification.Severity.INFO, Notification.Category.WEATHER),
            (daughter, father, "Пульс выше обычного", "У папы был зафиксирован повышенный пульс на браслете.", Notification.Severity.WARNING, Notification.Category.HEALTH_ALERT),
            (mother, mother, "Напоминание о воде", "Выпейте ещё один стакан воды до обеда.", Notification.Severity.INFO, Notification.Category.ENTRY_REMINDER),
            (father, father, "Цель по шагам почти достигнута", "До дневной цели осталось около 1200 шагов.", Notification.Severity.INFO, Notification.Category.CHALLENGE),
        ]
        for recipient, subject, title, body, severity, category in notifications:
            Notification.objects.create(
                recipient=recipient,
                related_subject=subject,
                title=title,
                body=body,
                severity=severity,
                category=category,
            )

    def _seed_ai_data(self, observer, mother, father):
        expires_at = timezone.now() + timedelta(hours=12)
        AIComment.objects.create(
            subject=mother,
            content="Давление у мамы слегка выше нормы, но активность и прогулки держатся стабильно. Сегодня стоит проследить за водой и вечерним пульсом.",
            is_fallback=True,
            expires_at=expires_at,
        )
        AIComment.objects.create(
            subject=father,
            content="У папы хороший темп по шагам за неделю. Полезно сохранить режим прогулок и контроль сахара перед ужином.",
            is_fallback=True,
            expires_at=expires_at,
        )
        VoiceCommandLog.objects.create(
            user=mother,
            subject=mother,
            transcript="Я выпила лекарство бисопролол",
            response_text="Отметила, что лекарство бисопролол принято.",
            action_type=VoiceCommandLog.ActionType.MEDICATION_LOG,
            payload={"medicine_name": "Бисопролол"},
            confirmed=True,
        )
        VoiceCommandLog.objects.create(
            user=observer,
            subject=mother,
            transcript="Напоминание",
            response_text="Через 30 мин: Утреннее лекарство. Время: 08:30.",
            action_type=VoiceCommandLog.ActionType.REMINDER,
            payload={"demo": True},
            confirmed=True,
            is_system_message=True,
            is_read=False,
        )
        VoiceCommandLog.objects.create(
            user=father,
            subject=father,
            transcript="Что у меня сегодня по плану?",
            response_text="На сегодня 4 задачи. Уже выполнено 1. Осталось: прогулка, вода, звонок детям.",
            action_type=VoiceCommandLog.ActionType.PLAN_QUERY,
            payload={"count": 4},
            confirmed=True,
        )

    def _seed_showcase_favorites(self, showcase_user):
        for name in [
            "Центр активного долголетия Алмалинского района",
            "Парк для прогулок и скандинавской ходьбы",
            "Социальная аптека у дома",
            "Продуктовый Магнолия",
        ]:
            FavoritePlace.objects.get_or_create(subject=showcase_user, place=CommunityPlace.objects.get(name=name))

    def _seed_showcase_notifications(self, showcase_user):
        notifications = [
            ("Пора принять утреннее лекарство", "Лозартан запланирован на 08:30.", Notification.Severity.INFO, Notification.Category.ENTRY_REMINDER),
            ("Давление стабильно", "Последние три замера укладываются в комфортный диапазон.", Notification.Severity.INFO, Notification.Category.HEALTH_ALERT),
            ("До цели по шагам осталось немного", "Сегодня осталось около 1800 шагов до дневной цели.", Notification.Severity.INFO, Notification.Category.CHALLENGE),
        ]
        for title, body, severity, category in notifications:
            Notification.objects.create(
                recipient=showcase_user,
                related_subject=showcase_user,
                title=title,
                body=body,
                severity=severity,
                category=category,
            )

    def _seed_showcase_ai_data(self, showcase_user):
        expires_at = timezone.now() + timedelta(hours=12)
        AIComment.objects.create(
            subject=showcase_user,
            content="Давление у вас сейчас выглядит спокойно, активность по шагам ровная, а вода и сон держатся близко к цели. Хороший профиль для демонстрации голосового помощника.",
            is_fallback=True,
            expires_at=expires_at,
        )
        VoiceCommandLog.objects.create(
            user=showcase_user,
            subject=showcase_user,
            transcript="Давление 126 на 82 это нормально?",
            response_text="Давление 126/82 пока выглядит в пределах целевого диапазона для профиля в приложении. Продолжайте обычный контроль и отмечайте самочувствие.",
            action_type=VoiceCommandLog.ActionType.ANSWER,
            payload={"source": "local-thresholds", "metric_type": MetricType.BLOOD_PRESSURE},
            confirmed=True,
        )
        VoiceCommandLog.objects.create(
            user=showcase_user,
            subject=showcase_user,
            transcript="Как улучшить сон?",
            response_text="Для режима в приложении ориентир по сну — около 8 часов. Полезно ложиться примерно в одно и то же время и избегать тяжёлой еды поздно вечером.",
            action_type=VoiceCommandLog.ActionType.ANSWER,
            payload={"source": "local-fallback"},
            confirmed=True,
        )
        VoiceCommandLog.objects.create(
            user=showcase_user,
            subject=showcase_user,
            transcript="Напоминание",
            response_text="Через 30 мин: Утреннее лекарство. Время: 08:30.",
            action_type=VoiceCommandLog.ActionType.REMINDER,
            payload={"demo": True},
            confirmed=True,
            is_system_message=True,
            is_read=False,
        )
