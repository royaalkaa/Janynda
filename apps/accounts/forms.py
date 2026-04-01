from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import IntegrityError
from django.utils.text import slugify

from apps.family.models import FamilyMembership
from apps.health.models import MetricType

from .models import User


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Введите пароль"}),
    )


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(
        label="Имя",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Айгерим"}),
    )
    last_name = forms.CharField(
        label="Фамилия",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Сериккызы"}),
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+7 777 000 00 00"}),
    )
    role = forms.ChoiceField(
        label="Как вы будете использовать Janynda",
        choices=User.Role.choices,
        widget=forms.RadioSelect,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name", "phone", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Минимум 8 символов"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Повторите пароль"}
        )

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].lower().strip()
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.phone = self.cleaned_data["phone"]
        user.role = self.cleaned_data["role"]
        base = slugify(user.get_full_name()) or user.email.split("@")[0]
        user.username = base

        suffix = 1
        while User.objects.filter(username=user.username).exists():
            suffix += 1
            user.username = f"{base}-{suffix}"

        if commit:
            try:
                user.save()
            except IntegrityError:
                self.add_error("email", "Пользователь с таким email уже существует.")
                raise forms.ValidationError("Пользователь с таким email уже существует.")
        return user


class OnboardingRoleForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["role"]
        widgets = {"role": forms.RadioSelect}
        labels = {"role": "Что вам нужно в первую очередь"}


class OnboardingProfileForm(forms.Form):
    first_name = forms.CharField(
        label="Имя",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Айгерим"}),
    )
    last_name = forms.CharField(
        label="Фамилия",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Сериккызы"}),
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+7 777 000 00 00"}),
    )
    date_of_birth = forms.DateField(
        label="Дата рождения",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    height_cm = forms.DecimalField(
        label="Рост, см",
        required=False,
        max_digits=5,
        decimal_places=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "167"}),
    )
    weight_kg = forms.DecimalField(
        label="Вес, кг",
        required=False,
        max_digits=5,
        decimal_places=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "62"}),
    )


class OnboardingFamilyForm(forms.Form):
    group_name = forms.CharField(
        label="Название семьи",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Семья Аманкул"}),
    )
    relative_name = forms.CharField(
        label="Кого добавить первым",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Мама"}),
    )
    relation = forms.ChoiceField(
        label="Кем вам приходится",
        required=False,
        choices=[("", "Выберите связь")] + list(FamilyMembership.Relation.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    relative_email = forms.EmailField(
        label="Email родственника",
        required=False,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "необязательно для magic link"}
        ),
    )

    def __init__(self, *args, **kwargs):
        self.role = kwargs.pop("role", User.Role.BOTH)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        needs_family = self.role in (User.Role.OBSERVER, User.Role.BOTH)
        if needs_family and not cleaned_data.get("relative_name"):
            self.add_error("relative_name", "Добавьте хотя бы одного родственника для старта.")
        if cleaned_data.get("relative_name") and not cleaned_data.get("relation"):
            self.add_error("relation", "Укажите связь с родственником.")
        return cleaned_data


class OnboardingPreferencesForm(forms.Form):
    reminder_time = forms.TimeField(
        label="Когда напоминать о вводе показателей",
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
    )
    health_alerts = forms.BooleanField(
        label="Присылать алерты по опасным показателям",
        required=False,
        initial=True,
    )
    weather_alerts = forms.BooleanField(
        label="Присылать предупреждения по погоде и воздуху",
        required=False,
        initial=True,
    )
    daily_steps_goal = forms.IntegerField(
        label="Ежедневная цель по шагам",
        required=False,
        min_value=1000,
        max_value=50000,
        initial=8000,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "8000"}),
    )
    primary_metric = forms.ChoiceField(
        label="На чём сфокусироваться сначала",
        choices=[
            (MetricType.BLOOD_PRESSURE, "Давление"),
            (MetricType.HEART_RATE, "Пульс"),
            (MetricType.STEPS, "Шаги"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
