import pytest
from django.core import mail
from django.utils import timezone
from datetime import timedelta

ENDPOINT = '/api/sensor/update'

@pytest.mark.django_db
def test_alert_sent_on_high_temp(api_client, allowed_device, terrarium):
    """
    SCENARIUSZ: Temperatura 40st (Max ustawiony na 35st).
    OCZEKIWANE: Wysłanie maila + aktualizacja last_alert_sent.
    """
    # Konfiguracja terrarium
    terrarium.alerts_enabled = True
    terrarium.alert_max_temp = 35.0
    terrarium.alert_email = "admin@example.com"
    terrarium.last_alert_sent = None # Nigdy nie wysłano
    terrarium.save()

    # Symulacja API (ESP zgłasza ukrop)
    data = {'temp': 40.0, 'hum': 50.0}
    api_client.post(
        ENDPOINT,
        data,
        format='json',
        headers={'Authorization': f'Bearer {allowed_device.api_token}'}
    )

    # SPRAWDZENIE 1: Czy wysłano maila?
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == f"ALARM: {terrarium.name} - Wysoka Temperatura!"
    assert "40.0" in mail.outbox[0].body
    assert mail.outbox[0].to == ["admin@example.com"]

    # SPRAWDZENIE 2: Czy zaktualizowano czas wysłania?
    terrarium.refresh_from_db()
    assert terrarium.last_alert_sent is not None

@pytest.mark.django_db
def test_alert_throttling(api_client, allowed_device, terrarium):
    """
    SCENARIUSZ: Spamowanie alertami. Jeśli alert poszedł minutę temu,
    nie wysyłaj kolejnego (żeby nie zapchać skrzynki).
    Limit np. 15 minut.
    """
    terrarium.alerts_enabled = True
    terrarium.alert_max_temp = 35.0
    terrarium.alert_email = "admin@example.com"
    # Ustawiamy, że alert poszedł minutę temu
    terrarium.last_alert_sent = timezone.now() - timedelta(minutes=1)
    terrarium.save()

    data = {'temp': 40.0, 'hum': 50.0}
    api_client.post(
        ENDPOINT,
        data,
        format='json',
        headers={'Authorization': f'Bearer {allowed_device.api_token}'}
    )

    # OCZEKIWANE: Skrzynka pusta (0 nowych maili)
    assert len(mail.outbox) == 0