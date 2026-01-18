from django.contrib import admin
from .models import Terrarium, AllowedDevice, Reading


@admin.register(AllowedDevice)
class AllowedDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'created_at')
    search_fields = ('device_id',)


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