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

    # Tworzymy PRAWDZIWĄ datę (rok/mc/dzien nie wazne, wazna godzina 12:00)
    fixed_now = datetime(2024, 1, 1, 12, 0, 0)

    with patch('django.utils.timezone.localtime') as mock_now:
        mock_now.return_value = fixed_now  # Widok dostanie prawdziwy obiekt datetime

        response = api_client.post(
            ENDPOINT_UPDATE,
            data=json.dumps(api_payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {allowed_device.api_token}'
        )

        if response.status_code != 200:
            print(f"\n🛑 API ERROR: {response.content.decode()}")

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

    # Godzina 01:00 w nocy
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
def test_mist_schedule_logic(api_client, allowed_device, terrarium, api_payload):
    """
    Scenariusz: Zraszanie o 15:30. Jest 15:30.
    """
    terrarium.mist_mode = 'harmonogram'
    terrarium.mist_h1 = time(15, 30)
    terrarium.save()

    # Godzina 15:30
    fixed_now = datetime(2024, 1, 1, 15, 30, 0)

    with patch('django.utils.timezone.localtime') as mock_now:
        mock_now.return_value = fixed_now
        # Nie musimy mockować strftime, bo fixed_now to prawdziwy datetime i ma tę metodę!

        response = api_client.post(
            ENDPOINT_UPDATE,
            data=json.dumps(api_payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {allowed_device.api_token}'
        )

        assert response.status_code == 200
        assert response.json()['mist'] is True


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