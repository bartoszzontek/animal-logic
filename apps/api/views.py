import os
import json
import secrets
from datetime import timedelta

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


# --- WIDOKI POMOCNICZE ---

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


# --- WIDOKI KLASOWE ---

@method_decorator(csrf_exempt, name='dispatch')
class DeviceAuthView(View):
    """
    Widok opcjonalny - jeśli chciałbyś automatycznie generować tokeny na podstawie PINu.
    Obecnie Twój ESP używa tokena wpisanego na sztywno, ale to może się przydać w przyszłości.
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
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith("Bearer "):
            return JsonResponse({'error': 'Missing or Invalid Token Header'}, status=401)

        token = auth_header.split(" ")[1]

        try:
            allowed = AllowedDevice.objects.get(api_token=token)
            dev_id = allowed.device_id
        except AllowedDevice.DoesNotExist:
            return JsonResponse({'error': 'Unauthorized: Invalid Token'}, status=401)

        try:
            # 2. DANE Z ESP
            data = json.loads(request.body)
            temp = float(data.get('temp'))
            hum = float(data.get('hum'))

            # 3. POBRANIE URZĄDZENIA
            device, created = Terrarium.objects.get_or_create(
                device_id=dev_id,
                defaults={'name': f"Terrarium {dev_id}"}
            )

            # --- LOGIKA BIZNESOWA ---
            now = timezone.localtime()
            now_time = now.time()

            # A. ALERTY EMAIL
            if device.alerts_enabled:
                recipient_email = device.alert_email or (device.owner.email if device.owner else None)

                if recipient_email:
                    # Cooldown 1h
                    cooldown_passed = True
                    if device.last_alert_sent:
                        if now - device.last_alert_sent < timedelta(hours=1):
                            cooldown_passed = False

                    if cooldown_passed:
                        alert_subject = None
                        alert_msg = None

                        if temp < device.alert_min_temp:
                            alert_subject = f"🚨 ALARM: Niska temperatura w {device.name}!"
                            alert_msg = f"Aktualna: {temp}°C (Min: {device.alert_min_temp}°C)."
                        elif temp > device.alert_max_temp:
                            alert_subject = f"🚨 ALARM: Wysoka temperatura w {device.name}!"
                            alert_msg = f"Aktualna: {temp}°C (Max: {device.alert_max_temp}°C)."

                        if alert_subject:
                            print(f"📧 Sending mail to {recipient_email}")
                            try:
                                send_mail(
                                    alert_subject, alert_msg, 'system@animallogic.pl',
                                    [recipient_email], fail_silently=False,
                                )
                                device.last_alert_sent = now
                                device.save(update_fields=['last_alert_sent'])
                            except Exception as e:
                                print(f"❌ Mail error: {e}")

            # B. STEROWANIE (LOGIKA)

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
                    # Prosty harmonogram (sprawdzenie minuty)
                    current_hm = now_time.strftime("%H:%M")
                    timers = [device.mist_h1, device.mist_h2, device.mist_h3, device.mist_h4]
                    for t in timers:
                        if t and t.strftime("%H:%M") == current_hm:
                            mist_on = True

            # C. ZAPIS DO BAZY
            Reading.objects.create(
                terrarium=device, temp=temp, hum=hum,
                is_heater_on=heater_on, is_mist_on=mist_on, is_light_on=light_on
            )

            device.last_seen = now
            device.is_online = True
            device.save()

            # D. ODPOWIEDŹ DLA ESP (ROZKAZY)
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