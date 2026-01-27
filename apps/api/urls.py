# apps/api/urls.py
from django.urls import path
from .views import (
    IoTUpdateView,
    DeviceAuthView,
    chart_data_view,
    download_firmware
)

urlpatterns = [
    # Główny endpoint dla ESP (wysyłanie pomiarów)
    # ZMIANA: name='sensor_update' -> name='api_sensor_update' (żeby testy przeszły)
    path('sensor/update', IoTUpdateView.as_view(), name='api_sensor_update'),

    # Endpoint do pobierania danych na wykres
    path('chart/<str:device_id>/', chart_data_view, name='chart_data'),

    # Endpoint do aktualizacji OTA
    path('firmware/<str:filename>', download_firmware, name='download_firmware'),

    # Autoryzacja PINem
    path('auth/device', DeviceAuthView.as_view(), name='api_device_auth'),
]