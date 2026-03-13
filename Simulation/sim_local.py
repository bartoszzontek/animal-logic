import requests
import time
import random
import sys

# ==========================================
# KONFIGURACJA (LOCALHOST)
# ==========================================
# Adres Twojego lokalnego serwera Django
BASE_URL = "http://127.0.0.1:8000/api"

# Dane urządzenia (muszą istnieć w bazie admina!)
DEVICE_ID = "TEST01"
DEVICE_PIN = "1234"

# Fizyka symulacji
ROOM_TEMP = 20.0  # Temperatura pokoju (do niej dąży terrarium gdy nie grzeje)
HEATING_POWER = 0.4  # O ile stopni rośnie temp na cykl grzania
COOLING_RATE = 0.1  # O ile stopni spada temp gdy nie grzeje
MISTING_POWER = 3.0  # O ile % rośnie wilgotność przy zraszaniu
DRYING_RATE = 0.5  # O ile % spada wilgotność naturalnie


class SmartTerrariumSimulator:
    def __init__(self):
        self.token = None

        # Stan początkowy środowiska
        self.current_temp = 21.0
        self.current_hum = 50.0

        # RZECZYWISTY stan przekaźników (To co wysyłamy jako feedback)
        self.relay_heater = False
        self.relay_mist = False
        self.relay_light = False

    def authenticate(self):
        """Logowanie do API po token"""
        print(f"🔑 Logowanie jako {DEVICE_ID}...")
        try:
            resp = requests.post(f"{BASE_URL}/auth/device", json={
                "id": DEVICE_ID,
                "pin": DEVICE_PIN
            })

            if resp.status_code == 200:
                self.token = resp.json().get('token')
                print(f"✅ Zalogowano! Token: {self.token[:10]}...")
                return True
            else:
                print(f"❌ Błąd logowania: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Serwer nie odpowiada: {e}")
            return False

    def update_physics(self):
        """Symulacja fizyki terrarium"""
        # 1. Temperatura
        if self.relay_heater:
            # Grzanie: Rośnie + mała losowość
            self.current_temp += HEATING_POWER + random.uniform(-0.05, 0.05)
        else:
            # Stygnięcie: Spada w stronę temp. pokojowej
            if self.current_temp > ROOM_TEMP:
                self.current_temp -= COOLING_RATE

        # 2. Wilgotność
        if self.relay_mist:
            self.current_hum += MISTING_POWER
        else:
            if self.current_hum > 30.0:  # Minimum 30%
                self.current_hum -= DRYING_RATE

        # Ograniczenia (Limity czujnika)
        self.current_temp = max(10.0, min(50.0, self.current_temp))
        self.current_hum = max(0.0, min(100.0, self.current_hum))

    def run(self):
        print(f"\n🚀 Start Symulatora Terrarium [{DEVICE_ID}]")
        print("Cykliczne wysyłanie danych do Localhost...\n")

        if not self.authenticate():
            return

        while True:
            # 1. Oblicz nową temperaturę/wilgotność na podstawie włączonych urządzeń
            self.update_physics()

            # 2. Przygotuj dane (PAYLOAD)
            # Tu wysyłamy FEEDBACK: "temp jest X, a grzałka jest Y"
            payload = {
                "temp": round(self.current_temp, 2),
                "hum": round(self.current_hum, 2),
                "heater_state": self.relay_heater,  # <--- To jest kluczowe!
                "mist_state": self.relay_mist,
                "light_state": self.relay_light
            }

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            try:
                # 3. Wyślij do Django
                resp = requests.post(f"{BASE_URL}/sensor/update", json=payload, headers=headers)

                if resp.status_code == 200:
                    # 4. Odbierz ROZKAZY z Django
                    commands = resp.json()

                    # Decyzja serwera:
                    cmd_heat = commands.get('heater', False)
                    cmd_mist = commands.get('mist', False)
                    cmd_light = commands.get('light', False)
                    target = commands.get('target', 0)

                    # 5. Wykonaj rozkazy (Przełącz wirtualne przekaźniki)
                    self.relay_heater = cmd_heat
                    self.relay_mist = cmd_mist
                    self.relay_light = cmd_light

                    # 6. Wyświetl ładny log
                    self.print_status(target)

                elif resp.status_code == 401:
                    print("⚠️ Token wygasł. Ponowne logowanie...")
                    self.authenticate()
                else:
                    print(f"❌ Błąd serwera: {resp.status_code}")

            except requests.exceptions.ConnectionError:
                print("❌ Nie można połączyć z Django (czy serwer działa?)")

            time.sleep(2)  # Czekaj 2 sekundy

    def print_status(self, target_temp):
        # Ikony stanu
        icon_heat = "🔥 GRZEJE" if self.relay_heater else "❄️ STOP"
        icon_mist = "💦 ZRASZA" if self.relay_mist else "🌵 SUCHO"
        icon_light = "☀️ DZIEŃ" if self.relay_light else "🌑 NOC"

        print("-" * 60)
        print(f"🌡️  Temp: {self.current_temp:.2f}°C (Cel: {target_temp}°C) | {icon_heat}")
        print(f"💧 Wilg: {self.current_hum:.1f}%                  | {icon_mist}")
        print(f"💡 Światło: {icon_light}")
        print("-" * 60)


if __name__ == "__main__":
    sim = SmartTerrariumSimulator()
    sim.run()