from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from .models import Terrarium, AllowedDevice


class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Hasło")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Powtórz hasło")

    class Meta:
        model = User
        fields = ['username', 'email']  # <--- WAŻNE: Dodano email przy rejestracji

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError("Hasła nie są identyczne.")
        return cleaned_data

class AddDeviceForm(forms.Form):
    device_id = forms.CharField(label="ID Urządzenia (np. A1001)", max_length=50)
    pin = forms.CharField(label="PIN z naklejki", widget=forms.PasswordInput)
    name = forms.CharField(label="Nazwa Terrarium", max_length=100)

    def clean(self):
        cleaned_data = super().clean()
        dev_id = cleaned_data.get("device_id")
        pin = cleaned_data.get("pin")

        if not dev_id or not pin: return cleaned_data

        try:
            allowed = AllowedDevice.objects.get(device_id=dev_id)
        except AllowedDevice.DoesNotExist:
            raise forms.ValidationError("Nieznane ID urządzenia.")

        if not check_password(pin, allowed.pin_hash):
            raise forms.ValidationError("Błędny PIN!")

        if Terrarium.objects.filter(device_id=dev_id, owner__isnull=False).exists():
            raise forms.ValidationError("To urządzenie jest już przypisane do innego konta.")

        return cleaned_data

class TerrariumSettingsForm(forms.ModelForm):
    class Meta:
        model = Terrarium
        fields = [
            'name',
            'temp_day', 'temp_night',
            'light_start', 'light_end', 'light_mode',
            'mist_enabled', 'mist_mode', 'mist_duration', 'mist_min_humidity',
            'alerts_enabled', 'alert_min_temp', 'alert_max_temp', 'alert_email'
        ]
    def clean(self):
            cleaned_data = super().clean()
            min_t = cleaned_data.get("alert_min_temp")
            max_t = cleaned_data.get("alert_max_temp")

            if min_t and max_t and min_t >= max_t:
                raise forms.ValidationError("Minimalna temperatura alarmu musi być niższa niż maksymalna!")