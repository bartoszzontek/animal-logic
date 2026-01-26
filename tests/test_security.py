import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from apps.core.models import Terrarium


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username='hacker', password='password')


@pytest.mark.django_db
def test_user_cannot_access_others_dashboard(client, other_user, terrarium):
    """
    SCENARIUSZ: Zalogowany 'hacker' próbuje wejść na dashboard
    terrarium, które należy do 'testadmin' (fixture 'terrarium').
    OCZEKIWANE: 404 Not Found (bo używamy get_object_or_404 z filtrem ownera).
    """
    # Logujemy się jako hacker (nie właściciel)
    client.force_login(other_user)

    url = reverse('dashboard', args=[terrarium.device_id])
    response = client.get(url)

    # Django powinno powiedzieć "Nie ma takiego terrarium" (dla Ciebie),
    # zamiast pokazać dane.
    assert response.status_code == 404


@pytest.mark.django_db
def test_user_cannot_delete_others_device(client, other_user, terrarium):
    """
    SCENARIUSZ: Hacker próbuje usunąć cudze urządzenie wysyłając POST.
    OCZEKIWANE: 404 Not Found.
    """
    client.force_login(other_user)

    url = reverse('delete_device', args=[terrarium.device_id])
    response = client.post(url)

    assert response.status_code == 404

    # Upewniamy się, że urządzenie NADAL ma właściciela (nie zostało usunięte)
    terrarium.refresh_from_db()
    assert terrarium.owner is not None


@pytest.mark.django_db
def test_user_cannot_toggle_others_light(client, other_user, terrarium):
    """
    SCENARIUSZ: Hacker próbuje włączyć światło u sąsiada.
    """
    client.force_login(other_user)
    url = reverse('toggle_light', args=[terrarium.device_id])

    response = client.get(url)
    assert response.status_code == 404