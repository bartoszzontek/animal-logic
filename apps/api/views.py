from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from django.core.mail import send_mail
from datetime import timedelta
import json
import secrets

# Upewnij się, że masz te modele w apps/core/models.py
from apps.core.models import Terrarium, Reading, AllowedDevice


@method_decorator(csrf_exempt, name='dispatch')
class DeviceAuthView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            dev_id = data.get('id')
            pin = data.get('pin')

            # Sprawdź czy urządzenie jest na liście dozwolonych (AllowedDevice)
            try:
                allowed = AllowedDevice.objects.get(device_id=dev_id)
            except AllowedDevice.DoesNotExist:
                return JsonResponse({'error': 'Device not allowed'}, status=403)

            # Sprawdź PIN
            if not check_password(str(pin), allowed.pin_hash):
                return JsonResponse({'error': 'Invalid PIN'}, status=403)

            # Utwórz lub pobierz Terrarium
            device, created = Terrarium.objects.get_or_create(device_id=dev_id)

            # Generowanie tokenu urządzenia (opcjonalne, jeśli używamy Shared Secret)
            if not device.api_token:
                device.api_token = secrets.token_urlsafe(32)
                device.save()

            return JsonResponse({'token': device.api_token})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class IoTUpdateView(View):
    def post(self, request):
        # 1. AUTORYZACJA (TOKEN Z SETTINGS.PY)
        # To pasuje do Twojego ESP i skryptu simulateon.py
        auth_header = request.headers.get('Authorization')
        expected_token = f"Bearer {settings.SENSOR_API_TOKEN}"

        if not auth_header or auth_header != expected_token:
            return JsonResponse({'error': 'Invalid or Missing Token'}, status=401)

        try:
            # 2. POBRANIE DANYCH
            data = json.loads(request.body)
            dev_id = data.get('id')
            pin = data.get('pin')
            temp = float(data.get('temp'))
            hum = float(data.get('hum'))

            # 3. WERYFIKACJA URZĄDZENIA W BAZIE
            try:
                # Szukamy urządzenia po ID (D1001), żeby pobrać jego ustawienia
                device = Terrarium.objects.get(device_id=dev_id)
            except Terrarium.DoesNotExist:
                # Jeśli nie ma w Terrarium, sprawdźmy w AllowedDevice i utwórzmy
                if AllowedDevice.objects.filter(device_id=dev_id).exists():
                    device = Terrarium.objects.create(device_id=dev_id, name=f"New {dev_id}")
                else:
                    return JsonResponse({'error': 'Device not found'}, status=404)

            # Opcjonalnie: Sprawdź PIN z AllowedDevice dla bezpieczeństwa
            try:
                allowed = AllowedDevice.objects.get(device_id=dev_id)
                if not check_password(str(pin), allowed.pin_hash):
                    return JsonResponse({'error': 'Invalid PIN'}, status=403)
            except AllowedDevice.DoesNotExist:
                pass  # Jeśli nie ma w Allowed, ale jest w Terrarium, puszczamy (zależy od Twojej logiki)

            # --- LOGIKA BIZNESOWA (TWOJA) ---

            now = timezone.localtime()
            now_time = now.time()

            # --- SYSTEM ALERTÓW ---
            if device.alerts_enabled:
                recipient_email = device.alert_email
                if not recipient_email and device.owner:
                    recipient_email = device.owner.email

                if recipient_email:
                    cooldown_passed = True
                    if device.last_alert_sent:
                        if now - device.last_alert_sent < timedelta(hours=1):
                            cooldown_passed = False

                    if cooldown_passed:
                        alert_subject = None
                        alert_msg = None

                        if temp < device.alert_min_temp:
                            alert_subject = f"🚨 ALARM: Niska temperatura w {device.name}!"
                            alert_msg = f"Aktualna temperatura: {temp}°C (Minimum: {device.alert_min_temp}°C).\nSprawdź grzałkę!"
                        elif temp > device.alert_max_temp:
                            alert_subject = f"🚨 ALARM: Wysoka temperatura w {device.name}!"
                            alert_msg = f"Aktualna temperatura: {temp}°C (Maksimum: {device.alert_max_temp}°C).\nRyzyko przegrzania!"

                        if alert_subject:
                            print(f"📧 WYSYŁAM EMAIL DO {recipient_email}: {alert_subject}")
                            try:
                                send_mail(
                                    alert_subject, alert_msg, 'system@animallogic.pl',
                                    [recipient_email], fail_silently=False,
                                )
                                device.last_alert_sent = now
                                device.save(update_fields=['last_alert_sent'])
                            except Exception as mail_err:
                                print(f"❌ Błąd wysyłki maila: {mail_err}")

            # --- STEROWANIE ---

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

            # Mgła (Zraszanie)
            mist_on = False
            if device.mist_enabled:
                if device.mist_mode == 'auto':
                    mist_on = hum < device.mist_min_humidity
                else:
                    current_simple = now_time.strftime("%H:%M")
                    for t in [device.mist_h1, device.mist_h2, device.mist_h3, device.mist_h4]:
                        if t and t.strftime("%H:%M") == current_simple:
                            mist_on = True

            # Zapis odczytu
            Reading.objects.create(
                terrarium=device, temp=temp, hum=hum,
                is_heater_on=heater_on, is_mist_on=mist_on, is_light_on=light_on
            )

            # Aktualizacja statusu urządzenia
            device.last_seen = now
            device.is_online = True
            device.save()

            # Odpowiedź dla ESP
            return JsonResponse({
                'status': 'ok',
                'heater': heater_on,
                'mist': mist_on,
                'light': light_on,
                'screen': True,  # Wymuszamy włączenie ekranu
                'name': device.name
            })

        except Exception as e:
            print("Błąd API:", e)
            return JsonResponse({'error': str(e)}, status=500)