import pytest
from django.urls import reverse
from apps.core.models import Terrarium, Reading
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password  # <--- Dodaj ten import na samej górze pliku!
from apps.core.models import AllowedDevice

# --- TESTY AUTORYZACJI (AUTH) ---

@pytest.mark.django_db
def test_register_view(client):
    """Sprawdza, czy rejestracja tworzy użytkownika i loguje go."""
    url = reverse('register')
    data = {
        'username': 'newuser',
        'password': 'password123',
        'confirm_password': 'password123',  # Zakładam, że formularz tego wymaga
        'email': 'new@test.com'
    }

    # 1. Wysyłamy POST
    response = client.post(url, data)

    # 2. Oczekujemy przekierowania na stronę główną (home)
    assert response.status_code == 302
    assert response.url == reverse('home')

    # 3. Sprawdzamy czy user powstał
    assert User.objects.filter(username='newuser').exists()

    # 4. Sprawdzamy czy jest zalogowany
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
    assert response.status_code == 200  # Zostaje na stronie (błąd)
    # Sprawdzamy czy wiadomość o błędzie jest w kontekście (messages)
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
    # Sprawdzenie czy sesja wyczyszczona
    assert '_auth_user_id' not in client.session


# --- TESTY CORE (HOME, DEVICES, DASHBOARD) ---

@pytest.mark.django_db
def test_home_view_authenticated(client, user, terrarium):
    """Zalogowany user powinien widzieć swoje terraria."""
    client.force_login(user)
    response = client.get(reverse('home'))

    assert response.status_code == 200
    # Sprawdzamy czy przekazano urządzenia do szablonu
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
    """Test dodawania nowego urządzenia do konta."""
    client.force_login(user)

    # 1. KROK NAPRAWCZY: Tworzymy urządzenie w "Magazynie" (AllowedDevice)
    # Musimy zahaszować PIN, bo formularz będzie używał check_password
    AllowedDevice.objects.create(
        device_id='A9999',
        pin_hash=make_password('1234'),  # <--- Symulujemy poprawne hasło w bazie
        api_token='TOKEN_TESTOWY'
    )

    url = reverse('add_device')

    # 2. Wysyłamy dane (user wpisuje PIN '1234')
    data = {
        'device_id': 'A9999',
        'name': 'Nowe Terra',
        'pin': '1234'
    }
    response = client.post(url, data)

    # Debugowanie (jeśli nadal błąd, to pokaże dlaczego)
    if response.status_code == 200 and 'form' in response.context:
        print("\n🛑 BŁĘDY FORMULARZA:", response.context['form'].errors)

    assert response.status_code == 302  # Redirect na home

    # Sprawdzamy w bazie
    dev = Terrarium.objects.get(device_id='A9999')
    assert dev.owner == user

@pytest.mark.django_db
def test_delete_device_view(client, user, terrarium):
    """
    Test usuwania (odpinania) urządzenia.
    Ważne: Urządzenie nie znika z bazy, tylko owner=None.
    """
    client.force_login(user)
    url = reverse('delete_device', args=[terrarium.device_id])

    response = client.post(url)

    assert response.status_code == 302

    # Odświeżamy obiekt z bazy
    terrarium.refresh_from_db()
    assert terrarium.owner is None  # Już nie należy do usera
    assert Terrarium.objects.filter(pk=terrarium.pk).exists()  # Ale nadal istnieje


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
    client.force_login(user)
    url = reverse('dashboard', args=[terrarium.device_id])

    # Kompletne dane (muszą pasować do modelu Terrarium)
    data = {
        'name': 'Zmieniona Nazwa',
        'temp_day': 30.0,
        'temp_night': 25.0,
        'light_start': '09:00',
        'light_end': '21:00',
        'mist_min_humidity': 60,
        'mist_duration': 10,
        'mist_mode': 'harmonogram',  # Często zapominane pole select!
        'light_mode': 'auto',  # To też!
        'alert_min_temp': 15.0,
        'alert_max_temp': 35.0,
        'alerts_enabled': True  # Checkbox w HTML wysyla 'on' lub True
    }

    response = client.post(url, data)

    # --- DEBUGOWANIE ---
    # Jeśli dostaniemy 200 zamiast 302, wypiszmy błędy formularza
    if response.status_code == 200 and 'form' in response.context:
        print("\n🛑 BŁĘDY FORMULARZA (DASHBOARD):", response.context['form'].errors)
    # -------------------

    assert response.status_code == 302  # Oczekujemy przekierowania

    terrarium.refresh_from_db()
    assert terrarium.name == 'Zmieniona Nazwa'


@pytest.mark.django_db
def test_toggle_light(client, user, terrarium):
    """Test przycisku włączania światła (wymuszenie trybu ręcznego)."""
    client.force_login(user)
    # Stan początkowy
    terrarium.light_mode = 'auto'
    terrarium.light_manual_state = False
    terrarium.save()

    url = reverse('toggle_light', args=[terrarium.device_id])
    client.get(url)  # Ten widok działa na GET lub POST (w Twoim kodzie nie ma if method == POST)

    terrarium.refresh_from_db()

    # Oczekujemy: Przełączenia na MANUAL i włączenia światła
    assert terrarium.light_mode == 'manual'
    assert terrarium.light_manual_state is True


# --- TESTY JSON / AJAX ---

@pytest.mark.django_db
def test_history_data_json(client, user, terrarium):
    """Sprawdza czy endpoint wykresu zwraca poprawny JSON."""
    client.force_login(user)

    # Dodajemy jakieś odczyty
    Reading.objects.create(terrarium=terrarium, temp=22, hum=50)
    Reading.objects.create(terrarium=terrarium, temp=23, hum=55)

    url = reverse('history_data', args=['day']) + f'?id={terrarium.device_id}'

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
    # Service worker musi być serwowany jako javascript
    assert response['Content-Type'] == 'application/javascript'
    assert "const CACHE_NAME" in response.content.decode()


def test_offline_view(client):
    url = reverse('offline')
    response = client.get(url)
    assert response.status_code == 200
    assert "Nie masz dostępu do internetu." in response.content.decode()