from django.urls import path
from .views import (
    IoTUpdateView,
    DeviceAuthView,
    chart_data_view,
    download_firmware
)

urlpatterns = [
    # Główny endpoint dla ESP (wysyłanie pomiarów)
    path('sensor/update', IoTUpdateView.as_view(), name='sensor_update'),

    # Endpoint do pobierania danych na wykres (Frontend)
    path('chart/<str:device_id>/', chart_data_view, name='chart_data'),

    # Endpoint do aktualizacji OTA (pobieranie pliku .bin)
    path('firmware/<str:filename>', download_firmware, name='firmware_download'),

    # Opcjonalne: autoryzacja PINem (jeśli będziesz tego używać)
    path('auth/device', DeviceAuthView.as_view(), name='device_auth'),
]