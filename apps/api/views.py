from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import check_password
from django.core.mail import send_mail
from datetime import timedelta
import json
import secrets

from apps.core.models import Terrarium, Reading, AllowedDevice


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
            device, created = Terrarium.objects.get_or_create(device_id=dev_id)
            if not device.api_token:
                device.api_token = secrets.token_urlsafe(32)
                device.save()
            return JsonResponse({'token': device.api_token})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class IoTUpdateView(View):
    def post(self, request):
        try:
            token = request.headers.get('X-Device-Token')
            if not token: return JsonResponse({'error': 'Missing Token'}, status=401)
            try:
                device = Terrarium.objects.get(api_token=token)
            except Terrarium.DoesNotExist:
                return JsonResponse({'error': 'Invalid Token'}, status=401)

            data = json.loads(request.body)
            temp = float(data.get('temp'))
            hum = float(data.get('hum'))

            now = timezone.localtime()
            now_time = now.time()

            # --- SYSTEM ALERTÓW ---
            # Sprawdzamy czy włączone
            if device.alerts_enabled:

                # Ustal adresata: Albo dedykowany mail, albo właściciel konta
                recipient_email = device.alert_email
                if not recipient_email and device.owner:
                    recipient_email = device.owner.email

                # Jeśli mamy adresata, sprawdzamy warunki
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
                            except Exception as mail_err:
                                print(f"❌ Błąd wysyłki maila: {mail_err}")

            # --- STEROWANIE ---
            if device.light_mode == 'manual':
                light_on = device.light_manual_state
                is_day = light_on
            else:
                if device.light_start <= device.light_end:
                    is_day = device.light_start <= now_time < device.light_end
                else:
                    is_day = now_time >= device.light_start or now_time < device.light_end
                light_on = is_day

            target_temp = device.temp_day if is_day else device.temp_night
            heater_on = temp < target_temp

            mist_on = False
            if device.mist_enabled:
                if device.mist_mode == 'auto':
                    mist_on = hum < device.mist_min_humidity
                else:
                    current_simple = now_time.strftime("%H:%M")
                    for t in [device.mist_h1, device.mist_h2, device.mist_h3, device.mist_h4]:
                        if t and t.strftime("%H:%M") == current_simple:
                            mist_on = True

            Reading.objects.create(
                terrarium=device, temp=temp, hum=hum,
                is_heater_on=heater_on, is_mist_on=mist_on, is_light_on=light_on
            )

            device.last_seen = now
            device.is_online = True
            device.save()

            return JsonResponse({'heater': heater_on, 'mist': mist_on, 'light': light_on})

        except Exception as e:
            print("Błąd API:", e)
            return JsonResponse({'error': str(e)}, status=500)