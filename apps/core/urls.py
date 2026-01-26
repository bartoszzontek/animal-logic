from django.urls import path
from . import views

urlpatterns = [
    # --- AUTH ---
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # --- HOME & URZĄDZENIA ---
    path('', views.home, name='home'),
    path('add/', views.add_device, name='add_device'),
    path('delete/<str:device_id>/', views.delete_device, name='delete_device'),

    # --- DASHBOARD & STEROWANIE ---
    path('dashboard/<str:device_id>/', views.dashboard, name='dashboard'),

    # --- NOWE STEROWANIE ŚWIATŁEM (Poprawka błędu) ---
    # Zamiast starego toggle_light, mamy teraz dwie ścieżki:
    path('mode-light/<str:device_id>/', views.switch_light_mode, name='switch_light_mode'),  # Zmiana Auto/Manual
    path('toggle-light/<str:device_id>/', views.toggle_light_state, name='toggle_light_state'),
    # Włącz/Wyłącz (tylko manual)

    # --- API (WYKRESY) ---
    path('api/chart/<str:device_id>/', views.chart_data, name='chart_data'),

    # --- USTAWIENIA KONTA ---
    path('account/', views.account_settings, name='account_settings'),

    # --- PWA (Offline & Mobile) ---
    path('manifest.json', views.manifest_view, name='manifest'),
    path('sw.js', views.service_worker_view, name='service_worker'),
    path('offline/', views.offline_view, name='offline'),
]