import pytest
import json
from apps.core.models import Reading

ENDPOINT = '/api/sensor/update'

@pytest.mark.django_db
def test_api_rejects_no_token(api_client):
    """ESP próbuje wysłać dane bez tokenu -> Oczekiwany Błąd 401"""
    data = {'temp': 25.0, 'hum': 50.0}
    response = api_client.post(ENDPOINT, data, format='json')
    assert response.status_code == 401

@pytest.mark.django_db
def test_thermostat_logic_heating_on(api_client, allowed_device, terrarium):
    """
    TEST LOGIKI: Jest zimno (20st), cel to 28st.
    Oczekujemy, że serwer odeśle: 'heater': True
    """
    # 1. Symulujemy dane z ESP (jest 20 stopni)
    data = {'temp': 20.0, 'hum': 50.0}
    
    # 2. Wysyłamy request z poprawnym tokenem
    response = api_client.post(
        ENDPOINT,
        data,
        format='json',
        headers={'Authorization': f'Bearer {allowed_device.api_token}'}
    )

    # 3. Sprawdzamy odpowiedź
    assert response.status_code == 200
    json_resp = response.json()
    
    # 4. KLUCZOWE: Sprawdzamy czy serwer kazał włączyć grzałkę
    # Skoro jest 20C, a cel 28C -> Grzałka musi być ON
    assert json_resp['heater'] is True, "Grzałka powinna się włączyć, bo jest zimno!"
    
    # 5. Sprawdzamy czy zapisało pomiar w bazie
    assert Reading.objects.count() == 1
    assert Reading.objects.first().temp == 20.0

@pytest.mark.django_db
def test_thermostat_logic_heating_off(api_client, allowed_device, terrarium):
    """
    TEST LOGIKI: Jest gorąco (30st), cel to 28st.
    Oczekujemy, że serwer odeśle: 'heater': False
    """
    data = {'temp': 30.0, 'hum': 50.0}
    
    response = api_client.post(
        ENDPOINT,
        data,
        format='json',
        headers={'Authorization': f'Bearer {allowed_device.api_token}'}
    )

    assert response.status_code == 200
    json_resp = response.json()
    
    # Grzałka musi być OFF
    assert json_resp['heater'] is False, "Grzałka powinna się wyłączyć, bo jest za ciepło!"
