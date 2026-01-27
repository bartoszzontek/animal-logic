import pytest
import json
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from apps.core.models import AllowedDevice, Terrarium, Reading


@pytest.mark.django_db
class TestIoTUpdateAPI:

    @pytest.fixture
    def setup_device(self):
        """Tworzy urządzenie testowe i token w bazie"""
        device = AllowedDevice.objects.create(
            device_id="TEST_DEV_01",
            pin_hash=make_password("1234"),
            api_token="SECRET_TOKEN_123"
        )
        # Tworzymy też instancję Terrarium z ustawieniami
        Terrarium.objects.create(
            device_id="TEST_DEV_01",
            name="Test Terrarium",
            temp_day=25.0,
            temp_night=20.0,
            light_mode='auto'
        )
        return device

    def test_sensor_update_success(self, client, setup_device):
        """
        Sprawdza, czy API przyjmuje dane z symulatora (Token w JSON body)
        i zapisuje je poprawnie w bazie używając nowych nazw pól.
        """
        url = reverse('api_sensor_update')  # Upewnij się, że w urls.py nazwa to 'api_sensor_update'

        payload = {
            "token": "SECRET_TOKEN_123",  # Symulator wysyła token w body
            "temp": 22.5,
            "hum": 50.0
        }

        response = client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json"
        )

        # 1. Sprawdź status HTTP
        assert response.status_code == 200, f"Błąd API: {response.content.decode()}"

        # 2. Sprawdź czy dane zapisały się w bazie
        reading = Reading.objects.last()
        assert reading is not None
        assert reading.temp == 22.5
        assert reading.hum == 50.0

        # 3. KLUCZOWE: Sprawdź czy pola logiczne istnieją i mają wartości boolean
        # (To potwierdza, że usunęliśmy 'is_heater_on' na rzecz 'heater')
        assert hasattr(reading, 'heater')
        assert hasattr(reading, 'light')
        assert hasattr(reading, 'mist')

    def test_sensor_update_invalid_token(self, client, setup_device):
        """Sprawdza czy odrzucamy błędny token"""
        url = reverse('api_sensor_update')

        payload = {
            "token": "ZLY_TOKEN_XYZ",
            "temp": 20.0,
            "hum": 50.0
        }

        response = client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 401  # Unauthorized

    def test_thermostat_logic(self, client, setup_device):
        """
        Sprawdza, czy backend poprawnie decyduje o włączeniu grzałki.
        Cel: 25.0, Obecna: 20.0 -> Grzałka powinna być ON.
        """
        url = reverse('api_sensor_update')

        # Wysyłamy temperaturę 10.0 (bardzo zimno)
        payload = {
            "token": "SECRET_TOKEN_123",
            "temp": 10.0,
            "hum": 50.0
        }

        response = client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.json()

        # Backend powinien odesłać rozkaz włączenia grzałki
        assert data['heater'] is True, "Termostat powinien włączyć grzanie przy 10 stopniach!"

        # Sprawdzamy czy w bazie też zapisało się True
        reading = Reading.objects.last()
        assert reading.heater is True

    def test_auth_via_header(self, client, setup_device):
        """
        Sprawdza, czy API działa też z tokenem w nagłówku (dla prawdziwego ESP)
        """
        url = reverse('api_sensor_update')
        payload = {"temp": 22.0, "hum": 60.0}

        # Token w nagłówku Authorization
        headers = {"HTTP_AUTHORIZATION": "Bearer SECRET_TOKEN_123"}

        response = client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            **headers
        )

        assert response.status_code == 200