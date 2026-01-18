from django.urls import path
from .views import IoTUpdateView, DeviceAuthView

urlpatterns = [
    path('auth', DeviceAuthView.as_view(), name='device_auth'),
    path('sensor/update', IoTUpdateView.as_view(), name='sensor_update'),
]