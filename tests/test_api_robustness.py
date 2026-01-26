import pytest
import json

ENDPOINT = '/api/sensor/update'

@pytest.fixture
def auth_header(allowed_device):
    return {'HTTP_AUTHORIZATION': f'Bearer {allowed_device.api_token}'}

@pytest.mark.django_db
def test_api_handles_garbage_json(api_client, auth_header):
    """
    Scenariusz: ESP wysyła niepoprawny JSON (np. ucięty w połowie).
    Oczekiwane: 400 Bad Request.
    """
    response = api_client.post(
        ENDPOINT,
        data="{ 'temp': 25, ", # Błędna składnia JSON
        content_type='application/json',
        **auth_header
    )
    # Obecnie Twój kod rzuca Exception -> 500.
    # Profesjonalnie powinno być 400.
    assert response.status_code == 400

@pytest.mark.django_db
def test_api_handles_missing_fields(api_client, auth_header):
    """
    Scenariusz: Brakuje pola 'hum'.
    Oczekiwane: 400 Bad Request (nie można zapisać do bazy bez wilgotności).
    """
    data = {'temp': 25.0} # Brak hum
    response = api_client.post(
        ENDPOINT,
        data=json.dumps(data),
        content_type='application/json',
        **auth_header
    )
    assert response.status_code == 400
    assert 'error' in response.json()

@pytest.mark.django_db
def test_api_handles_wrong_data_types(api_client, auth_header):
    """
    Scenariusz: Zamiast liczby przychodzi tekst.
    Oczekiwane: 400 Bad Request.
    """
    data = {'temp': "sensor_error", 'hum': 50.0}
    response = api_client.post(
        ENDPOINT,
        data=json.dumps(data),
        content_type='application/json',
        **auth_header
    )
    assert response.status_code == 400
