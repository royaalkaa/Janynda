from django import forms

from .models import FamilyMembership


class FamilyMemberForm(forms.Form):
    group_name = forms.CharField(
        label="Название семьи",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Семья Аманкул"}),
    )
    subject_name = forms.CharField(
        label="Имя родственника",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Мама"}),
    )
    subject_email = forms.EmailField(
        label="Email родственника",
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "необязательно"}),
    )
    relation = forms.ChoiceField(
        label="Кем вам приходится",
        choices=FamilyMembership.Relation.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    can_view_location = forms.BooleanField(
        label="Разрешить просмотр геоданных и прогулок",
        required=False,
    )
