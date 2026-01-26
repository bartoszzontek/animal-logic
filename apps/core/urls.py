from django.urls import path
from django.views.generic import TemplateView  # <--- WAŻNE: Dodaj ten import!
from . import views
from .views import account_settings

urlpatterns = [
    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('dashboard/<str:device_id>/', views.dashboard, name='dashboard'),
    path('dashboard/<str:device_id>/toggle-light/', views.toggle_light, name='toggle_light'),

    # Zarządzanie
    path('add/', views.add_device, name='add_device'),
    path('delete/<str:device_id>/', views.delete_device, name='delete_device'),

    # API Wykresów
    path('api/history/<str:period>/', views.history_data, name='history_data'),

    # --- PWA (POPRAWIONE) ---
    # Używamy TemplateView bezpośrednio tutaj, żeby nie babrać się w views.py
    path('manifest.json', TemplateView.as_view(
        template_name='manifest.json',
        content_type='application/json'  # To jest kluczowe dla Androida/Chrome!
    ), name='manifest'),

    path('sw.js', TemplateView.as_view(
        template_name='sw.js',
        content_type='application/javascript' # To jest kluczowe dla działania Workera!
    ), name='service_worker'),

    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),

    path('account/', account_settings, name='account_settings'),

    # Home
    path('', views.home, name='home'),
]