import pytest
import json
from django.urls import reverse
from apps.core.models import AllowedDevice, Terrarium, Reading
from django.contrib.auth.hashers import make_password


@pytest.fixture
def setup_iot(db):
    """Tworzy środowisko: Urządzenie, Token, Terrarium"""
    allowed = AllowedDevice.objects.create(
        device_id='ESP_FEEDBACK_TEST',
        pin_hash=make_password('1234'),
        api_token='TOKEN_FEEDBACK_123'
    )
    terra = Terrarium.objects.create(
        device_id='ESP_FEEDBACK_TEST',
        name='Feedback Lab',
        temp_day=25.0,
        temp_night=20.0
    )
    return allowed, terra


@pytest.mark.django_db
class TestFeedbackLoop:

    def test_feedback_is_saved_live(self, client, setup_iot):
        allowed, terra = setup_iot
        url = reverse('api_sensor_update')

        payload = {
            "token": allowed.api_token,
            "temp": 24.0,
            "hum": 50.0,
            "heater_state": True,
            "mist_state": False,
            "light_state": True
        }

        client.post(url, data=json.dumps(payload), content_type="application/json")
        terra.refresh_from_db()
        assert terra.is_heating is True
        assert terra.is_online is True

    def test_feedback_is_saved_history(self, client, setup_iot):
        allowed, terra = setup_iot
        url = reverse('api_sensor_update')

        payload = {
            "token": allowed.api_token,
            "temp": 24.0, "hum": 50.0,
            "heater_state": True,
            "mist_state": True,
            "light_state": False
        }

        client.post(url, data=json.dumps(payload), content_type="application/json")
        reading = Reading.objects.last()
        assert reading.heater is True
        assert reading.mist is True
        assert reading.light is False

    def test_deadband_logic_uses_feedback(self, client, setup_iot):
        """
        SCENARIUSZ (Histereza):
        Cel: 25.0 st. Obecna: 24.8 st (strefa martwa).
        """
        allowed, terra = setup_iot
        url = reverse('api_sensor_update')

        # --- NAPRAWA: WYMUSZAMY TRYB DZIENNY ---
        # Żeby test nie brał temperatury nocnej (20.0) jeśli uruchamiasz go w nocy
        terra.temp_day = 25.0
        terra.light_mode = 'manual'
        terra.light_manual_state = True  # To wymusza użycie temp_day
        terra.save()
        # ---------------------------------------

        # Przypadek A: Grzałka chodzi -> ma chodzić dalej
        payload_a = {
            "token": allowed.api_token,
            "temp": 24.8,
            "hum": 50.0,
            "heater_state": True  # Feedback: "Grzeję"
        }
        resp_a = client.post(url, data=json.dumps(payload_a), content_type="application/json")

        # Jeśli tu pada, to znaczy że cel jest źle wyliczony
        debug_target = resp_a.json().get('target')
        assert resp_a.json()['heater'] is True, f"Błąd histerezy! Cel: {debug_target}, Obecna: 24.8, Feedback: True"

        # Przypadek B: Grzałka stoi -> ma stać dalej
        payload_b = {
            "token": allowed.api_token,
            "temp": 24.8,
            "hum": 50.0,
            "heater_state": False  # Feedback: "Nie grzeję"
        }
        resp_b = client.post(url, data=json.dumps(payload_b), content_type="application/json")
        assert resp_b.json()['heater'] is False, "W strefie martwej włączono grzanie bez potrzeby!"

    def test_alert_content_format(self, client, setup_iot, mailoutbox):
        allowed, terra = setup_iot
        terra.alerts_enabled = True
        terra.alert_email = "test@test.pl"
        terra.alert_max_temp = 30.0
        terra.last_alert_sent = None
        terra.save()

        payload = {"token": allowed.api_token, "temp": 40.0, "hum": 50.0}
        client.post(reverse('api_sensor_update'), data=json.dumps(payload), content_type="application/json")

        assert len(mailoutbox) == 1
        expected_subject = f"ALARM: {terra.name} - Wysoka Temperatura!"
        assert mailoutbox[0].subject == expected_subject