# apps/core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # --- Auth (Logowanie/Rejestracja) ---
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # --- Home & Core (Dashboard) ---
    path('', views.home, name='home'),
    path('add/', views.add_device, name='add_device'),
    path('delete/<str:device_id>/', views.delete_device, name='delete_device'),
    path('dashboard/<str:device_id>/', views.dashboard, name='dashboard'),
    path('account/', views.account_settings, name='account_settings'),

    # --- Controls (Przyciski na stronie) ---
    path('mode-light/<str:device_id>/', views.switch_light_mode, name='switch_light_mode'),
    path('toggle-light/<str:device_id>/', views.toggle_light_state, name='toggle_light_state'),

    # --- AJAX (Tylko dla odświeżania Dashboardu w przeglądarce) ---
    # Zostawiamy to tutaj, bo funkcja api_get_latest_data jest w core/views.py
    path('api/status/<str:device_id>/', views.api_get_latest_data, name='api_get_latest_data'),

    # --- PWA (Aplikacja mobilna) ---
    path('manifest.json', views.manifest_view, name='manifest'),
    path('sw.js', views.service_worker_view, name='service_worker'),
    path('offline/', views.offline_view, name='offline'),

    path('dashboard/<str:device_id>/update/', views.trigger_ota_update, name='trigger_ota'),
]