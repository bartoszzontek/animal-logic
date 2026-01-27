from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Home & Core
    path('', views.home, name='home'),
    path('add/', views.add_device, name='add_device'),
    path('delete/<str:device_id>/', views.delete_device, name='delete_device'),
    path('dashboard/<str:device_id>/', views.dashboard, name='dashboard'),
    path('account/', views.account_settings, name='account_settings'),

    # Controls
    path('mode-light/<str:device_id>/', views.switch_light_mode, name='switch_light_mode'),
    path('toggle-light/<str:device_id>/', views.toggle_light_state, name='toggle_light_state'),

    # API
    path('api/chart/<str:device_id>/', views.chart_data, name='chart_data'),
    path('api/sensor/update', views.api_sensor_update, name='sensor_update'),
    path('api/auth/device', views.api_device_auth, name='device_auth'),
    path('api/firmware/<str:filename>', views.download_firmware, name='firmware_download'),
    path('api/status/<str:device_id>/', views.api_get_latest_data, name='api_get_latest_data'),

    # PWA
    path('manifest.json', views.manifest_view, name='manifest'),
    path('sw.js', views.service_worker_view, name='service_worker'),
    path('offline/', views.offline_view, name='offline'),
]