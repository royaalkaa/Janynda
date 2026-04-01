from django import forms


class BloodPressureEntryForm(forms.Form):
    systolic = forms.IntegerField(min_value=60, max_value=250)
    diastolic = forms.IntegerField(min_value=30, max_value=180)
    pulse = forms.IntegerField(min_value=30, max_value=220, required=False)


class HeartRateEntryForm(forms.Form):
    bpm = forms.IntegerField(min_value=30, max_value=220)


class StepsEntryForm(forms.Form):
    steps = forms.IntegerField(min_value=0, max_value=100000)


METRIC_FORM_MAP = {
    "blood_pressure": BloodPressureEntryForm,
    "heart_rate": HeartRateEntryForm,
    "steps": StepsEntryForm,
}
