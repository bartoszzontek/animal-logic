import pytest
from django.utils import timezone
from django.urls import reverse
from apps.core.models import Terrarium


@pytest.mark.django_db
class TestUINavigation:

    # 1. TEST DLA GOŚCIA (Niezalogowany)
    def test_home_page_for_guest(self, client):
        """
        Sprawdza, czy gość widzi Landing Page.
        """
        url = reverse('home')
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Co MA być:
        assert "Pełna kontrola" in content  # Tekst z Landing Page
        assert "/login/" in content  # Link logowania

        # Czego ma NIE być:
        # Zmieniamy sprawdzanie tekstu na sprawdzanie LINKU.
        # Tekst może być w stylach CSS, link HTML pojawia się tylko gdy user ma uprawnienia.
        assert 'action="/logout/"' not in content
        assert 'href="/logout/"' not in content
        assert 'href="/admin/"' not in content

    # 2. TEST DLA ZWYKŁEGO UŻYTKOWNIKA
    def test_home_page_for_logged_user(self, client, django_user_model):
        """
        Sprawdza, czy zalogowany widzi Dashboard, ale NIE widzi linku do Admina.
        """
        user = django_user_model.objects.create_user(username='zwykly', password='password')
        client.force_login(user)

        url = reverse('home')
        response = client.get(url)
        content = response.content.decode()

        # Co MA być:
        assert f"Cześć, {user.username}" in content
        assert 'action="/logout/"' in content  # Formularz wylogowania

        # Czego ma NIE być:
        assert "Pełna kontrola" not in content
        assert '/login/' not in content

        # POPRAWKA: Sprawdzamy obecność linku HTML, a nie nazwy klasy w CSS
        assert 'href="/admin/"' not in content

        # 3. TEST DLA ADMINA

    def test_navbar_for_admin(self, client, django_user_model):
        """
        Sprawdza, czy administrator widzi link /admin/.
        """
        admin = django_user_model.objects.create_user(username='szef', password='password', is_staff=True)
        client.force_login(admin)

        url = reverse('home')
        response = client.get(url)
        content = response.content.decode()

        # Admin musi widzieć link href="/admin/"
        assert 'href="/admin/"' in content

    # 4. TEST LISTY URZĄDZEŃ
    def test_dashboard_shows_user_devices(self, client, django_user_model):
        """
        Sprawdza, czy na liście pojawia się dodane urządzenie.
        """
        user = django_user_model.objects.create_user(username='hodowca', password='password')

        # POPRAWKA: Ustawiamy pola bazodanowe, a nie @property
        Terrarium.objects.create(
            device_id='TEST_DEV_1',
            name='Gekon Leon',
            owner=user,
            is_online=True,  # To jest pole w bazie
            last_seen=timezone.now()  # To sprawi, że property .is_active zwróci True
        )

        client.force_login(user)
        response = client.get(reverse('home'))
        content = response.content.decode()

        assert "Gekon Leon" in content
        assert "ONLINE" in content
        assert "TEST_DEV_1" in content