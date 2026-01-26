import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from apps.core.models import Terrarium, Reading, AllowedDevice


# --- TESTY AUTORYZACJI (AUTH) ---

@pytest.mark.django_db
def test_register_view(client):
    """Sprawdza, czy rejestracja tworzy użytkownika i loguje go."""
    url = reverse('register')
    data = {
        'username': 'newuser',
        'password': 'password123',
        # Jeśli Twój formularz ma confirm_password, zostaw to.
        # Jeśli nie, możesz usunąć. Formularz Django UserCreationForm zazwyczaj tego wymaga.
        'confirm_password': 'password123',
        'email': 'new@test.com'
    }

    response = client.post(url, data)

    assert response.status_code == 302
    assert response.url == reverse('home')
    assert User.objects.filter(username='newuser').exists()
    assert int(client.session['_auth_user_id']) == User.objects.get(username='newuser').pk


@pytest.mark.django_db
def test_login_view(client, user):
    """Sprawdza logowanie istniejącego usera."""
    url = reverse('login')

    # 1. Logowanie poprawne
    response = client.post(url, {'username': 'testadmin', 'password': 'password'})
    assert response.status_code == 302
    assert response.url == reverse('home')

    # 2. Logowanie błędne
    client.logout()
    response = client.post(url, {'username': 'testadmin', 'password': 'WRONGPASSWORD'})
    assert response.status_code == 200

    messages = list(response.context['messages'])
    assert len(messages) > 0
    assert "Błędne dane" in str(messages[0])


@pytest.mark.django_db
def test_logout_view(client, user):
    """Sprawdza wylogowanie."""
    client.force_login(user)
    url = reverse('logout')

    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse('login')
    assert '_auth_user_id' not in client.session


# --- TESTY CORE (HOME, DEVICES, DASHBOARD) ---

@pytest.mark.django_db
def test_home_view_authenticated(client, user, terrarium):
    """Zalogowany user powinien widzieć swoje terraria."""
    client.force_login(user)
    response = client.get(reverse('home'))

    assert response.status_code == 200
    assert 'devices' in response.context
    assert len(response.context['devices']) == 1
    assert response.context['devices'][0] == terrarium


@pytest.mark.django_db
def test_home_view_anonymous(client):
    """Niezalogowany user widzi stronę startową, ale bez urządzeń."""
    response = client.get(reverse('home'))
    assert response.status_code == 200
    assert len(response.context['devices']) == 0


@pytest.mark.django_db
def test_add_device_view(client, user):
    """Test dodawania nowego urządzenia do konta (z weryfikacją PIN)."""
    client.force_login(user)

    # 1. Tworzymy urządzenie w "Magazynie" (AllowedDevice)
    # Haszujemy PIN, bo formularz używa check_password
    AllowedDevice.objects.create(
        device_id='A9999',
        pin_hash=make_password('1234'),
        api_token='TOKEN_TESTOWY'
    )

    url = reverse('add_device')

    # 2. User wpisuje poprawne dane
    data = {
        'device_id': 'A9999',
        'name': 'Nowe Terra',
        'pin': '1234'
    }
    response = client.post(url, data)

    # Debugowanie
    if response.status_code == 200 and 'form' in response.context:
        print("\n🛑 BŁĘDY FORMULARZA:", response.context['form'].errors)

    assert response.status_code == 302  # Redirect na home

    # Sprawdzamy w bazie
    dev = Terrarium.objects.get(device_id='A9999')
    assert dev.owner == user
    assert dev.name == 'Nowe Terra'


@pytest.mark.django_db
def test_delete_device_view(client, user, terrarium):
    """Test odpinania urządzenia."""
    client.force_login(user)
    url = reverse('delete_device', args=[terrarium.device_id])

    response = client.post(url)

    assert response.status_code == 302

    terrarium.refresh_from_db()
    assert terrarium.owner is None
    assert Terrarium.objects.filter(pk=terrarium.pk).exists()


@pytest.mark.django_db
def test_dashboard_view_renders(client, user, terrarium):
    """Czy dashboard się ładuje dla właściciela."""
    client.force_login(user)
    url = reverse('dashboard', args=[terrarium.device_id])

    response = client.get(url)
    assert response.status_code == 200
    assert response.context['settings'] == terrarium


@pytest.mark.django_db
def test_save_settings_view(client, user, terrarium):
    """Test zapisu ustawień z dashboardu."""
    client.force_login(user)
    url = reverse('dashboard', args=[terrarium.device_id])

    data = {
        'name': 'Zmieniona Nazwa',
        'temp_day': 30.0,
        'temp_night': 25.0,
        'light_start': '09:00',
        'light_end': '21:00',
        'mist_min_humidity': 60,
        'mist_duration': 10,
        'mist_mode': 'harmonogram',
        'light_mode': 'auto',
        'mist_enabled': 'on',  # Checkbox wysyła 'on'
        'alert_min_temp': 15.0,
        'alert_max_temp': 35.0,
        'alerts_enabled': 'on'
    }

    response = client.post(url, data)

    if response.status_code == 200 and 'form' in response.context:
        print("\n🛑 BŁĘDY FORMULARZA (DASHBOARD):", response.context['form'].errors)

    assert response.status_code == 302

    terrarium.refresh_from_db()
    assert terrarium.name == 'Zmieniona Nazwa'
    assert terrarium.mist_enabled is True


@pytest.mark.django_db
def test_toggle_light(client, user, terrarium):
    """
    Test przełączania światła w trybie ręcznym.
    Używamy nowego widoku 'toggle_light_state'.
    """
    client.force_login(user)

    # 1. Przygotowanie: Ustawiamy tryb manualny i światło wyłączone
    terrarium.light_mode = 'manual'
    terrarium.light_manual_state = False
    terrarium.save()

    # 2. Wywołanie akcji (Toggle)
    url = reverse('toggle_light_state', args=[terrarium.device_id])
    response = client.get(url)

    # 3. Sprawdzenie
    assert response.status_code == 302  # Redirect

    terrarium.refresh_from_db()

    # Oczekujemy: Tryb nadal manual, stan zmienił się na True (Włączone)
    assert terrarium.light_mode == 'manual'
    assert terrarium.light_manual_state is True


# --- TESTY API (WYKRESY) ---

@pytest.mark.django_db
def test_chart_data_json(client, user, terrarium):
    """Sprawdza czy endpoint wykresu zwraca poprawny JSON."""
    client.force_login(user)

    # Dodajemy jakieś odczyty
    Reading.objects.create(terrarium=terrarium, temp=22, hum=50)
    Reading.objects.create(terrarium=terrarium, temp=23, hum=55)

    # UWAGA: Nowy widok chart_data nie przyjmuje parametru 'period' (np. 'day') w URL
    url = reverse('chart_data', args=[terrarium.device_id])

    response = client.get(url)
    assert response.status_code == 200

    data = response.json()
    assert 'labels' in data
    assert 'temps' in data
    assert len(data['temps']) == 2
    assert data['temps'][0] == 22.0


# --- TESTY PWA (MANIFEST & SERVICE WORKER) ---

def test_manifest_view(client):
    url = reverse('manifest')
    response = client.get(url)
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/json'
    assert response.json()['name'] == "AnimalLogic"


def test_service_worker_view(client):
    url = reverse('service_worker')
    response = client.get(url)
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/javascript'
    assert "const CACHE_NAME" in response.content.decode()


def test_offline_view(client):
    url = reverse('offline')
    response = client.get(url)
    assert response.status_code == 200
    assert "Nie masz dostępu do internetu" in response.content.decode() or "offline" in response.content.decode()