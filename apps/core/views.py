import json
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404, FileResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from datetime import timedelta

# Importuj modele z pliku models.py (nie definiuj ich tutaj!)
from .models import Terrarium, Reading, AllowedDevice
from .forms import RegisterForm, AddDeviceForm, TerrariumSettingsForm


# --- 1. AUTHENTICATION ---

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


# --- 2. DASHBOARD & URZĄDZENIA ---

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
        'settings': terrarium,
        'reading': reading,
        'is_day': is_day,
    })


@login_required
def switch_light_mode(request, device_id):
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    if device.light_mode == 'auto':
        device.light_mode = 'manual'
        device.light_manual_state = True
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
        messages.warning(request, "Włącz tryb ręczny!")
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


# --- 3. API (WYKRESY & PWA) ---

@login_required
def chart_data(request, device_id):
    device = get_object_or_404(Terrarium, device_id=device_id, owner=request.user)
    now = timezone.now()
    readings = Reading.objects.filter(terrarium=device, timestamp__gte=now - timedelta(hours=24)).order_by('timestamp')

    data_list = list(readings)
    if len(data_list) > 100:
        data_list = data_list[::len(data_list) // 100]

    return JsonResponse({
        'labels': [timezone.localtime(r.timestamp).strftime('%H:%M') for r in data_list],
        'temps': [r.temp for r in data_list],
        'hums': [r.hum for r in data_list]
    })


def manifest_view(request):
    return render(request, 'manifest.json', content_type='application/json')


def service_worker_view(request):
    return render(request, 'sw.js', content_type='application/javascript')


def offline_view(request):
    return render(request, 'offline.html')


# ==========================================
# 4. API DLA ESP32 (BEZPIECZNIKI WYŁĄCZONE)
# ==========================================

@csrf_exempt
def api_sensor_update(request):
    """Odbiera pomiary (POST)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        data = json.loads(request.body)
        dev_id = data.get('device_id')
        token = data.get('token')

        # Debug: Pokaż co przyszło (pomocne przy debugowaniu)
        # print(f"DEBUG VIEW: ID={dev_id}, Token={token}")

        try:
            allowed = AllowedDevice.objects.get(device_id=dev_id)
        except AllowedDevice.DoesNotExist:
            return JsonResponse({'error': f'Device {dev_id} not allowed'}, status=401)

        # Sprawdzenie tokena (konwersja na string dla bezpieczeństwa)
        if str(allowed.api_token).strip() != str(token).strip():
            return JsonResponse({'error': 'Invalid Token'}, status=401)

        # Logika zapisu...
        terrarium, _ = Terrarium.objects.get_or_create(device_id=dev_id)

        Reading.objects.create(
            terrarium=terrarium,
            temp=data.get('temp', 0),
            hum=data.get('hum', 0),
            # --- ODKOMENTOWANE I GOTOWE DO DZIAŁANIA ---
            heater=data.get('heater', False),
            light=data.get('light', False),
            mist=data.get('mist', False)
            # -------------------------------------------
        )

        # Aktualizacja 'ostatnio widziano'
        terrarium.last_seen = timezone.now()
        terrarium.is_online = True
        terrarium.save()

        return JsonResponse({"status": "ok"})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def api_device_auth(request):
    """Logowanie PINem (POST)."""
    if request.method != 'POST': return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body)
        allowed = AllowedDevice.objects.get(device_id=data.get('device_id'))

        if check_password(data.get('pin'), allowed.pin_hash):
            return JsonResponse({'status': 'authorized', 'token': allowed.api_token})

        return JsonResponse({'error': 'Wrong PIN'}, status=403)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=403)


@csrf_exempt
def download_firmware(request, filename):
    """Pobieranie pliku (GET)."""
    if not filename.endswith('.bin'): raise Http404

    fw_path = getattr(settings, 'FIRMWARE_ROOT', os.path.join(settings.BASE_DIR, 'firmware'))
    path = os.path.join(fw_path, filename)

    if os.path.exists(path):
        return FileResponse(open(path, 'rb'), content_type='application/octet-stream')

    raise Http404