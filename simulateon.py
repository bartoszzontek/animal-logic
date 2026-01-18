import requests
import json

# --- KONFIGURACJA ---
# Zgodnie z życzeniem: DOMENA (nie local)
URL = "https://animal.zipit.pl/api/sensor/update"
# Zwróć uwagę na HTTPS - Cloudflare tego wymaga

# Twój token
TOKEN = "dI-Fdlp40BeaJWzaEPBPnHh0afiz_5EvKaOqjZGgeYc"

# Dane urządzenia (Musi pasować do tego co w bazie!)
DEVICE_ID = "A1001"
PIN = "1234"

payload = {
    "id": DEVICE_ID,
    "pin": PIN,
    "temp": 25.5,
    "hum": 55.0
}

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "ESP8266-Controller"
}

print(f"📡 Wysyłam dane na: {URL}")

try:
    response = requests.post(URL, json=payload, headers=headers, timeout=10)

    print("-" * 30)
    print(f"Kod odpowiedzi: {response.status_code}")
    print(f"Treść: {response.text}")

    if response.status_code == 200:
        print("✅ SUKCES!")
    elif response.status_code == 404:
        print("❌ BŁĄD 404: Zła ścieżka. Pokaż mi pliki urls.py!")
    elif response.status_code == 403:
        print("⛔ BŁĄD 403: Domena wciąż kieruje na Home.pl lub Cloudflare blokuje.")

except Exception as e:
    print(f"💀 Błąd połączenia: {e}")