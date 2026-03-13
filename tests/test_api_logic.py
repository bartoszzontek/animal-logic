import pytest
import json
from datetime import time, datetime
from unittest.mock import patch
from apps.core.models import Reading

# Endpointy
ENDPOINT_UPDATE = '/api/sensor/update'
ENDPOINT_FIRMWARE = '/api/firmware/'
ENDPOINT_CHART = '/api/chart/'


@pytest.fixture
def api_payload():
    return {'temp': 25.0, 'hum': 50.0}


@pytest.mark.django_db
def test_light_logic_simple_day(api_client, allowed_device, terrarium, api_payload):
    """
    Scenariusz: Dzień 08:00 - 20:00. Jest godzina 12:00.
    """
    terrarium.light_start = time(8, 0)
    terrarium.light_end = time(20, 0)
    terrarium.light_mode = 'auto'
    terrarium.save()

    fixed_now = datetime(2024, 1, 1, 12, 0, 0)

    with patch('django.utils.timezone.localtime') as mock_now:
        mock_now.return_value = fixed_now

        response = api_client.post(
            ENDPOINT_UPDATE,
            data=json.dumps(api_payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {allowed_device.api_token}'
        )

        assert response.status_code == 200
        assert response.json()['light'] is True


@pytest.mark.django_db
def test_light_logic_night_crossing(api_client, allowed_device, terrarium, api_payload):
    """
    Scenariusz: Dzień 20:00 - 04:00. Jest 01:00 w nocy.
    """
    terrarium.light_start = time(20, 0)
    terrarium.light_end = time(4, 0)
    terrarium.save()

    fixed_now = datetime(2024, 1, 1, 1, 0, 0)

    with patch('django.utils.timezone.localtime') as mock_now:
        mock_now.return_value = fixed_now

        response = api_client.post(
            ENDPOINT_UPDATE,
            data=json.dumps(api_payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {allowed_device.api_token}'
        )
        assert response.status_code == 200
        assert response.json()['light'] is True


@pytest.mark.django_db
def test_mist_schedule_12_slots(api_client, allowed_device, terrarium, api_payload):
    """
    Scenariusz: Weryfikacja działania 12 slotów zraszania oraz czasu trwania.
    Ustawiamy slot nr 1 na 10:00 (15 sek) oraz slot nr 12 na 18:30 (45 sek).
    Symulujemy godzinę 18:30 i sprawdzamy, czy API każe włączyć zraszacz na 45 sekund.
    """
    terrarium.mist_mode = 'harmonogram'

    # Ustawiamy slot #1
    terrarium.mist_h1 = time(10, 0)
    terrarium.mist_d1 = 15

    # Ustawiamy odległy slot #12
    terrarium.mist_h12 = time(18, 30)
    terrarium.mist_d12 = 45
    terrarium.save()

    # Symulujemy, że na serwerze jest dokładnie 18:30
    fixed_now = datetime(2024, 1, 1, 18, 30, 0)

    with patch('django.utils.timezone.localtime') as mock_now:
        mock_now.return_value = fixed_now

        response = api_client.post(
            ENDPOINT_UPDATE,
            data=json.dumps(api_payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {allowed_device.api_token}'
        )

        assert response.status_code == 200
        json_data = response.json()

        # 1. Sprawdzamy, czy system wydał komendę zraszania
        assert json_data['mist'] is True
        # 2. Sprawdzamy, czy poprawnie wczytał czas 45 sekund ze slotu #12
        assert json_data['mist_duration'] == 45


@pytest.mark.django_db
def test_mist_schedule_no_match(api_client, allowed_device, terrarium, api_payload):
    """
    Scenariusz: Zraszanie jest włączone, ale o obecnej godzinie nie ma żadnego slotu.
    Oczekujemy, że zraszacz pozostanie wyłączony.
    """
    terrarium.mist_mode = 'harmonogram'
    terrarium.mist_h3 = time(12, 0)
    terrarium.mist_d3 = 10
    terrarium.save()

    # Symulujemy godzinę 13:00 (żaden slot do niej nie pasuje)
    fixed_now = datetime(2024, 1, 1, 13, 0, 0)

    with patch('django.utils.timezone.localtime') as mock_now:
        mock_now.return_value = fixed_now

        response = api_client.post(
            ENDPOINT_UPDATE,
            data=json.dumps(api_payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {allowed_device.api_token}'
        )

        assert response.status_code == 200
        assert response.json()['mist'] is False


@pytest.mark.django_db
def test_firmware_download_security(api_client):
    url = ENDPOINT_FIRMWARE + 'secret.txt'
    response = api_client.get(url)
    assert response.status_code in [403, 404]


@pytest.mark.django_db
def test_chart_data_format(api_client, terrarium, user):
    api_client.force_login(user)
    Reading.objects.create(terrarium=terrarium, temp=25.5, hum=50.0)

    url = f'{ENDPOINT_CHART}{terrarium.device_id}/'
    response = api_client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert 'labels' in data
    assert data['temps'][0] == 25.5