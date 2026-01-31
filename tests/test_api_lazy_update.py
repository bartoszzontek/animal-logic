import pytest
import json
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from apps.core.models import Terrarium, AllowedDevice


@pytest.fixture
def setup_env(db, django_user_model):
    """Tworzy użytkownika i terrarium"""
    user = django_user_model.objects.create_user(username='tester', password='password')

    # Urządzenie
    terra = Terrarium.objects.create(
        device_id='LAZY_TEST_DEV',
        name='Lazy Lab',
        owner=user,
        is_online=True,  # Zakładamy, że jest online na start
        last_seen=timezone.now()
    )
    return user, terra


@pytest.mark.django_db
class TestLazyStatusUpdate:

    def test_api_detects_zombie_device_and_fixes_db(self, client, setup_env):
        """
        SCENARIUSZ: Urządzenie ma w bazie is_online=True,
        ale last_seen było 5 minut temu (jest martwe).

        OCZEKIWANE:
        1. Widok API zmienia is_online w bazie na False.
        2. Widok zwraca JSON z "online": false.
        """
        user, terra = setup_env
        client.force_login(user)

        # 1. Symulujemy stan "Zombie" (Baza mówi Online, Czas mówi Offline)
        terra.is_online = True
        terra.last_seen = timezone.now() - timedelta(minutes=5)  # 5 min temu
        terra.save()

        # 2. Strzał do API (to co robi Dashboard co 3 sekundy)
        url = reverse('api_get_latest_data', args=[terra.device_id])
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # SPRAWDZENIE ODPOWIEDZI JSON
        assert data['online'] is False, "API powinno zwrócić False dla starego urządzenia!"

        # SPRAWDZENIE BAZY DANYCH (Samonaprawa)
        terra.refresh_from_db()
        assert terra.is_online is False, "API powinno naprawić flagę w bazie danych na False!"

    def test_api_keeps_healthy_device_online(self, client, setup_env):
        """
        SCENARIUSZ: Urządzenie nadało sygnał 5 sekund temu.

        OCZEKIWANE:
        1. JSON zwraca "online": true.
        2. Baza pozostaje bez zmian (True).
        """
        user, terra = setup_env
        client.force_login(user)

        # 1. Stan "Zdrowy"
        terra.is_online = True
        terra.last_seen = timezone.now() - timedelta(seconds=5)  # 5 sek temu
        terra.save()

        url = reverse('api_get_latest_data', args=[terra.device_id])
        response = client.get(url)
        data = response.json()

        assert data['online'] is True

        terra.refresh_from_db()
        assert terra.is_online is True

    def test_api_handles_null_last_seen(self, client, setup_env):
        """
        SCENARIUSZ: Urządzenie jest nowe i nigdy nie nadało sygnału (last_seen=None).
        OCZEKIWANE: Online = False.
        """
        user, terra = setup_env
        client.force_login(user)

        terra.is_online = True  # Błędny stan
        terra.last_seen = None  # Nigdy nie widziano
        terra.save()

        url = reverse('api_get_latest_data', args=[terra.device_id])
        response = client.get(url)
        data = response.json()

        assert data['online'] is False
        assert data['last_seen'] == 'Brak danych'

        terra.refresh_from_db()
        assert terra.is_online is False