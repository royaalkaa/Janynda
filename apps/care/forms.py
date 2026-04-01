from django import forms

from .models import (
    DailyPlanItem,
    LocationPing,
    LocationSharingSettings,
    SafeZone,
    TaskReminder,
    WearableDailySummary,
    WearableDevice,
)


class DailyPlanItemForm(forms.ModelForm):
    WEEKDAY_CHOICES = [
        (0, "Понедельник"),
        (1, "Вторник"),
        (2, "Среда"),
        (3, "Четверг"),
        (4, "Пятница"),
        (5, "Суббота"),
        (6, "Воскресенье"),
    ]

    title = forms.CharField(
        label="Задача",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Принять таблетки после завтрака"}
        ),
    )
    description = forms.CharField(
        label="Подробности",
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Детали или напоминание"}
        ),
    )
    scheduled_date = forms.DateField(
        label="Дата",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    scheduled_time = forms.TimeField(
        label="Время",
        required=False,
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
    )
    duration_minutes = forms.IntegerField(
        label="Длительность, мин",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "30"}),
    )
    category = forms.ChoiceField(
        label="Категория",
        choices=DailyPlanItem.Category.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    priority = forms.ChoiceField(
        label="Приоритет",
        choices=DailyPlanItem.Priority.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    recurrence_type = forms.ChoiceField(
        label="Повторяемость",
        choices=DailyPlanItem.RecurrenceType.choices,
        required=False,
        initial=DailyPlanItem.RecurrenceType.ONCE,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    recurrence_days = forms.MultipleChoiceField(
        label="Дни недели",
        choices=WEEKDAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    recurrence_end_date = forms.DateField(
        label="Повторять до",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    remind_before_minutes = forms.IntegerField(
        label="Напомнить за, мин",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "30"}),
    )
    medicine_name = forms.CharField(
        label="Название лекарства",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Кардиомагнил"}),
    )
    medicine_dosage = forms.CharField(
        label="Дозировка",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "1 таблетка"}),
    )
    doctor_specialty = forms.CharField(
        label="Специалист",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Кардиолог"}),
    )
    doctor_address = forms.CharField(
        label="Адрес врача",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Поликлиника №5"}),
    )
    water_amount_ml = forms.IntegerField(
        label="Количество воды, мл",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "250"}),
    )

    class Meta:
        model = DailyPlanItem
        fields = [
            "title",
            "description",
            "scheduled_date",
            "scheduled_time",
            "duration_minutes",
            "category",
            "priority",
            "recurrence_type",
            "recurrence_days",
            "recurrence_end_date",
            "medicine_name",
            "medicine_dosage",
            "doctor_specialty",
            "doctor_address",
            "water_amount_ml",
        ]
        widgets = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["recurrence_days"].initial = self.instance.recurrence_days
            reminder = self.instance.reminders.order_by("remind_before_minutes").first()
            if reminder:
                self.fields["remind_before_minutes"].initial = reminder.remind_before_minutes

    def clean_recurrence_days(self):
        values = self.cleaned_data.get("recurrence_days") or []
        return [int(value) for value in values]

    def clean(self):
        cleaned_data = super().clean()
        recurrence_type = cleaned_data.get("recurrence_type")
        recurrence_days = cleaned_data.get("recurrence_days") or []
        scheduled_date = cleaned_data.get("scheduled_date")
        recurrence_end_date = cleaned_data.get("recurrence_end_date")

        if recurrence_type == DailyPlanItem.RecurrenceType.WEEKLY and not recurrence_days and scheduled_date:
            cleaned_data["recurrence_days"] = [scheduled_date.weekday()]

        if recurrence_end_date and scheduled_date and recurrence_end_date < scheduled_date:
            self.add_error("recurrence_end_date", "Дата окончания не может быть раньше даты задачи.")

        return cleaned_data

    def save(self, commit=True):
        reminder_minutes = self.cleaned_data.get("remind_before_minutes")
        instance = super().save(commit=commit)
        if commit:
            self._sync_reminders(instance, reminder_minutes)
        return instance

    def sync_reminders(self, instance=None):
        instance = instance or self.instance
        self._sync_reminders(instance, self.cleaned_data.get("remind_before_minutes"))

    def _sync_reminders(self, instance, reminder_minutes):
        instance.reminders.all().delete()
        if reminder_minutes:
            TaskReminder.objects.create(
                task=instance,
                remind_before_minutes=reminder_minutes,
            )


class LocationSharingSettingsForm(forms.ModelForm):
    tracking_enabled = forms.BooleanField(
        label="Активное отслеживание включено",
        required=False,
    )
    share_with_family = forms.BooleanField(
        label="Показывать геолокацию семье",
        required=False,
    )
    allow_manual_updates = forms.BooleanField(
        label="Разрешить ручные обновления точки",
        required=False,
    )
    city = forms.CharField(
        label="Город",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Алматы"}),
    )
    home_address = forms.CharField(
        label="Домашний адрес",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Улица, дом, подъезд"}
        ),
    )
    home_latitude = forms.DecimalField(
        label="Широта дома",
        required=False,
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.000001", "placeholder": "43.238949"}
        ),
    )
    home_longitude = forms.DecimalField(
        label="Долгота дома",
        required=False,
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.000001", "placeholder": "76.889709"}
        ),
    )
    emergency_contact_notes = forms.CharField(
        label="Комментарий для семьи",
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Что важно знать семье"}
        ),
    )
    max_absence_hours = forms.IntegerField(
        label="Тревога при отсутствии дольше, ч",
        min_value=1,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "4"}),
    )

    class Meta:
        model = LocationSharingSettings
        fields = [
            "tracking_enabled",
            "share_with_family",
            "allow_manual_updates",
            "city",
            "home_address",
            "home_latitude",
            "home_longitude",
            "emergency_contact_notes",
            "max_absence_hours",
        ]
        widgets = {}


class LocationPingForm(forms.ModelForm):
    latitude = forms.DecimalField(
        label="Широта",
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.000001", "placeholder": "43.238949"}
        ),
    )
    longitude = forms.DecimalField(
        label="Долгота",
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.000001", "placeholder": "76.889709"}
        ),
    )
    source = forms.ChoiceField(
        label="Источник",
        choices=LocationPing.Source.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    note = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Дом, поликлиника, прогулка"}
        ),
    )

    class Meta:
        model = LocationPing
        fields = ["latitude", "longitude", "source", "note"]
        widgets = {}


class SafeZoneForm(forms.ModelForm):
    name = forms.CharField(
        label="Название зоны",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Дом"}),
    )
    latitude = forms.DecimalField(
        label="Широта",
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.000001", "placeholder": "43.238949"}
        ),
    )
    longitude = forms.DecimalField(
        label="Долгота",
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.000001", "placeholder": "76.889709"}
        ),
    )
    radius_meters = forms.IntegerField(
        label="Радиус, м",
        min_value=50,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "300"}),
    )
    is_home = forms.BooleanField(
        label="Это домашняя зона",
        required=False,
    )

    class Meta:
        model = SafeZone
        fields = ["name", "latitude", "longitude", "radius_meters", "is_home"]
        widgets = {}


class WearableDeviceForm(forms.ModelForm):
    provider = forms.ChoiceField(
        label="Провайдер",
        choices=WearableDevice.Provider.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    nickname = forms.CharField(
        label="Название устройства",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Mi Band мамы"}),
    )
    external_id = forms.CharField(
        label="Внешний ID / связка",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "ID или имя подключения"}
        ),
    )
    is_active = forms.BooleanField(
        label="Используется сейчас",
        required=False,
    )

    class Meta:
        model = WearableDevice
        fields = ["provider", "nickname", "external_id", "is_active"]
        widgets = {}


class WearableDailySummaryForm(forms.ModelForm):
    summary_date = forms.DateField(
        label="Дата сводки",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    steps = forms.IntegerField(
        label="Шаги",
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "6500"}),
    )
    average_heart_rate = forms.IntegerField(
        label="Средний пульс",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "72"}),
    )
    heart_rate_min = forms.IntegerField(
        label="Минимальный пульс",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "58"}),
    )
    heart_rate_max = forms.IntegerField(
        label="Максимальный пульс",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "118"}),
    )
    sleep_hours = forms.DecimalField(
        label="Сон, ч",
        required=False,
        max_digits=4,
        decimal_places=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "7.5"}),
    )
    sleep_quality = forms.ChoiceField(
        label="Качество сна",
        required=False,
        choices=[("", "Не указано"), *WearableDailySummary.SleepQuality.choices],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    deep_sleep_hours = forms.DecimalField(
        label="Глубокий сон, ч",
        required=False,
        max_digits=4,
        decimal_places=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "2.1"}),
    )
    light_sleep_hours = forms.DecimalField(
        label="Лёгкий сон, ч",
        required=False,
        max_digits=4,
        decimal_places=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "5.4"}),
    )
    active_minutes = forms.IntegerField(
        label="Активные минуты",
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "55"}),
    )
    distance_km = forms.DecimalField(
        label="Дистанция, км",
        required=False,
        max_digits=6,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "4.3"}),
    )
    calories_kcal = forms.IntegerField(
        label="Калории, ккал",
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "320"}),
    )

    class Meta:
        model = WearableDailySummary
        fields = [
            "device",
            "summary_date",
            "steps",
            "average_heart_rate",
            "heart_rate_min",
            "heart_rate_max",
            "sleep_hours",
            "sleep_quality",
            "deep_sleep_hours",
            "light_sleep_hours",
            "active_minutes",
            "distance_km",
            "calories_kcal",
        ]
        widgets = {
            "device": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        subject = kwargs.pop("subject", None)
        super().__init__(*args, **kwargs)
        self.fields["device"].label = "Устройство"
        if subject is not None:
            self.fields["device"].queryset = subject.wearable_devices.order_by("-is_active", "nickname")

    def clean(self):
        cleaned_data = super().clean()
        heart_rate_min = cleaned_data.get("heart_rate_min")
        heart_rate_max = cleaned_data.get("heart_rate_max")
        if heart_rate_min and heart_rate_max and heart_rate_min > heart_rate_max:
            self.add_error("heart_rate_min", "Минимальный пульс не может быть выше максимального.")
        return cleaned_data
