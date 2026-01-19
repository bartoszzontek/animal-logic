from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime
from datetime import timedelta
import secrets
from django.db import models

class AllowedDevice(models.Model):
    device_id = models.CharField(max_length=50, unique=True)
    pin_hash = models.CharField(max_length=128)
    api_token = models.CharField(max_length=64, blank=True, null=True, unique=True)

    def save(self, *args, **kwargs):
        if not self.api_token:
            self.api_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        # ZABEZPIECZENIE: Jeśli token istnieje, skracamy go. Jeśli nie, piszemy "BRAK".
        token_str = self.api_token[:10] if self.api_token else "BRAK"
        return f"{self.device_id} (Token: {token_str}...)"


class Terrarium(models.Model):
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='terrariums')
    device_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100, default="Moje Terrarium")
    api_token = models.CharField(max_length=64, blank=True, null=True, unique=True, db_index=True)

    # Termostat
    temp_day = models.FloatField(default=28.0, verbose_name="Temp. Dzień")
    temp_night = models.FloatField(default=22.0, verbose_name="Temp. Noc")

    # --- ALERTY ---
    alerts_enabled = models.BooleanField(default=True, verbose_name="Alerty Email włączone")
    # NOWE POLE:
    alert_email = models.EmailField(max_length=254, blank=True, null=True, verbose_name="Email do powiadomień")
    alert_min_temp = models.FloatField(default=18.0, verbose_name="Alarm Min Temp")
    alert_max_temp = models.FloatField(default=35.0, verbose_name="Alarm Max Temp")
    last_alert_sent = models.DateTimeField(null=True, blank=True)

    # Cykl Dnia
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
    mist_h1 = models.TimeField(null=True, blank=True)
    mist_h2 = models.TimeField(null=True, blank=True)
    mist_h3 = models.TimeField(null=True, blank=True)
    mist_h4 = models.TimeField(null=True, blank=True)

    last_seen = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False)

    @property
    def is_active(self):
        if not self.last_seen: return False
        return (timezone.now() - self.last_seen) < timedelta(seconds=30)

    def __str__(self):
        return f"{self.name} ({self.device_id})"


class Reading(models.Model):
    terrarium = models.ForeignKey(Terrarium, on_delete=models.CASCADE, related_name='readings')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    temp = models.FloatField()
    hum = models.FloatField()
    is_heater_on = models.BooleanField(default=False)
    is_mist_on = models.BooleanField(default=False)
    is_light_on = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['terrarium', 'timestamp'])]