import pytest
import json
from django.test import RequestFactory
from django.conf import settings
from django.contrib.auth.hashers import make_password
from apps.core.models import Terrarium, Reading, AllowedDevice
from apps.core import views  # Importujemy widoki bezpośrednio


# --- FIXTURES ---

@pytest.fixture
def factory():
    """Fabryka zapytań, która omija Middleware (blokady 403)."""
    return RequestFactory()


@pytest.fixture
def api_device(db):
    """Tworzy urządzenie w bazie."""
    allowed = AllowedDevice.objects.create(
        device_id='ESP_TEST_01',
        pin_hash=make_password('1234'),
        api_token='SECRET_TOKEN_123'
    )
    terra = Terrarium.objects.create(
        device_id='ESP_TEST_01',
        name='Test API Terra'
    )
    return allowed, terra


# --- TESTY BEZPOŚREDNIE (OMIJAMY URLS.PY) ---

@pytest.mark.django_db
def test_sensor_update_success(factory, api_device):
    """Testuje funkcję views.api_sensor_update bezpośrednio."""
    allowed_dev, terra = api_device

    # 1. Przygotuj dane
    payload = {
        "device_id": "ESP_TEST_01",
        "token": "SECRET_TOKEN_123",
        "temp": 24.5, "hum": 60.0,
        "heater": False, "light": True
    }

    # 2. Stwórz "sztuczne" żądanie POST (z pominięciem sieci)
    request = factory.post(
        '/api/sensor/update',
        data=json.dumps(payload),
        content_type='application/json'
    )

    # 3. Wywołaj widok RĘCZNIE
    response = views.api_sensor_update(request)

    # 4. Sprawdź wynik
    if response.status_code != 200:
        print(f"\n🛑 BŁĄD WIDOKU: {response.content.decode()}")

    assert response.status_code == 200, f"BŁĄD SERWERA: {response.content.decode()}"
    assert Reading.objects.filter(terrarium=terra).count() == 1


@pytest.mark.django_db
def test_device_auth_view(factory, api_device):
    """Testuje funkcję views.api_device_auth bezpośrednio."""
    allowed_dev, terra = api_device

    payload = {"device_id": "ESP_TEST_01", "pin": "1234"}

    request = factory.post(
        '/api/auth/device',
        data=json.dumps(payload),
        content_type='application/json'
    )

    response = views.api_device_auth(request)

    if response.status_code != 200:
        print(f"\n🛑 BŁĄD PINU: {response.content.decode()}")

    assert response.status_code == 200
    assert json.loads(response.content)['token'] == 'SECRET_TOKEN_123'


def test_firmware_download_success(factory, tmp_path, settings):
    """Testuje pobieranie pliku bezpośrednio."""
    # 1. Stwórz plik tymczasowy
    fw_dir = tmp_path / "firmware"
    fw_dir.mkdir()
    settings.FIRMWARE_ROOT = str(fw_dir)

    p = fw_dir / "eps32.bin"
    p.write_bytes(b"BINARY_DATA")

    # 2. Stwórz żądanie GET
    request = factory.get('/api/firmware/eps32.bin')

    # 3. Wywołaj widok
    response = views.download_firmware(request, filename='eps32.bin')

    assert response.status_code == 200
    # Pobieramy treść z generatora pliku (FileResponse)
    assert b"BINARY_DATA" in b"".join(response.streaming_content)


def test_firmware_download_not_found(factory):
    """Testuje brak pliku."""
    request = factory.get('/api/firmware/ghost.bin')

    # Wywołujemy widok - powinien rzucić wyjątkiem Http404 lub zwrócić 404
    # Widoki Django często rzucają wyjątek, który Middleware zamienia na 404.
    # W testach bezpośrednich musimy złapać ten wyjątek LUB sprawdzić response.

    from django.http import Http404

    try:
        response = views.download_firmware(request, filename='ghost.bin')
        assert response.status_code == 404
    except Http404:
        # Jeśli rzucił wyjątek Http404, to też jest sukces (Django by to obsłużyło)
        assert True