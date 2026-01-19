from django.contrib import admin
from django.contrib.auth.hashers import make_password
from .models import Terrarium, Reading, AllowedDevice


@admin.register(AllowedDevice)
class AllowedDeviceAdmin(admin.ModelAdmin):
    # Wyświetlanie na liście
    list_display = ('device_id', 'short_token', 'short_pin_status')

    # Token tylko do odczytu (bo generuje się sam)
    readonly_fields = ('api_token',)

    # Pola w formularzu edycji
    fields = ('device_id', 'pin_hash', 'api_token')

    def short_token(self, obj):
        return obj.api_token[:15] + "..." if obj.api_token else "-"

    short_token.short_description = "Token API (Skopiuj do ESP)"

    def short_pin_status(self, obj):
        return "🔒 Zahaszowany" if obj.pin_hash else "⚠️ Brak"

    short_pin_status.short_description = "Status PIN"

    # --- TO JEST MAGIA DLA PINU ---
    def save_model(self, request, obj, form, change):
        # Sprawdzamy, czy to, co wpisałeś wygląda jak PIN (krótkie) czy jak HASH (długie)
        # Jeśli wpisałeś "1234" (krótkie), to system sam to zakoduje.
        if len(obj.pin_hash) < 20:
            obj.pin_hash = make_password(obj.pin_hash)

        super().save_model(request, obj, form, change)

    # Dodajemy opis do formularza, żebyś wiedział co wpisać
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['pin_hash'].label = "PIN Urządzenia"
        form.base_fields[
            'pin_hash'].help_text = "Wpisz tutaj normalny PIN (np. 1234). System sam go zaszyfruje po kliknięciu Zapisz."
        return form


# Rejestracja pozostałych modeli (zabezpieczona przed duplikatami)
try:
    admin.site.register(Terrarium)
except admin.sites.AlreadyRegistered:
    pass

try:
    admin.site.register(Reading)
except admin.sites.AlreadyRegistered:
    pass