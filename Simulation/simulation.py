import requests
import time
import random
import os
import sys

# --- KONFIGURACJA ---
API_URL = "https://animal.zipit.pl/api"
DEVICE_ID = "A1001"
DEVICE_PIN = "1234"
TOKEN_FILE = "token_file.txt"

# FIZYKA
ROOM_TEMP = 20.0
HEATING_POWER = 0.5
COOLING_RATE = 0.1
MISTING_POWER = 5.0
DRYING_RATE = 0.5


class UltimateSimulator:
    def __init__(self):
        self.token = self.load_token()
        self.current_temp = 21.5
        self.current_hum = 45.0
        self.firmware_version = "1.0.0"

        # Stany przekaźników
        self.relay_heater = False
        self.relay_mist = False
        self.relay_light = False

    def load_token(self):
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                return f.read().strip()
        return None

    def authenticate(self):
        print(f"🔑 Logowanie urządzenia {DEVICE_ID}...")
        try:
            resp = requests.post(f"{API_URL}/auth/device", json={
                "id": DEVICE_ID,
                "pin": DEVICE_PIN
            }, timeout=10)

            if resp.status_code == 200:
                self.token = resp.json().get('token')
                print(f"✅ Zalogowano! Token zapisany.")
                with open(TOKEN_FILE, "w") as f:
                    f.write(self.token)
                return True
            else:
                print(f"❌ Błąd logowania: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Błąd połączenia (Auth): {e}")
            return False

    def simulate_physics(self):
        if self.relay_heater:
            self.current_temp += HEATING_POWER + random.uniform(-0.05, 0.05)
        else:
            if self.current_temp > ROOM_TEMP:
                self.current_temp -= COOLING_RATE

        if self.relay_mist:
            self.current_hum += MISTING_POWER
        else:
            if self.current_hum > 30.0:
                self.current_hum -= DRYING_RATE

        self.current_temp = max(10.0, min(60.0, self.current_temp))
        self.current_hum = max(0.0, min(100.0, self.current_hum))

    def simulate_ota(self):
        """Udaje proces aktualizacji firmware'u"""
        print("\n" + "🚨" * 20)
        print(f"📡 WYKRYTO AKTUALIZACJĘ OTA (Klucz: 'ota')!")
        print(f"⬇️  Pobieranie aktualizacji...")
        print("-" * 40)

        for i in range(0, 101, 10):
            time.sleep(0.3)
            bar = "█" * (i // 5) + "░" * ((100 - i) // 5)
            sys.stdout.write(f"\r📥 Pobieranie: [{bar}] {i}%")
            sys.stdout.flush()

        print("\n💾 Zapisywanie do pamięci flash...")
        time.sleep(1)
        print("🔄 RESTART SYSTEMU...")
        time.sleep(2)

        # Zmiana wersji
        major, minor, patch = map(int, self.firmware_version.split('.'))
        self.firmware_version = f"{major}.{minor}.{patch + 1}"

        # Reset po restarcie
        self.relay_heater = False
        self.relay_mist = False
        self.relay_light = False

        print(f"✨ SYSTEM URUCHOMIONY: v{self.firmware_version}")
        print("🚨" * 20 + "\n")

    def print_status(self):
        icon_heat = "🔥 GRZEJE" if self.relay_heater else "❄️"
        icon_mist = "💦 POMPA" if self.relay_mist else "🌵"
        icon_light = "☀️ ŚWIATŁO" if self.relay_light else "🌑"

        print(f"[{time.strftime('%H:%M:%S')}] v{self.firmware_version} | "
              f"🌡️ {self.current_temp:.1f}°C {icon_heat} | "
              f"💧 {self.current_hum:.0f}% {icon_mist} | "
              f"{icon_light}")

    def run(self):
        print(f"🚀 START SYMULATORA (Connecting to: {API_URL})")

        while True:
            if not self.token:
                if not self.authenticate():
                    time.sleep(5)
                    continue

            self.simulate_physics()

            # Payload zgodny z Twoim serwerem (wysyłamy 'heater_state' itp.)
            payload = {
                "temp": round(self.current_temp, 2),
                "hum": round(self.current_hum, 2),
                "heater_state": self.relay_heater,
                "mist_state": self.relay_mist,
                "light_state": self.relay_light,
                "version": self.firmware_version
            }

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            try:
                resp = requests.post(f"{API_URL}/sensor/update", json=payload, headers=headers, timeout=5)

                if resp.status_code == 200:
                    data = resp.json()

                    # --- TUTAJ BYŁ BŁĄD, TERAZ JEST POPRAWIONE ---
                    # Twój serwer wysyła klucz "ota", a nie "ota_update"
                    if data.get('ota') is True:
                        self.simulate_ota()
                        continue

                        # Odbieranie rozkazów
                    self.relay_heater = data.get('heater', False)
                    self.relay_mist = data.get('mist', False)
                    self.relay_light = data.get('light', False)

                    self.print_status()

                elif resp.status_code == 401:
                    print("⚠️ Token wygasł. Usuwam i loguję ponownie.")
                    self.token = None
                    if os.path.exists(TOKEN_FILE): os.remove(TOKEN_FILE)

                else:
                    print(f"⚠️ Błąd serwera: {resp.status_code}")
                    # Wyświetl kawałek błędu, żeby widzieć o co chodzi
                    print(resp.text[:200])

            except Exception as e:
                print(f"❌ Błąd połączenia: {e}")

            time.sleep(2)


if __name__ == "__main__":
    sim = UltimateSimulator()
    sim.run()