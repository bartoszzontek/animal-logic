import requests
import time
import random
import os
import sys

# --- KONFIGURACJA ---
# Używamy HTTPS (Cloudflare Tunnel)
API_URL = "https://animal.zipit.pl/api"

# Dane Twojego urządzenia (muszą być takie same jak w bazie Django)
DEVICE_ID = "A1001"
DEVICE_PIN = "1234"
TOKEN_FILE = "token_file.txt"


class SecureSimulator:
    def __init__(self):
        self.token = self.load_token()
        self.current_temp = 20.0
        self.current_hum = 45.0

        # --- NOWOŚĆ: WERSJA FIRMWARE ---
        self.firmware_version = "1.0.0"

        # Stan "urządzeń" w symulatorze
        self.heater_on = False
        self.mist_on = False
        self.light_on = False

    def load_token(self):
        """Wczytuje zapisany token z pliku."""
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                t = f.read().strip()
                if t: return t
        return None

    def authenticate(self):
        """Loguje urządzenie i pobiera nowy token."""
        print(f"🔑 Brak tokena. Próba logowania dla {DEVICE_ID}...")
        try:
            resp = requests.post(f"{API_URL}/auth/device", json={
                "id": DEVICE_ID,
                "pin": DEVICE_PIN
            }, timeout=10)

            if resp.status_code == 200:
                token = resp.json().get('token')
                print(f"✅ Otrzymano token: {token[:10]}...")
                with open(TOKEN_FILE, "w") as f:
                    f.write(token)
                self.token = token
                return True
            else:
                print(f"❌ Błąd logowania: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Błąd połączenia (Auth): {e}")
            return False

    def simulate_ota_process(self, new_version_url):
        """Symuluje proces pobierania i instalacji aktualizacji."""
        print("\n" + "=" * 50)
        print(f"🚀 WYKRYTO AKTUALIZACJĘ OTA!")
        print(f"⬇️  Rozpoczynam pobieranie z: {new_version_url}")
        print("=" * 50)

        # 1. Symulacja pobierania (Download)
        for i in range(0, 101, 10):
            time.sleep(0.2)  # Symulacja czasu pobierania
            bar = "█" * (i // 5) + "-" * ((100 - i) // 5)
            sys.stdout.write(f"\r📥 Pobieranie: [{bar}] {i}%")
            sys.stdout.flush()
        print("\n✅ Pobrano pomyślnie.")

        # 2. Symulacja instalacji (Flash)
        print("💾 Instalowanie firmware'u...")
        time.sleep(1.5)

        # 3. Symulacja restartu
        print("🔄 Restartowanie urządzenia...")
        self.heater_on = False
        self.mist_on = False
        self.light_on = False
        self.current_temp = 20.0  # Reset czujników po restarcie

        # Zmiana wersji na "nowszą" (dla symulacji podbijamy o 0.0.1)
        # W prawdziwym urządzeniu wersja jest zaszyta w nowym kodzie
        major, minor, patch = map(int, self.firmware_version.split('.'))
        self.firmware_version = f"{major}.{minor}.{patch + 1}"

        time.sleep(2)
        print(f"✨ URZĄDZENIE URUCHOMIONE PONOWNIE (v{self.firmware_version})")
        print("=" * 50 + "\n")

    def print_status(self):
        """Wyświetla ładny status w konsoli."""
        status_symbol = "🔥" if self.heater_on else "❄️"
        mist_symbol = "💦" if self.mist_on else "🌵"
        light_symbol = "☀️" if self.light_on else "🌑"

        print(
            f"STATUS [{DEVICE_ID} v{self.firmware_version}] | T: {self.current_temp:.1f}°C {status_symbol} | H: {self.current_hum:.1f}% {mist_symbol} | L: {light_symbol}")

    def update_loop(self):
        print(f"--- Start Symulacji (Device: {DEVICE_ID}, Ver: {self.firmware_version}) ---")
        while True:
            # 1. Upewnij się, że mamy token
            if not self.token:
                if not self.authenticate():
                    time.sleep(5)
                    continue

            # 2. Fizyka (symulacja zmian temperatury)
            if self.heater_on:
                self.current_temp += 0.4 + random.uniform(-0.1, 0.1)
            else:
                if self.current_temp > 20.0: self.current_temp -= 0.1

            if self.mist_on:
                self.current_hum += 2.0
            else:
                if self.current_hum > 30.0: self.current_hum -= 0.5

            self.current_temp = max(15.0, min(60.0, self.current_temp))
            self.current_hum = max(0.0, min(100.0, self.current_hum))

            # 3. Przygotuj dane do wysłania
            payload = {
                "temp": round(self.current_temp, 2),
                "hum": round(self.current_hum, 2),
                # WAŻNE: Urządzenie wysyła swoją wersję, żeby serwer wiedział czy aktualizować
                "version": self.firmware_version
            }

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            try:
                # print(f"📡 Wysyłam... ", end="") # Zakomentowane dla czytelności
                resp = requests.post(f"{API_URL}/sensor/update", json=payload, headers=headers, timeout=5)

                if resp.status_code == 200:
                    data = resp.json()

                    # --- OBSŁUGA OTA ---
                    # Sprawdzamy czy serwer odesłał flagę ota_update=True
                    if data.get('ota_update') is True:
                        new_url = data.get('ota_url', 'http://unknown-url')
                        self.simulate_ota_process(new_url)
                        continue  # Pomijamy resztę pętli, bo urządzenie się "restartuje"

                    # Standardowe sterowanie
                    self.heater_on = data.get('heater', False)
                    self.mist_on = data.get('mist', False)
                    self.light_on = data.get('light', False)

                    self.print_status()

                elif resp.status_code == 401:
                    print(f"❌ Błąd 401 (Token wygasł). Loguję ponownie...")
                    self.token = None
                    if os.path.exists(TOKEN_FILE): os.remove(TOKEN_FILE)

                else:
                    print(f"❌ Błąd serwera: {resp.status_code} - {resp.text}")

            except Exception as e:
                print(f"❌ Błąd połączenia: {e}")

            time.sleep(2)


if __name__ == "__main__":
    sim = SecureSimulator()
    sim.update_loop()