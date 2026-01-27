import os
import json
import secrets
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
from django.db.models.functions import TruncHour
from django.db.models import Avg

from apps.core.models import Terrarium, Reading, AllowedDevice


def chart_data_view(request, device_id):
    """
    Zwraca dane pomiarowe z ostatnich 24h w formacie JSON dla wykresu Chart.js.
    """
    # 1. Zakres czasu: Ostatnie 24 godziny
    now = timezone.now()
    cutoff = now - timedelta(hours=24)

    # 2. Pobierz dane
    readings = Reading.objects.filter(
        terrarium__device_id=device_id,
        timestamp__gte=cutoff
    ).order_by('timestamp')

    # 3. Formatowanie danych
    data = {
        'labels': [r.timestamp.strftime("%H:%M") for r in readings],
        'temps': [float(r.temp) for r in readings],
        'hums': [float(r.hum) for r in readings]
    }
    return JsonResponse(data)


def download_firmware(request, filename):
    """
    Służy do pobierania pliku .bin przez ESP32 dla OTA.
    Adres: /api/firmware/esp32.bin
    """
    # Zabezpieczenie: Pozwól pobrać tylko konkretne pliki
    allowed_files = ['esp32.bin', 'esp8266.bin']

    if filename not in allowed_files:
        return HttpResponse("File not allowed", status=403)

    # Budujemy ścieżkę do pliku w folderze 'firmware' w głównym katalogu projektu
    # Upewnij się, że folder 'firmware' istnieje obok manage.py
    file_path = os.path.join(settings.BASE_DIR, 'firmware', filename)

    if os.path.exists(file_path):
        # Otwieramy plik w trybie binarnym (rb) i wysyłamy
        response = FileResponse(open(file_path, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    else:
        raise Http404("Firmware not found")


@method_decorator(csrf_exempt, name='dispatch')
class DeviceAuthView(View):

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

            if allowed.api_token:
                return JsonResponse({'token': allowed.api_token})
            else:
                return JsonResponse({'error': 'Token not generated in Admin'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class IoTUpdateView(View):
    """
    Główny punkt odbioru danych z ESP.
    Obsługuje: Autoryzację, Logikę sterowania, Alerty Email, Zapis do bazy.
    """

    def post(self, request):
        # 1. AUTORYZACJA (TOKEN)
        # Sprawdzamy nagłówek ALBO body (dla symulatora)
        auth_header = request.headers.get('Authorization')
        token = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            # Fallback: sprawdź body (dla symulatora, który wysyła token w JSON)
            try:
                body_data = json.loads(request.body)
                token = body_data.get('token')
            except:
                pass

        if not token:
            return JsonResponse({'error': 'Missing or Invalid Token'}, status=401)

        try:
            allowed = AllowedDevice.objects.get(api_token=token)
            dev_id = allowed.device_id
        except AllowedDevice.DoesNotExist:
            return JsonResponse({'error': 'Unauthorized: Invalid Token'}, status=401)

        try:
            # 2. DANE Z ESP
            try:
                data = json.loads(request.body)
            except JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON format'}, status=400)

            raw_temp = data.get('temp')
            raw_hum = data.get('hum')

            if raw_temp is None or raw_hum is None:
                return JsonResponse({'error': 'Missing required fields: temp, hum'}, status=400)

            try:
                temp = float(raw_temp)
                hum = float(raw_hum)
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Fields temp and hum must be numbers'}, status=400)

            # 3. POBRANIE URZĄDZENIA
            device, created = Terrarium.objects.get_or_create(
                device_id=dev_id,
                defaults={'name': f"Terrarium {dev_id}"}
            )

            # --- LOGIKA BIZNESOWA ---
            now = timezone.localtime()
            now_time = now.time()

            # A. ALERTY EMAIL
            if device.alerts_enabled and device.alert_email:
                cooldown = True
                if device.last_alert_sent and (timezone.now() - device.last_alert_sent < timedelta(minutes=15)):
                    cooldown = False

                if cooldown:
                    subject = ""
                    should_send = False
                    if temp > device.alert_max_temp:
                        should_send = True
                        subject = f"ALARM: {device.name} - Wysoka Temperatura!"
                        msg = f"Temperatura wzrosła do {temp}°C! (Limit: {device.alert_max_temp}°C)"
                    elif temp < device.alert_min_temp:
                        should_send = True
                        subject = f"ALARM: {device.name} - Niska Temperatura!"
                        msg = f"Temperatura spadła do {temp}°C! (Limit: {device.alert_min_temp}°C)"

                    if should_send:
                        try:
                            send_mail(subject, msg, 'system@animal.zipit.pl', [device.alert_email], fail_silently=True)
                            device.last_alert_sent = timezone.now()
                            device.save()
                        except:
                            pass

            # B. STEROWANIE
            # Światło
            if device.light_mode == 'manual':
                light_on = device.light_manual_state
                is_day = light_on
            else:
                if device.light_start <= device.light_end:
                    is_day = device.light_start <= now_time < device.light_end
                else:
                    is_day = now_time >= device.light_start or now_time < device.light_end
                light_on = is_day

            # Grzanie
            target_temp = device.temp_day if is_day else device.temp_night
            heater_on = temp < target_temp

            # Mgła
            mist_on = False
            if device.mist_enabled:
                if device.mist_mode == 'auto':
                    mist_on = hum < device.mist_min_humidity
                else:
                    current_hm = now_time.strftime("%H:%M")
                    timers = [device.mist_h1, device.mist_h2, device.mist_h3, device.mist_h4]
                    for t in timers:
                        if t and t.strftime("%H:%M") == current_hm:
                            mist_on = True

            # C. ZAPIS DO BAZY (NAPRAWIONE NAZWY PÓL)
            Reading.objects.create(
                terrarium=device,
                temp=temp,
                hum=hum,
                heater=heater_on,  # POPRAWNE: heater (zamiast is_heater_on)
                mist=mist_on,      # POPRAWNE: mist (zamiast is_mist_on)
                light=light_on     # POPRAWNE: light (zamiast is_light_on)
            )

            device.last_seen = now
            device.is_online = True
            device.save()

            # D. ODPOWIEDŹ
            return JsonResponse({
                'status': 'ok',
                'heater': heater_on,
                'mist': mist_on,
                'light': light_on,
                'screen': True,
                'name': device.name
            })

        except Exception as e:
            print(f"❌ API Error: {e}")
            return JsonResponse({'error': str(e)}, status=500)