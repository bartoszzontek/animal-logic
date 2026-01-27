from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg
from django.db.models.functions import TruncHour
from apps.core.models import Reading, HourlyReading


class Command(BaseCommand):
    help = 'Kompresuje stare dane do średnich godzinowych i usuwa surowe wpisy'

    def handle(self, *args, **options):
        now = timezone.now()
        # Granica: Dane starsze niż 24h podlegają kompresji
        cutoff = now - timedelta(hours=24)

        # 1. POBIERANIE I GRUPOWANIE
        # To zapytanie Django przetłumaczy na szybkie GROUP BY w Postgresie
        readings_to_aggregate = Reading.objects.filter(
            timestamp__lt=cutoff
        ).annotate(
            hour=TruncHour('timestamp')
        ).values(
            'terrarium', 'hour'
        ).annotate(
            avg_temp=Avg('temp'),
            avg_hum=Avg('hum')
        ).order_by('hour')

        if not readings_to_aggregate:
            self.stdout.write("Brak danych do archiwizacji.")
            return

        # 2. ZAPISYWANIE ŚREDNICH (bulk_create dla szybkości)
        new_archives = []
        for entry in readings_to_aggregate:
            # Sprawdzamy, czy już nie ma archiwum dla tej godziny (żeby nie dublować)
            exists = HourlyReading.objects.filter(
                terrarium_id=entry['terrarium'],
                timestamp=entry['hour']
            ).exists()

            if not exists:
                new_archives.append(HourlyReading(
                    terrarium_id=entry['terrarium'],
                    timestamp=entry['hour'],
                    avg_temp=entry['avg_temp'],
                    avg_hum=entry['avg_hum']
                ))

        if new_archives:
            HourlyReading.objects.bulk_create(new_archives)
            self.stdout.write(self.style.SUCCESS(f'Utworzono {len(new_archives)} rekordów archiwalnych.'))

        # 3. USUWANIE SUROWYCH DANYCH
        deleted_count, _ = Reading.objects.filter(timestamp__lt=cutoff).delete()
        self.stdout.write(self.style.WARNING(f'Usunięto {deleted_count} surowych odczytów.'))