import requests
import time
import random
import os

# --- KONFIGURACJA ---
# Upewnij się, że port jest dobry (zazwyczaj 8000 dla Django lokalnie)
API_URL = "http://127.0.0.1:8000/api"
DEVICE_ID = "A1001"
DEVICE_PIN = "1234"
TOKEN_FILE = "token_file.txt"


class SecureSimulator:
    def __init__(self):
        self.token = self.load_token()
        self.current_temp = 20.0
        self.current_hum = 45.0
        # Stan "urządzeń" w symulatorze
        self.heater_on = False
        self.mist_on = False
        self.light_on = False

    def load_token(self):
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                t = f.read().strip()
                if t: return t
        return None

    def authenticate(self):
        print(f"🔑 Brak tokena. Próba logowania dla {DEVICE_ID}...")
        try:
            # POPRAWKA 1: Adres URL musi pasować do urls.py (path('auth/device', ...))
            resp = requests.post(f"{API_URL}/auth/device", json={
                "id": DEVICE_ID,
                "pin": DEVICE_PIN
            })
            if resp.status_code == 200:
                token = resp.json().get('token')
                print(f"✅ Otrzymano token: {token[:10]}...")
                with open(TOKEN_FILE, "w") as f:
                    f.write(token)
                self.token = token
                return True
            else:
                print(f"❌ Błąd logowania: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Błąd połączenia (Auth): {e}")
            return False

    def print_status(self):
        status_symbol = "🔥" if self.heater_on else "❄️"
        mist_symbol = "💦" if self.mist_on else "🌵"
        light_symbol = "☀️" if self.light_on else "🌑"

        print("-" * 50)
        print(f"STATUS [{DEVICE_ID}]")
        print(f"Temp: {self.current_temp:.2f}°C  | Stan: {status_symbol}")
        print(f"Wilg: {self.current_hum:.2f}%   | Stan: {mist_symbol}")
        print(f"Światło: {light_symbol}")
        print("-" * 50)

    def update_loop(self):
        print(f"--- Start Symulacji (Secure) ---")
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

            # Ograniczenia zakresu
            self.current_temp = max(15.0, min(60.0, self.current_temp))
            self.current_hum = max(0.0, min(100.0, self.current_hum))

            # 3. Wyślij dane
            payload = {"temp": round(self.current_temp, 2), "hum": round(self.current_hum, 2)}

            # POPRAWKA 2: Nagłówek musi być 'Authorization: Bearer <token>'
            # Twój backend sprawdza: request.headers.get('Authorization').startswith("Bearer ")
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            try:
                print(f"📡 Wysyłam... ", end="")
                resp = requests.post(f"{API_URL}/sensor/update", json=payload, headers=headers, timeout=2)

                if resp.status_code == 200:
                    data = resp.json()
                    print(f"✅ OK")

                    self.heater_on = data.get('heater', False)
                    self.mist_on = data.get('mist', False)
                    self.light_on = data.get('light', False)

                    self.print_status()

                elif resp.status_code == 401:
                    print(f"❌ Błąd 401 (Unauthorized). Token wygasł? Usuwam plik.")
                    self.token = None
                    if os.path.exists(TOKEN_FILE): os.remove(TOKEN_FILE)

                elif resp.status_code == 400:
                    print(f"❌ Błąd 400 (Bad Request). Złe dane: {resp.text}")

                else:
                    print(f"❌ Błąd serwera: {resp.status_code} - {resp.text}")

            except Exception as e:
                print(f"\n❌ Błąd połączenia: {e}")

            time.sleep(2)


if __name__ == "__main__":
    sim = SecureSimulator()
    sim.update_loop()