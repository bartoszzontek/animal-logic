from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import timedelta
import datetime

from .models import Terrarium, Reading
from .forms import RegisterForm, AddDeviceForm, TerrariumSettingsForm


# --- AUTHENTICATION ---

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            # Sprawdzenie czy user/email już istnieje
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


# --- HOME & DEVICES ---

def home(request):
    if request.user.is_authenticated:
        # Pobieramy urządzenia przypisane do użytkownika
        devices = request.user.terrariums.all()
    else:
        devices = []
    return render(request, 'home.html', {'devices': devices})


@login_required
def add_device(request):
    if request.method == "POST":
        form = AddDeviceForm(request.POST)
        if form.is_valid():
            dev_id = form.cleaned_data['device_id']
            pin = form.cleaned_data['pin']
            name = form.cleaned_data['name']

            # 1. Sprawdź czy PIN się zgadza w AllowedDevice
            # (Tutaj zakładamy uproszczoną wersję z Twojego kodu,
            #  normalnie sprawdzalibyśmy model AllowedDevice)

            # 2. Przypisz lub stwórz urządzenie
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
        device.owner = None  # Odpinamy usera, nie usuwamy rekordu z bazy
        device.save()
        messages.success(request, "Urządzenie usunięte z konta.")
    return redirect('home')


# --- DASHBOARD & CONTROL ---

@login_required
def dashboard(request, device_id):
    terrarium = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)

    # OBSŁUGA FORMULARZA USTAWIEŃ (POST)
    if request.method == "POST":
        form = TerrariumSettingsForm(request.POST, instance=terrarium)
        if form.is_valid():
            form.save()
            messages.success(request, "Ustawienia zapisane pomyślnie.")
            return redirect('dashboard', device_id=device_id)
        else:
            messages.error(request, "Błąd zapisu ustawień. Sprawdź formularz.")

    # POBIERANIE DANYCH DO WYŚWIETLENIA (GET)
    reading = Reading.objects.filter(terrarium=terrarium).order_by('-timestamp').first()

    # --- LOGIKA DZIEŃ / NOC ---
    now = timezone.localtime().time()

    if terrarium.light_mode == 'manual':
        # Priorytet manuala: Jeśli ręcznie włączone -> Dzień. Wyłączone -> Noc.
        is_day = terrarium.light_manual_state
    else:
        # Tryb Auto (Zegar)
        start = terrarium.light_start
        end = terrarium.light_end

        if start < end:
            is_day = start <= now < end
        else:
            is_day = now >= start or now < end

    # Debug w konsoli
    print(f"DASHBOARD STATUS: Godzina={now}, Tryb={terrarium.light_mode}, IS_DAY={is_day}")

    context = {
        'settings': terrarium,
        'reading': reading,
        'is_day': is_day,
    }
    return render(request, 'dashboard.html', context)


# apps/core/views.py

@login_required
def switch_light_mode(request, device_id):
    """Przełącza tylko tryb: Auto <-> Manual"""
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)

    if device.light_mode == 'auto':
        device.light_mode = 'manual'
        # Przy przejściu na manual, zachowaj obecny stan światła (żeby nie mrugało)
        # albo domyślnie włącz. Tutaj np. zostawiamy domyślnie włączone dla wygody.
        device.light_manual_state = True
        msg = "Tryb RĘCZNY aktywowany."
    else:
        device.light_mode = 'auto'
        msg = "Tryb AUTOMATYCZNY aktywowany."

    device.save()
    messages.info(request, msg)
    return redirect('dashboard', device_id=device_id)


@login_required
def toggle_light_state(request, device_id):
    """Włącza/Wyłącza światło (tylko w trybie Manual)"""
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)

    if device.light_mode == 'manual':
        device.light_manual_state = not device.light_manual_state
        device.save()
        state = "WŁĄCZONE" if device.light_manual_state else "WYŁĄCZONE"
        messages.success(request, f"Światło zostało {state}.")
    else:
        messages.warning(request, "Najpierw przełącz na tryb Ręczny!")

    return redirect('dashboard', device_id=device_id)
# --- API & DATA ---

@login_required
def chart_data(request, device_id):
    """API dla wykresu w Dashboardzie"""
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)

    # Pobierz dane z ostatnich 24h
    now = timezone.now()
    yesterday = now - timedelta(hours=24)
    readings = Reading.objects.filter(terrarium=device, timestamp__gte=yesterday).order_by('timestamp')

    # Optymalizacja: Jeśli danych jest za dużo (>100), cofnij co N-ty
    data_list = list(readings)
    if len(data_list) > 100:
        step = len(data_list) // 100
        data_list = data_list[::step]

    labels = []
    temps = []
    hums = []

    for r in data_list:
        local_time = timezone.localtime(r.timestamp)
        labels.append(local_time.strftime('%H:%M'))
        temps.append(r.temp)
        hums.append(r.hum)

    return JsonResponse({'labels': labels, 'temps': temps, 'hums': hums})


# --- PWA & ACCOUNT ---

def manifest_view(request):
    return render(request, 'manifest.json', content_type='application/json')


def service_worker_view(request):
    return render(request, 'sw.js', content_type='application/javascript')


def offline_view(request):
    return render(request, 'offline.html')


@login_required
def account_settings(request):
    if request.method == "POST":
        email = request.POST.get('email')
        if email:
            request.user.email = email
            request.user.save()
            messages.success(request, "Adres email został zaktualizowany.")
        else:
            messages.error(request, "Podaj poprawny adres email.")
        return redirect('account_settings')

    return render(request, 'account_settings.html', {'user': request.user})