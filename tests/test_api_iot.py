import pytest
import json
from django.urls import reverse
from apps.core.models import AllowedDevice, Terrarium, Reading
from django.contrib.auth.hashers import make_password


@pytest.fixture
def setup_device(db):
    """Tworzy testowe urządzenie i terrarium."""
    AllowedDevice.objects.create(
        device_id='TEST_DEV_01',
        pin_hash=make_password('1234'),
        api_token='SECRET_TOKEN_123'
    )
    Terrarium.objects.create(device_id='TEST_DEV_01', name='Test Terrarium')
    return AllowedDevice.objects.get(device_id='TEST_DEV_01')


@pytest.mark.django_db
class TestIoTUpdateAPI:

    def test_sensor_update_success(self, client, setup_device):
        url = reverse('api_sensor_update')
        payload = {
            "token": "SECRET_TOKEN_123",
            "temp": 25.5,
            "hum": 60.0,
            "heater_state": False,  # Nowe pola
            "mist_state": False,
            "light_state": True
        }
        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 200
        assert Reading.objects.count() == 1

    def test_sensor_update_invalid_token(self, client, setup_device):
        url = reverse('api_sensor_update')
        payload = {"token": "WRONG_TOKEN", "temp": 20, "hum": 50}
        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 401

    def test_thermostat_logic(self, client, setup_device):
        """
        Sprawdza, czy backend poprawnie podejmuje DECYZJĘ o włączeniu grzałki.
        Cel: 25.0 (Dzień), Obecna: 10.0 -> Rozkaz: Grzej!
        """
        url = reverse('api_sensor_update')

        # Konfiguracja celu w bazie
        terra = Terrarium.objects.get(device_id='TEST_DEV_01')
        terra.temp_day = 25.0
        terra.save()

        # ESP melduje: Jest mi zimno (10 stopni) i grzałka jest wyłączona
        payload = {
            "token": "SECRET_TOKEN_123",
            "temp": 10.0,
            "hum": 50.0,
            "heater_state": False
        }

        response = client.post(url, data=json.dumps(payload), content_type="application/json")

        assert response.status_code == 200
        data = response.json()

        # NAPRAWA: Sprawdzamy ROZKAZ (przyszłość), a nie stan w bazie (przeszłość)
        assert data['heater'] is True, "Backend powinien kazać włączyć grzanie!"

    def test_auth_via_header(self, client, setup_device):
        url = reverse('api_sensor_update')
        payload = {"temp": 22.0, "hum": 50.0}  # Bez tokena w body

        response = client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {setup_device.api_token}"
        )
        assert response.status_code == 200