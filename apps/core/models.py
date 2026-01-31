# apps/core/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime
from datetime import timedelta
import secrets

class AllowedDevice(models.Model):
    device_id = models.CharField(max_length=50, unique=True)
    pin_hash = models.CharField(max_length=128)
    api_token = models.CharField(max_length=64, blank=True, null=True, unique=True)

    def save(self, *args, **kwargs):
        if not self.api_token:
            self.api_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        token_str = self.api_token[:10] if self.api_token else "BRAK"
        return f"{self.device_id} (Token: {token_str}...)"


class Terrarium(models.Model):
    """
    Główne ustawienia i stan terrarium.
    """
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='terrariums')
    device_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100, default="Moje Terrarium")

    # Termostat
    temp_day = models.FloatField(default=28.0, verbose_name="Temp. Dzień")
    temp_night = models.FloatField(default=22.0, verbose_name="Temp. Noc")

    # --- ALERTY ---
    alerts_enabled = models.BooleanField(default=True, verbose_name="Alerty Email włączone")
    alert_email = models.EmailField(max_length=254, blank=True, null=True, verbose_name="Email do powiadomień")
    alert_min_temp = models.FloatField(default=18.0, verbose_name="Alarm Min Temp")
    alert_max_temp = models.FloatField(default=35.0, verbose_name="Alarm Max Temp")
    last_alert_sent = models.DateTimeField(null=True, blank=True)

    # Cykl Dnia (Światło)
    light_start = models.TimeField(default=datetime.time(8, 0))
    light_end = models.TimeField(default=datetime.time(20, 0))
    light_mode = models.CharField(max_length=10, default='auto', choices=[('auto', 'Automat'), ('manual', 'Ręczny')])
    light_manual_state = models.BooleanField(default=False, verbose_name="Stan ręczny")

    # Zraszanie
    mist_enabled = models.BooleanField(default=True)
    mist_mode = models.CharField(max_length=20, default='harmonogram',
                                 choices=[('harmonogram', 'Harmonogram'), ('auto', 'Auto')])
    mist_duration = models.IntegerField(default=10, help_text="Czas zraszania w sekundach")
    mist_min_humidity = models.IntegerField(default=60, verbose_name="Min Wilgotność %")

    # Harmonogram zraszania (opcjonalny)
    mist_h1 = models.TimeField(null=True, blank=True)
    mist_h2 = models.TimeField(null=True, blank=True)
    mist_h3 = models.TimeField(null=True, blank=True)
    mist_h4 = models.TimeField(null=True, blank=True)

    # Status Online
    last_seen = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False)

    # (Status LIVE z Tasmoty)

    is_heating = models.BooleanField(default=False)
    is_misting = models.BooleanField(default=False)
    is_lighting = models.BooleanField(default=False)

    # Mechanizm Ota online

    update_required = models.BooleanField(default=False,  verbose_name="Update OTA Required")

    @property
    def is_active(self):
        if not self.last_seen: return False
        return (timezone.now() - self.last_seen) < timedelta(seconds=30)




    def __str__(self):
        return f"{self.name} ({self.device_id})"


class Reading(models.Model):
    """
    Historia odczytów z sensorów.
    """
    terrarium = models.ForeignKey(Terrarium, on_delete=models.CASCADE, related_name='readings')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    # Pomiary
    temp = models.FloatField()
    hum = models.FloatField()

    # Stan urządzeń (Historia)
    # Tu zapiszemy to, co przyszło w 'heater_state' z ESP
    heater = models.BooleanField(default=False)
    mist = models.BooleanField(default=False)
    light = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['terrarium', 'timestamp'])]

    def __str__(self):
        return f"{self.terrarium.name} - {self.timestamp.strftime('%H:%M:%S')}"

# ... (HourlyReading zostaje bez zmian) ...
class HourlyReading(models.Model):
    terrarium = models.ForeignKey(Terrarium, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    avg_temp = models.DecimalField(max_digits=5, decimal_places=2)
    avg_hum = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        indexes = [models.Index(fields=['terrarium', 'timestamp'])]