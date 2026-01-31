import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Terrarium, Reading
from .forms import RegisterForm, AddDeviceForm, TerrariumSettingsForm

from apps.api.views import IoTUpdateView, DeviceAuthView, download_firmware as api_fw
api_sensor_update = csrf_exempt(IoTUpdateView.as_view())
api_device_auth = csrf_exempt(DeviceAuthView.as_view())
download_firmware = api_fw

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

# NAPRAWA 1: Brak @login_required tutaj!
def home(request):
    if request.user.is_authenticated:
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
    terrarium = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    if request.method == "POST":
        form = TerrariumSettingsForm(request.POST, instance=terrarium)
        if form.is_valid():
            form.save()
            messages.success(request, "Ustawienia zapisane.")
            return redirect('dashboard', device_id=device_id)

    reading = Reading.objects.filter(terrarium=terrarium).order_by('-timestamp').first()
    now = timezone.localtime().time()
    is_day = False
    if terrarium.light_mode == 'manual':
        is_day = terrarium.light_manual_state
    else:
        if terrarium.light_start and terrarium.light_end:
            start = terrarium.light_start
            end = terrarium.light_end
            if start < end:
                is_day = start <= now < end
            else:
                is_day = now >= start or now < end

    return render(request, 'dashboard.html', {
        'settings': terrarium, 'reading': reading, 'is_day': is_day,
    })

@login_required
def switch_light_mode(request, device_id):
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    if device.light_mode == 'auto':
        device.light_mode = 'manual'
        device.light_manual_state = True # NAPRAWA 2: Ustawiamy na True przy przejściu
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

def manifest_view(request): return render(request, 'manifest.json', content_type='application/json')
def service_worker_view(request): return render(request, 'sw.js', content_type='application/javascript')
def offline_view(request): return render(request, 'offline.html')

@login_required
def chart_data(request, device_id):
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    now = timezone.now()
    readings = Reading.objects.filter(terrarium=device, timestamp__gte=now - timedelta(hours=24)).order_by('timestamp')
    data_list = list(readings)
    if len(data_list) > 200: data_list = data_list[::len(data_list) // 200]
    return JsonResponse({
        'labels': [timezone.localtime(r.timestamp).strftime('%H:%M') for r in data_list],
        'temps': [r.temp for r in data_list],
        'hums': [r.hum for r in data_list],
        'heaters': [1 if r.heater else 0 for r in data_list]
    })

@login_required
def api_get_latest_data(request, device_id):
    terrarium = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    reading = Reading.objects.filter(terrarium=terrarium).order_by('-timestamp').first()
    response_data = {
        'online': terrarium.is_active,
        'heater': terrarium.is_heating,
        'mist': terrarium.is_misting,
        'light': terrarium.is_lighting,
    }
    if reading:
        response_data['temp'] = reading.temp
        response_data['hum'] = reading.hum
        response_data['last_seen'] = timezone.localtime(reading.timestamp).strftime('%d.%m.%Y %H:%M:%S')
    else:
        response_data['temp'] = '--'; response_data['hum'] = '--'; response_data['last_seen'] = 'Brak danych'
    return JsonResponse(response_data)

@login_required
def trigger_ota_update(request, device_id):
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    if request.method == "POST":
        device.update_required = True
        device.save()
        messages.success(request, f"Zlecono aktualizacje dla {device.name}. Czekam na połączenie... ")

    return redirect('dashboard', device_id=device_id)
