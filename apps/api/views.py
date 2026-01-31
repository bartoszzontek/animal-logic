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

from apps.core.models import Terrarium, Reading, AllowedDevice


# -------------------------------------------------------------------------
# 1. Wykresy (Chart.js)
# -------------------------------------------------------------------------
def chart_data_view(request, device_id):
    now = timezone.now()
    cutoff = now - timedelta(hours=24)
    readings = Reading.objects.filter(
        terrarium__device_id=device_id,
        timestamp__gte=cutoff
    ).order_by('timestamp')

    data = {
        'labels': [r.timestamp.strftime("%H:%M") for r in readings],
        'temps': [float(r.temp) for r in readings],
        'hums': [float(r.hum) for r in readings],
        'heaters': [1 if r.heater else 0 for r in readings]
    }
    return JsonResponse(data)


# -------------------------------------------------------------------------
# 2. Pobieranie Firmware (OTA)
# -------------------------------------------------------------------------
def download_firmware(request, filename):
    allowed_files = ['esp32.bin', 'esp8266.bin']

    # NAPRAWA: Jeśli plik nie jest na liście, udajemy że go nie ma (404)
    # zamiast krzyczeć "Zabronione" (403). To naprawia test.
    if filename not in allowed_files:
        raise Http404("Firmware not found")  # Było HttpResponse(..., 403)

    file_path = os.path.join(settings.BASE_DIR, 'firmware', filename)

    if os.path.exists(file_path):
        response = FileResponse(open(file_path, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    else:
        raise Http404("Firmware not found")


# -------------------------------------------------------------------------
# 3. Autoryzacja Urządzenia
# -------------------------------------------------------------------------
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

            if not allowed.api_token:
                allowed.save()

            return JsonResponse({'token': allowed.api_token})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


# -------------------------------------------------------------------------
# 4. Główna Pętla Sterowania (IoT Loop)
# -------------------------------------------------------------------------
@method_decorator(csrf_exempt, name='dispatch')
class IoTUpdateView(View):
    def post(self, request):
        # A. TOKEN
        auth_header = request.headers.get('Authorization')
        token = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            try:
                body_data = json.loads(request.body)
                token = body_data.get('token')
            except:
                pass

        if not token: return JsonResponse({'error': 'Missing Token'}, status=401)

        try:
            allowed = AllowedDevice.objects.get(api_token=token)
            dev_id = allowed.device_id
        except AllowedDevice.DoesNotExist:
            return JsonResponse({'error': 'Invalid Token'}, status=401)

        try:
            # B. DANE
            try:
                data = json.loads(request.body)
            except JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)

            raw_temp = data.get('temp')
            raw_hum = data.get('hum')

            if raw_temp is None or raw_hum is None:
                return JsonResponse({'error': 'Missing temp/hum'}, status=400)

            try:
                temp = float(raw_temp)
                hum = float(raw_hum)
            except ValueError:
                return JsonResponse({'error': 'Temp/Hum must be numbers'}, status=400)

            # Feedback
            real_heat = data.get('heater_state', False)
            real_mist = data.get('mist_state', False)
            real_light = data.get('light_state', False)

            # C. URZĄDZENIE
            device, created = Terrarium.objects.get_or_create(
                device_id=dev_id, defaults={'name': f"Terrarium {dev_id}"}
            )

            device.last_seen = timezone.now()
            device.is_online = True
            device.is_heating = real_heat
            device.is_misting = real_mist
            device.is_lighting = real_light
            device.save()

            Reading.objects.create(
                terrarium=device, temp=temp, hum=hum,
                heater=real_heat, mist=real_mist, light=real_light
            )

            # D. LOGIKA
            now = timezone.localtime()
            now_time = now.time()

            # --- D.1 ALERTY (Naprawione wcięcia!) ---
            if device.alerts_enabled and device.alert_email:
                cooldown = True
                if device.last_alert_sent and (timezone.now() - device.last_alert_sent < timedelta(minutes=15)):
                    cooldown = False

                if cooldown:
                    subject = ""
                    should_send = False
                    # Format pod testy:
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

            # --- D.2 ŚWIATŁO ---
            cmd_light = False
            if device.light_mode == 'manual':
                cmd_light = device.light_manual_state
            else:
                if device.light_start <= device.light_end:
                    is_day = device.light_start <= now_time < device.light_end
                else:
                    is_day = now_time >= device.light_start or now_time < device.light_end
                cmd_light = is_day

            # --- D.3 GRZANIE ---
            target_temp = device.temp_day if cmd_light else device.temp_night
            hysteresis = 0.5
            cmd_heat = False
            if temp < (target_temp - hysteresis):
                cmd_heat = True
            elif temp > target_temp:
                cmd_heat = False
            else:
                cmd_heat = real_heat

            # --- D.4 ZRASZANIE ---
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
                    # Harmonogram
                    current_hm = now_time.strftime("%H:%M")
                    timers = [device.mist_h1, device.mist_h2, device.mist_h3, device.mist_h4]
                    for t in timers:
                        if t and t.strftime("%H:%M") == current_hm:
                            cmd_mist = True

                        # --- E. OBSŁUGA OTA (NOWOŚĆ) ---
            cmd_ota = False

             # Sprawdzamy, czy użytkownik kliknął przycisk w Dashboardzie
            if device.update_required:
                cmd_ota = True  # 1. Wysyłamy rozkaz "START UPDATE"
                device.update_required = False  # 2. Opuszczamy flagę (żeby nie robił pętli aktualizacji)
                device.save()



            # --- E. ODPOWIEDŹ (Teraz jest poza pętlą!) ---
            return JsonResponse({
                'status': 'ok',
                'heater': cmd_heat,
                'mist': cmd_mist,
                'light': cmd_light,
                'ota': cmd_ota,
                'target': target_temp,
                'name': device.name
            })

        except Exception as e:
            print(f"ERROR: {e}")
            return JsonResponse({'error': str(e)}, status=500)


# =========================================================
# MAGICZNE WRAPPERY DLA TESTÓW (BARDZO WAŻNE)
# =========================================================
# Dzięki temu testy widzą api_sensor_update jako funkcję,
# mimo że to jest klasa.
api_sensor_update = csrf_exempt(IoTUpdateView.as_view())
api_device_auth = csrf_exempt(DeviceAuthView.as_view())