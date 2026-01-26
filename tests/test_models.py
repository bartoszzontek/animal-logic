import pytest
from datetime import timedelta
from django.utils import timezone
from apps.core.models import Terrarium, AllowedDevice, Reading


@pytest.mark.django_db
def test_allowed_device_token_generation():
    """Sprawdza czy save() automatycznie generuje token, jeśli go brak."""
    device = AllowedDevice.objects.create(
        device_id="TEST-GEN",
        pin_hash="1234"
        # Nie podajemy api_token
    )
    assert device.api_token is not None
    assert len(device.api_token) > 10


@pytest.mark.django_db
def test_terrarium_is_active_logic(user):
    """
    Testuje właściwość .is_active (Offline/Online).
    Limit wynosi 30 sekund.
    """
    # 1. Tworzymy terrarium
    t = Terrarium.objects.create(device_id="A1", owner=user, name="T1")

    # Przypadek A: Nigdy nie widziane -> False
    assert t.is_active is False

    # Przypadek B: Widziane 10 sekund temu -> True
    t.last_seen = timezone.now() - timedelta(seconds=10)
    t.save()
    assert t.is_active is True

    # Przypadek C: Widziane 31 sekund temu -> False
    t.last_seen = timezone.now() - timedelta(seconds=31)
    t.save()
    assert t.is_active is False


@pytest.mark.django_db
def test_reading_ordering(terrarium):
    """Sprawdza czy odczyty sortują się od najnowszego."""
    r1 = Reading.objects.create(terrarium=terrarium, temp=20, hum=50, timestamp=timezone.now() - timedelta(hours=1))
    r2 = Reading.objects.create(terrarium=terrarium, temp=21, hum=51, timestamp=timezone.now())

    readings = list(Reading.objects.filter(terrarium=terrarium))

    # Pierwszy na liście powinien być r2 (najnowszy)
    assert readings[0] == r2
    assert readings[1] == r1


@pytest.mark.django_db
def test_str_representations(allowed_device, terrarium):
    """Sprawdza czy __str__ nie wywala błędu."""
    assert str(allowed_device).startswith(allowed_device.device_id)
    assert str(terrarium) == f"{terrarium.name} ({terrarium.device_id})"