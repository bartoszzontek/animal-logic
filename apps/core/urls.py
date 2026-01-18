from django.urls import path
from . import views

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

    # --- PWA (TEGO BRAKOWAŁO) ---
    path('manifest.json', views.manifest_view, name='manifest'),
    path('sw.js', views.service_worker_view, name='service_worker'),
    path('offline/', views.offline_view, name='offline'),

    # Home
    path('', views.home, name='home'),
]