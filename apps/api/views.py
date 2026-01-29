import os
import json
from datetime import timedelta
from json import JSONDecodeError

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views import View
from django.http import JsonResponse, FileResponse, Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from django.core.mail import send_mail

# Importujemy Twoje modele
from apps.core.models import Terrarium, Reading, AllowedDevice


# -------------------------------------------------------------------------
# 1. Wykresy (Chart.js)
# -------------------------------------------------------------------------
def chart_data_view(request, device_id):
    """
    Zwraca dane pomiarowe z ostatnich 24h w formacie JSON dla wykresu.
    """
    now = timezone.now()
    cutoff = now - timedelta(hours=24)

    # Pobieramy historię
    readings = Reading.objects.filter(
        terrarium__device_id=device_id,
        timestamp__gte=cutoff
    ).order_by('timestamp')

    # Formatujemy dane dla frontendu
    data = {
        'labels': [r.timestamp.strftime("%H:%M") for r in readings],
        'temps': [float(r.temp) for r in readings],
        'hums': [float(r.hum) for r in readings],
        # Opcjonalnie: historia grzania na wykresie (0 lub 1)
        'heaters': [1 if r.heater else 0 for r in readings]
    }
    return JsonResponse(data)


# -------------------------------------------------------------------------
# 2. Pobieranie Firmware (OTA)
# -------------------------------------------------------------------------
def download_firmware(request, filename):
    """
    Służy do pobierania pliku .bin przez ESP32.
    Adres: /api/firmware/esp32.bin
    """
    allowed_files = ['esp32.bin', 'esp8266.bin']
    if filename not in allowed_files:
        return HttpResponse("File not allowed", status=403)

    file_path = os.path.join(settings.BASE_DIR, 'firmware', filename)

    if os.path.exists(file_path):
        response = FileResponse(open(file_path, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    else:
        raise Http404("Firmware not found")


# -------------------------------------------------------------------------
# 3. Autoryzacja Urządzenia (Logowanie)
# -------------------------------------------------------------------------
@method_decorator(csrf_exempt, name='dispatch')
class DeviceAuthView(View):
    """
    Endpoint: /api/auth/device
    Przyjmuje: {"id": "A1001", "pin": "1234"}
    Zwraca: {"token": "..."}
    """

    def post(self, request):
        try:
            data = json.loads(request.body)
            dev_id = data.get('id')
            pin = data.get('pin')

            try:
                allowed = AllowedDevice.objects.get(device_id=dev_id)
            except AllowedDevice.DoesNotExist:
                return JsonResponse({'error': 'Device not allowed'}, status=403)

            if not check_password(str(pin), allowed.pin_hash):
                return JsonResponse({'error': 'Invalid PIN'}, status=403)

            # Jeśli tokena nie ma, wygeneruj go w locie
            if not allowed.api_token:
                allowed.save()  # save() w modelu AllowedDevice generuje token

            return JsonResponse({'token': allowed.api_token})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


# -------------------------------------------------------------------------
# 4. Główna Pętla Sterowania (IoT Loop)
# -------------------------------------------------------------------------
@method_decorator(csrf_exempt, name='dispatch')
class IoTUpdateView(View):
    """
    Endpoint: /api/sensor/update
    Przyjmuje: Dane z ESP32 (temp, hum, stany)
    Zwraca: Rozkazy dla ESP32 (grzej, świeć, zraszaj)
    """

    def post(self, request):
        # --- A. SPRAWDZENIE TOKENA ---
        auth_header = request.headers.get('Authorization')
        token = None

        # 1. Sprawdź nagłówek (ESP32)
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            # 2. Fallback: Sprawdź body (Symulator)
            try:
                body_data = json.loads(request.body)
                token = body_data.get('token')
            except:
                pass

        if not token:
            return JsonResponse({'error': 'Missing Token'}, status=401)

        # Znajdź urządzenie po tokenie
        try:
            allowed = AllowedDevice.objects.get(api_token=token)
            dev_id = allowed.device_id
        except AllowedDevice.DoesNotExist:
            return JsonResponse({'error': 'Invalid Token'}, status=401)

        try:
            # --- B. ODCZYT DANYCH Z JSON ---
            try:
                data = json.loads(request.body)
            except JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)

            # Wartości pomiarowe
            raw_temp = data.get('temp')
            raw_hum = data.get('hum')

            if raw_temp is None or raw_hum is None:
                return JsonResponse({'error': 'Missing temp/hum'}, status=400)

            try:
                temp = float(raw_temp)
                hum = float(raw_hum)
            except ValueError:
                return JsonResponse({'error': 'Temp/Hum must be numbers'}, status=400)

            # --- C. FEEDBACK (Rzeczywiste stany z ESP) ---
            # Odczytujemy, co ESP32 faktycznie robi (feedback loop)
            # Używamy .get(..., False) dla bezpieczeństwa
            real_heat = data.get('heater_state', False)
            real_mist = data.get('mist_state', False)
            real_light = data.get('light_state', False)

            # --- D. POBRANIE I AKTUALIZACJA TERRARIUM ---
            device, created = Terrarium.objects.get_or_create(
                device_id=dev_id,
                defaults={'name': f"Terrarium {dev_id}"}
            )

            # Aktualizujemy status "na żywo" (żeby ikonki na Dashboardzie były prawdziwe)
            device.last_seen = timezone.now()
            device.is_online = True

            # WAŻNE: Te pola musisz mieć w models.py (dodałeś je w poprzednim kroku?)
            # Jeśli nie zrobisz migracji, tu wywali błąd!
            device.is_heating = real_heat
            device.is_misting = real_mist
            device.is_lighting = real_light
            device.save()

            # --- E. ZAPIS HISTORII ---
            Reading.objects.create(
                terrarium=device,
                temp=temp,
                hum=hum,
                heater=real_heat,  # Zapisujemy prawdę, a nie rozkaz
                mist=real_mist,
                light=real_light
            )

            # --- F. LOGIKA STEROWANIA (MÓZG) ---
            now = timezone.localtime()
            now_time = now.time()

            # 1. ŚWIATŁO
            cmd_light = False
            if device.light_mode == 'manual':
                cmd_light = device.light_manual_state
            else:
                # Obsługa północy (np. start 22:00, koniec 06:00)
                if device.light_start <= device.light_end:
                    is_day = device.light_start <= now_time < device.light_end
                else:
                    is_day = now_time >= device.light_start or now_time < device.light_end
                cmd_light = is_day

            # 2. GRZANIE (Histereza)
            target_temp = device.temp_day if cmd_light else device.temp_night
            hysteresis = 0.5

            cmd_heat = False
            if temp < (target_temp - hysteresis):
                cmd_heat = True  # Zimno -> Grzej
            elif temp > target_temp:
                cmd_heat = False  # Ciepło -> Stop
            else:
                # Strefa martwa (Deadband) - utrzymujemy obecny stan
                cmd_heat = real_heat

                # 3. ZRASZANIE (Prosta logika wilgotności)
            cmd_mist = False
            if device.mist_enabled:
                if device.mist_mode == 'auto':
                    if hum < device.mist_min_humidity:
                        cmd_mist = True
                    elif hum > (device.mist_min_humidity + 5):
                        cmd_mist = False
                    else:
                        cmd_mist = real_mist
                else:
                    # Harmonogram (sprawdza czy minuta się zgadza)
                    current_hm = now_time.strftime("%H:%M")
                    timers = [device.mist_h1, device.mist_h2, device.mist_h3, device.mist_h4]
                    for t in timers:
                        if t and t.strftime("%H:%M") == current_hm:
                            cmd_mist = True

            # --- G. ALERTY EMAIL ---
            if device.alerts_enabled and device.alert_email:
                cooldown = True
                if device.last_alert_sent and (timezone.now() - device.last_alert_sent < timedelta(minutes=15)):
                    cooldown = False

                if cooldown:
                    if temp > device.alert_max_temp or temp < device.alert_min_temp:
                        try:
                            msg = f"Alarm temperatury: {temp}°C w {device.name}"
                            send_mail("ALARM TERRA", msg, 'system@animal.zipit.pl', [device.alert_email],
                                      fail_silently=True)
                            device.last_alert_sent = timezone.now()
                            device.save()
                        except:
                            pass

            # --- H. ODPOWIEDŹ DLA ESP32 ---
            return JsonResponse({
                'status': 'ok',
                'heater': cmd_heat,  # Rozkaz
                'mist': cmd_mist,  # Rozkaz
                'light': cmd_light,  # Rozkaz
                'target': target_temp,
                'name': device.name
            })

        except Exception as e:
            print(f"❌ API Error: {e}")
            return JsonResponse({'error': str(e)}, status=500)