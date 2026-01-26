import pytest
from django.urls import reverse
from apps.core.models import AllowedDevice


@pytest.mark.django_db
def test_admin_can_create_allowed_device(client, admin_user):
    """
    Scenariusz: Admin wchodzi do panelu i dodaje nowe ESP32.
    Oczekiwane: Urządzenie powstaje, token generuje się automatycznie.
    """
    # Logujemy superusera (pytest-django fixture 'admin_user')
    client.force_login(admin_user)

    url = reverse('admin:core_alloweddevice_add')

    data = {
        'device_id': 'NEW-ESP',
        'pin_hash': '1234',
        # Nie podajemy api_token - powinien się wygenerować sam
    }

    response = client.post(url, data)

    # 302 oznacza sukces (przekierowanie do listy po zapisie)
    assert response.status_code == 302

    # Sprawdzamy czy powstało w bazie
    device = AllowedDevice.objects.get(device_id='NEW-ESP')
    assert device.api_token is not None
    assert len(device.api_token) > 10