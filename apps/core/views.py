from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse  # <--- WAŻNE: Dodano HttpResponse
from django.utils import timezone
from datetime import timedelta
import datetime
from .models import Terrarium, Reading, AllowedDevice
from .forms import RegisterForm, AddDeviceForm, TerrariumSettingsForm


# --- AUTH ---

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
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


# --- DASHBOARD & HOME ---

# apps/core/views.py

def home(request):
    # Jeśli użytkownik jest zalogowany -> Pokaż mu jego terraria
    if request.user.is_authenticated:
        # Pobieramy urządzenia przypisane do użytkownika (z modelu Terrarium)
        devices = request.user.terrariums.all()
    else:
        # Jeśli nie jest zalogowany -> Pusta lista (wyświetlimy Landing Page w HTML)
        devices = []

    return render(request, 'home.html', {'devices': devices})
@login_required
def add_device(request):
    if request.method == "POST":
        form = AddDeviceForm(request.POST)
        if form.is_valid():
            dev_id = form.cleaned_data['device_id']
            name = form.cleaned_data['name']
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
        device.owner = None
        device.save()
        messages.success(request, "Urządzenie usunięte z konta.")
    return redirect('home')


@login_required
def dashboard(request, device_id):
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)

    if request.method == "POST":
        form = TerrariumSettingsForm(request.POST, instance=device)
        if form.is_valid():
            form.save()
            messages.success(request, "Ustawienia zapisane!")
            return redirect('dashboard', device_id=device_id)
        else:
            print(f"❌ BŁĄD FORMULARZA DLA {device_id}:", form.errors)
            messages.error(request, "Błąd zapisu. Sprawdź poprawność danych.")

    last_reading = device.readings.first()
    if not last_reading:
        last_reading = {'temp': 0, 'hum': 0, 'timestamp': timezone.now(),
                        'is_heater_on': False, 'is_mist_on': False, 'is_light_on': False}

    features = {
        'heater': True,
        'mist': device.device_id.startswith(('A', 'B')),
        'light': device.device_id.startswith(('A', 'D'))
    }

    return render(request, 'dashboard.html', {
        'settings': device,
        'reading': last_reading,
        'features': features,
        'user': request.user
    })


@login_required
def toggle_light(request, device_id):
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    if device.light_mode == 'auto':
        device.light_mode = 'manual'
        device.light_manual_state = True
        msg = "Przełączono na tryb RĘCZNY: Światło WŁĄCZONE."
    else:
        device.light_manual_state = not device.light_manual_state
        state_txt = "WŁĄCZONE" if device.light_manual_state else "WYŁĄCZONE"
        msg = f"Światło {state_txt} (Tryb Ręczny)."
    device.save()
    messages.info(request, msg)
    return redirect('dashboard', device_id=device_id)


@login_required
def history_data(request, period):
    dev_id = request.GET.get('id')
    device = get_object_or_404(Terrarium, device_id=dev_id, owner=request.user)
    now = timezone.now()
    if period == 'day':
        delta, limit = timedelta(hours=24), 48
    elif period == 'week':
        delta, limit = timedelta(days=7), 100
    else:
        delta, limit = timedelta(days=30), 100
    readings = Reading.objects.filter(terrarium=device, timestamp__gte=now - delta).order_by('timestamp')
    data_list = list(readings.values('timestamp', 'temp', 'hum'))
    if len(data_list) > limit:
        step = len(data_list) // limit
        data_list = data_list[::step]
    labels = []
    temps = []
    hums = []
    for r in data_list:
        local_time = timezone.localtime(r['timestamp'])
        if period == 'day':
            labels.append(local_time.strftime('%H:%M'))
        else:
            labels.append(local_time.strftime('%d.%m'))
        temps.append(r['temp'])
        hums.append(r['hum'])
    return JsonResponse({'labels': labels, 'temps': temps, 'hums': hums})

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
        # Prosta walidacja i zapis
        if email:
            request.user.email = email
            request.user.save()
            messages.success(request, "Adres email został zaktualizowany.")
        else:
            messages.error(request, "Podaj poprawny adres email.")
        return redirect('account_settings')

    return render(request, 'account_settings.html', {'user': request.user})