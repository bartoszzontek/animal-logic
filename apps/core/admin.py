from django.contrib import admin
from .models import Terrarium, AllowedDevice, Reading


from django.contrib import admin
from .models import Terrarium, Reading, AllowedDevice
from django.contrib.auth.hashers import make_password

@admin.register(AllowedDevice)
class AllowedDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'short_token')
    readonly_fields = ('api_token',) # Token tylko do odczytu (generuje się sam)
    fields = ('device_id', 'pin_hash', 'api_token') # Kolejność pól w formularzu

    def short_token(self, obj):
        return obj.api_token[:10] + "..." if obj.api_token else "-"
    short_token.short_description = "Token API"

    # To pozwala wpisać PIN jawnie, a Django go zahaszuje przed zapisem
    def save_model(self, request, obj, form, change):
        # Jeśli pin_hash nie wygląda na hash (jest krótki), to go haszujemy
        if len(obj.pin_hash) < 20:
            obj.pin_hash = make_password(obj.pin_hash)
        super().save_model(request, obj, form, change)

# Reszta bez zmian (Terrarium, Reading)
admin.site.register(Terrarium)
admin.site.register(Reading)

@admin.register(Terrarium)
class TerrariumAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'name', 'owner', 'last_seen', 'is_online', 'temp_day')
    list_filter = ('is_online', 'mist_mode')
    search_fields = ('device_id', 'owner__username')

    # Ładne formatowanie online/offline
    def is_online(self, obj):
        return obj.is_online

    is_online.boolean = True


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ('terrarium', 'timestamp', 'temp', 'hum')
    list_filter = ('timestamp', 'terrarium')
    readonly_fields = ('terrarium', 'timestamp', 'temp', 'hum', 'is_heater_on')

    # Optymalizacja dla dużej bazy
    list_per_page = 50