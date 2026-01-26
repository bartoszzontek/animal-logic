import pytest
from apps.core.models import Terrarium, AllowedDevice
from django.contrib.auth.models import User
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user(db):
    return User.objects.create_user(username='testadmin', password='password')

@pytest.fixture
def allowed_device(db):
    # POPRAWIONE: Usunąłem pole 'name', bo Twój model go nie ma
    return AllowedDevice.objects.create(
        device_id='A1001',
        api_token='TOKEN_TESTOWY_123',
        pin_hash='1234'
    )

@pytest.fixture
def terrarium(db, allowed_device, user):
    return Terrarium.objects.create(
        device_id=allowed_device.device_id,
        name='Test Terra',
        owner=user,
        temp_day=28.0,
        temp_night=22.0,
        light_start='08:00',
        light_end='20:00',
        # hysteresis=0.5, # To tez moze wywalic blad jesli nie masz tego pola, sprawdz models.py
        # manual_mode=False
    )