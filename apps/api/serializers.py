# api/serializers.py
from rest_framework import serializers
from apps.core.models import Reading


class SensorDataSerializer(serializers.Serializer):
    # Pola, które przychodzą z ESP32 (z JSONa)
    temp = serializers.FloatField()
    hum = serializers.FloatField()

    # Opcjonalne pola stanów (gdyby stary soft ESP jeszcze działał)
    heater_state = serializers.BooleanField(required=False, default=False)
    mist_state = serializers.BooleanField(required=False, default=False)
    light_state = serializers.BooleanField(required=False, default=False)