import pytest
import json
from django.urls import reverse
from apps.core.models import AllowedDevice, Terrarium
from django.contrib.auth.hashers import make_password


# --- KONFIGURACJA ŚRODOWISKA TESTOWEGO ---

@pytest.fixture
def setup_ota_env(db, django_user_model):
    """
    Tworzy:
    1. Użytkownika (właściciela)
    2. Użytkownika (hakera)
    3. Urządzenie (AllowedDevice)
    4. Terrarium przypisane do właściciela
    """
    owner = django_user_model.objects.create_user(username='owner', password='password')
    hacker = django_user_model.objects.create_user(username='hacker', password='password')

    allowed = AllowedDevice.objects.create(
        device_id='ESP_OTA_TEST',
        pin_hash=make_password('1234'),
        api_token='TOKEN_OTA_123'
    )

    terra = Terrarium.objects.create(
        device_id='ESP_OTA_TEST',
        name='OTA Lab',
        owner=owner,
        update_required=False  # Domyślnie False
    )

    return owner, hacker, allowed, terra


@pytest.mark.django_db
class TestRemoteOTA:

    # ----------------------------------------------------------------
    # 1. TESTY WIDOKU (PRZYCISK NA DASHBOARDZIE)
    # ----------------------------------------------------------------

    def test_trigger_ota_button_sets_flag(self, client, setup_ota_env):
        """
        SCENARIUSZ: Właściciel klika 'Wyślij Aktualizację' (POST).
        OCZEKIWANE: W bazie update_required zmienia się na True.
        """
        owner, _, _, terra = setup_ota_env
        client.force_login(owner)

        url = reverse('trigger_ota', args=[terra.device_id])
        response = client.post(url)

        # 1. Powinno przekierować z powrotem na dashboard
        assert response.status_code == 302
        assert response.url == reverse('dashboard', args=[terra.device_id])

        # 2. Sprawdzamy bazę
        terra.refresh_from_db()
        assert terra.update_required is True, "Przycisk nie ustawił flagi w bazie!"

    def test_trigger_ota_security_check(self, client, setup_ota_env):
        """
        SCENARIUSZ: Zalogowany haker próbuje wywołać update cudzego urządzenia.
        OCZEKIWANE: Błąd 404 (nie znaleziono urządzenia dla tego usera).
        """
        _, hacker, _, terra = setup_ota_env
        client.force_login(hacker)

        url = reverse('trigger_ota', args=[terra.device_id])
        response = client.post(url)

        assert response.status_code == 404

        terra.refresh_from_db()
        assert terra.update_required is False, "Haker zdołał wywołać aktualizację!"

    def test_trigger_ota_requires_post(self, client, setup_ota_env):
        """
        SCENARIUSZ: Ktoś wchodzi na link /update/ metodą GET (np. wpisując w przeglądarce).
        OCZEKIWANE: Flaga NIE zmienia się (bezpieczeństwo przed crawlerami).
        """
        owner, _, _, terra = setup_ota_env
        client.force_login(owner)

        url = reverse('trigger_ota', args=[terra.device_id])
        client.get(url)  # Metoda GET

        terra.refresh_from_db()
        assert terra.update_required is False, "Metoda GET nie powinna wyzwalać aktualizacji!"

    # ----------------------------------------------------------------
    # 2. TESTY API (KOMUNIKACJA Z ESP32)
    # ----------------------------------------------------------------

    def test_api_sends_ota_command_when_flag_is_true(self, client, setup_ota_env):
        """
        SCENARIUSZ: Flaga w bazie jest True. ESP łączy się z API.
        OCZEKIWANE:
        1. JSON zwrotny ma "ota": True.
        2. Flaga w bazie natychmiast zmienia się na False (Reset).
        """
        _, _, allowed, terra = setup_ota_env

        # Ustawiamy stan początkowy: Użytkownik zlecił update
        terra.update_required = True
        terra.save()

        # ESP wysyła dane
        url = reverse('api_sensor_update')
        payload = {
            "token": allowed.api_token,
            "temp": 25.0, "hum": 50.0,
            "heater_state": False, "mist_state": False, "light_state": False
        }

        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 200
        data = response.json()

        # SPRAWDZENIE 1: Czy ESP dostało rozkaz?
        assert data['ota'] is True, "API nie wysłało rozkazu OTA mimo flagi w bazie!"

        # SPRAWDZENIE 2: Czy flaga się skasowała? (KRYTYCZNE DLA UNIKNIĘCIA PĘTLI)
        terra.refresh_from_db()
        assert terra.update_required is False, "API nie zresetowało flagi po wysłaniu rozkazu!"

    def test_api_no_ota_command_usually(self, client, setup_ota_env):
        """
        SCENARIUSZ: Normalna praca (Flaga False).
        OCZEKIWANE: JSON zwrotny ma "ota": False.
        """
        _, _, allowed, terra = setup_ota_env
        # Flaga domyślnie False

        url = reverse('api_sensor_update')
        payload = {
            "token": allowed.api_token,
            "temp": 25.0, "hum": 50.0
        }

        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        data = response.json()

        assert data['ota'] is False, "API wysyła rozkaz OTA bez potrzeby!"

    # ----------------------------------------------------------------
    # 3. TESTY DASHBOARDU (UI)
    # ----------------------------------------------------------------

    def test_dashboard_shows_waiting_message(self, client, setup_ota_env):
        """
        SCENARIUSZ: Flaga jest True.
        OCZEKIWANE: Na dashboardzie nie ma przycisku, jest napis "Oczekiwanie...".
        """
        owner, _, _, terra = setup_ota_env
        client.force_login(owner)

        terra.update_required = True
        terra.save()

        url = reverse('dashboard', args=[terra.device_id])
        response = client.get(url)

        content = response.content.decode()

        assert "Oczekiwanie na zgłoszenie się urządzenia" in content
        assert "Wyślij Rozkaz Aktualizacji" not in content  # Przycisk ukryty

    def test_dashboard_shows_button_usually(self, client, setup_ota_env):
        """
        SCENARIUSZ: Flaga jest False.
        OCZEKIWANE: Widoczny przycisk do wysłania aktualizacji.
        """
        owner, _, _, terra = setup_ota_env
        client.force_login(owner)

        # Flaga False

        url = reverse('dashboard', args=[terra.device_id])
        response = client.get(url)

        content = response.content.decode()

        assert "Wyślij Rozkaz Aktualizacji" in content
        assert "Oczekiwanie na zgłoszenie" not in content