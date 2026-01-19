from django.contrib import admin
from django.contrib.auth.hashers import make_password
from .models import Terrarium, Reading, AllowedDevice

# --- 1. Konfiguracja dla AllowedDevice (z Tokenem API) ---
@admin.register(AllowedDevice)
class AllowedDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'short_token')
    readonly_fields = ('api_token',) # Token tylko do odczytu
    fields = ('device_id', 'pin_hash', 'api_token') # Kolejność pól

    def short_token(self, obj):
        return obj.api_token[:10] + "..." if obj.api_token else "-"
    short_token.short_description = "Token API"

    def save_model(self, request, obj, form, change):
        # Automatyczne haszowanie PINu, jeśli jest wpisany jawnym tekstem
        if len(obj.pin_hash) < 20:
            obj.pin_hash = make_password(obj.pin_hash)
        super().save_model(request, obj, form, change)

# --- 2. Prosta rejestracja pozostałych modeli ---
# Używamy try/except, żeby uniknąć błędu "AlreadyRegistered",
# jeśli Django zgłupieje przy przeładowaniu, ale ten kod jest czysty.

try:
    admin.site.register(Terrarium)
except admin.sites.AlreadyRegistered:
    pass

try:
    admin.site.register(Reading)
except admin.sites.AlreadyRegistered:
    pass