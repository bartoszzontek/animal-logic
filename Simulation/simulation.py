import requests
import time
import random
import os

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
        # Stan "urządzeń" w symulatorze
        self.heater_on = False
        self.mist_on = False
        self.light_on = False

    def load_token(self):
        """Wczytuje zapisany token z pliku, żeby nie logować się co chwilę."""
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                t = f.read().strip()
                if t: return t
        return None

    def authenticate(self):
        """Loguje urządzenie i pobiera nowy token."""
        print(f"🔑 Brak tokena. Próba logowania dla {DEVICE_ID}...")
        try:
            # Tu też ważne: brak ukośnika na końcu, jeśli tak masz w urls.py
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
                print(f"❌ Błąd logowania: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Błąd połączenia (Auth): {e}")
            return False

    def print_status(self):
        """Wyświetla ładny status w konsoli."""
        status_symbol = "🔥" if self.heater_on else "❄️"
        mist_symbol = "💦" if self.mist_on else "🌵"
        light_symbol = "☀️" if self.light_on else "🌑"

        print("-" * 50)
        print(f"STATUS [{DEVICE_ID}]")
        print(f"Temp: {self.current_temp:.2f}°C  | Grzanie: {status_symbol}")
        print(f"Wilg: {self.current_hum:.2f}%   | Zraszanie: {mist_symbol}")
        print(f"Światło: {light_symbol}")
        print("-" * 50)

    def update_loop(self):
        print(f"--- Start Symulacji (HTTPS Secure) ---")
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

            # Ograniczenia zakresu (żeby nie wyszło poza skalę)
            self.current_temp = max(15.0, min(60.0, self.current_temp))
            self.current_hum = max(0.0, min(100.0, self.current_hum))

            # 3. Przygotuj dane do wysłania
            payload = {"temp": round(self.current_temp, 2), "hum": round(self.current_hum, 2)}

            # Nagłówek autoryzacji
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            try:
                print(f"📡 Wysyłam... ", end="")

                # --- KLUCZOWA ZMIANA TUTAJ ---
                # Usunięto ukośnik na końcu adresu URL: /sensor/update
                resp = requests.post(f"{API_URL}/sensor/update", json=payload, headers=headers, timeout=5)

                if resp.status_code == 200:
                    data = resp.json()
                    print(f"✅ OK")

                    # Odczytaj sterowanie z serwera
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

                elif resp.status_code == 404:
                    print(f"❌ Błąd 404 (Not Found). Sprawdź URL! (czy nie ma podwójnego // lub ukośnika na końcu)")

                else:
                    print(f"❌ Błąd serwera: {resp.status_code} - {resp.text}")

            except Exception as e:
                print(f"\n❌ Błąd połączenia: {e}")

            time.sleep(2)


if __name__ == "__main__":
    sim = SecureSimulator()
    sim.update_loop()