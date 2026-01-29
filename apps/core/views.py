# apps/core/views.py
import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import Terrarium, Reading
from .forms import RegisterForm, AddDeviceForm, TerrariumSettingsForm


# ==========================================
# 1. UWIERZYTELNIANIE (Auth)
# ==========================================

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            if User.objects.filter(username=form.cleaned_data['username']).exists():
                messages.error(request, "Taki użytkownik już istnieje.")
            else:
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    email=form.cleaned_data.get('email', '')
                )
                login(request, user)
                return redirect('home')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


def login_view(request):
    if request.method == "POST":
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Błędne dane logowania")
    return render(request, 'login.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


# ==========================================
# 2. DASHBOARD & ZARZĄDZANIE (HTML)
# ==========================================

@login_required
def home(request):
    """Lista kafelków z terrariami"""
    devices = request.user.terrariums.all()
    return render(request, 'home.html', {'devices': devices})


@login_required
def add_device(request):
    if request.method == "POST":
        form = AddDeviceForm(request.POST)
        if form.is_valid():
            dev_id = form.cleaned_data['device_id']
            name = form.cleaned_data['name']
            # Tworzymy lub pobieramy, żeby przypisać usera
            device, created = Terrarium.objects.get_or_create(device_id=dev_id)
            device.owner = request.user
            device.name = name
            device.save()
            messages.success(request, "Urządzenie dodane pomyślnie!")
            return redirect('home')
    else:
        form = AddDeviceForm()
    return render(request, 'add_device.html', {'form': form})


@login_required
def delete_device(request, device_id):
    if request.method == "POST":
        device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
        device.owner = None  # Odpinamy usera, ale nie kasujemy danych historycznych
        device.save()
        messages.success(request, "Urządzenie usunięte z konta.")
    return redirect('home')


@login_required
def dashboard(request, device_id):
    """Główny panel sterowania terrarium"""
    terrarium = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)

    if request.method == "POST":
        form = TerrariumSettingsForm(request.POST, instance=terrarium)
        if form.is_valid():
            form.save()
            messages.success(request, "Ustawienia zapisane.")
            return redirect('dashboard', device_id=device_id)

    # Pobieramy ostatni odczyt
    reading = Reading.objects.filter(terrarium=terrarium).order_by('-timestamp').first()

    # Sprawdzamy czy jest "dzień" wg ustawień (do wyświetlania słoneczka/księżyca)
    now = timezone.localtime().time()
    is_day = False
    if terrarium.light_mode == 'manual':
        is_day = terrarium.light_manual_state
    else:
        start = terrarium.light_start
        end = terrarium.light_end
        if start < end:
            is_day = start <= now < end
        else:
            is_day = now >= start or now < end

    return render(request, 'dashboard.html', {
        'settings': terrarium,  # Tutaj są pola is_heating, is_online itd.
        'reading': reading,  # Tutaj są ostatnie temperatury
        'is_day': is_day,
    })


@login_required
def switch_light_mode(request, device_id):
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    if device.light_mode == 'auto':
        device.light_mode = 'manual'
        # Przy przejściu na manual, przyjmij obecny stan
        # (Można tu dodać logikę pobierania aktualnego stanu)
        msg = "Tryb RĘCZNY."
    else:
        device.light_mode = 'auto'
        msg = "Tryb AUTO."
    device.save()
    messages.info(request, msg)
    return redirect('dashboard', device_id=device_id)


@login_required
def toggle_light_state(request, device_id):
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    if device.light_mode == 'manual':
        device.light_manual_state = not device.light_manual_state
        device.save()
        messages.success(request, "Przełączono światło.")
    else:
        messages.warning(request, "Włącz najpierw tryb ręczny!")
    return redirect('dashboard', device_id=device_id)


@login_required
def account_settings(request):
    if request.method == "POST":
        email = request.POST.get('email')
        if email:
            request.user.email = email
            request.user.save()
            messages.success(request, "Email zapisany.")
        return redirect('account_settings')
    return render(request, 'account_settings.html', {'user': request.user})


# ==========================================
# 3. API FRONTENDOWE (AJAX / PWA)
# ==========================================

def manifest_view(request):
    return render(request, 'manifest.json', content_type='application/json')


def service_worker_view(request):
    return render(request, 'sw.js', content_type='application/javascript')


def offline_view(request):
    return render(request, 'offline.html')


@login_required
def chart_data(request, device_id):
    """Dane do wykresu Chart.js"""
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    now = timezone.now()
    readings = Reading.objects.filter(terrarium=device, timestamp__gte=now - timedelta(hours=24)).order_by('timestamp')

    # Optymalizacja: jeśli jest za dużo punktów, bierzemy co któryś (downsampling)
    data_list = list(readings)
    if len(data_list) > 200:
        data_list = data_list[::len(data_list) // 200]

    return JsonResponse({
        'labels': [timezone.localtime(r.timestamp).strftime('%H:%M') for r in data_list],
        'temps': [r.temp for r in data_list],
        'hums': [r.hum for r in data_list],
        # Opcjonalnie: stany grzania na wykresie
        'heaters': [1 if r.heater else 0 for r in data_list]
    })


@login_required
def api_get_latest_data(request, device_id):
    """
    To odpytuje Dashboard co 5 sekund, żeby zaktualizować kropki statusu bez odświeżania strony.
    Korzystamy z nowych pól 'LIVE' w modelu Terrarium.
    """
    terrarium = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)

    # Pobieramy też ostatni odczyt temperatury
    reading = Reading.objects.filter(terrarium=terrarium).order_by('-timestamp').first()

    response_data = {
        'online': terrarium.is_active,  # Czy ESP nadało sygnał < 60s temu
        'heater': terrarium.is_heating,
        'mist': terrarium.is_misting,
        'light': terrarium.is_lighting,
    }

    if reading:
        response_data['temp'] = reading.temp
        response_data['hum'] = reading.hum
        response_data['last_seen'] = timezone.localtime(reading.timestamp).strftime('%H:%M:%S')
    else:
        response_data['temp'] = '--'
        response_data['hum'] = '--'
        response_data['last_seen'] = 'Brak danych'

    return JsonResponse(response_data)