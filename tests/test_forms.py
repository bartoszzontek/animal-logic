import pytest
from apps.core.forms import RegisterForm, AddDeviceForm, TerrariumSettingsForm
from apps.core.models import AllowedDevice
from django.contrib.auth.hashers import make_password


@pytest.mark.django_db
def test_register_form_password_mismatch():
    """Formularz powinien być invalid, gdy hasła są różne."""
    data = {
        'username': 'testuser',
        'email': 't@t.com',
        'password': 'pass1',
        'confirm_password': 'pass2'  # Różne hasła
    }
    form = RegisterForm(data=data)

    assert form.is_valid() is False
    # POPRAWKA: Sprawdzamy błędy ogólne (__all__), a nie konkretne pole
    assert '__all__' in form.errors
    # Opcjonalnie: sprawdzamy treść komunikatu
    assert 'Hasła nie są identyczne' in str(form.errors['__all__'])
@pytest.mark.django_db
def test_add_device_form_invalid_pin():
    """Formularz powinien odrzucić zły PIN."""
    # Tworzymy poprawne urządzenie w bazie
    AllowedDevice.objects.create(
        device_id='A100',
        pin_hash=make_password('1234')
    )

    # Próbujemy dodać ze złym pinem
    data = {'device_id': 'A100', 'name': 'Moje', 'pin': '0000'}
    form = AddDeviceForm(data=data)

    assert form.is_valid() is False
    assert form.non_field_errors()  # Błąd ogólny formularza (nie pola)


@pytest.mark.django_db
def test_settings_form_logic_error(user):
    """
    Testujemy logikę: Alarm Min Temp nie może być wyższy niż Max Temp.
    To jest test 'RED', bo prawdopodobnie nie masz tej walidacji w forms.py!
    """
    data = {
        'name': 'Test',
        'temp_day': 25, 'temp_night': 20,
        'light_start': '08:00', 'light_end': '20:00',
        'light_mode': 'auto', 'mist_mode': 'auto',
        'mist_min_humidity': 50, 'mist_duration': 10,
        'alerts_enabled': True,
        # BŁĄD LOGICZNY: Min (30) > Max (20)
        'alert_min_temp': 30.0,
        'alert_max_temp': 20.0
    }
    form = TerrariumSettingsForm(data=data)

    # Jeśli ten test przejdzie (form.is_valid() == True), to znaczy że masz dziurę w logice!
    # Powinno być False.
    if form.is_valid():
        pytest.fail("Formularz pozwolił ustawić Min Temp > Max Temp!")

    assert form.is_valid() is False
