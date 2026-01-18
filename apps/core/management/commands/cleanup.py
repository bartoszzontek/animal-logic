from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Reading

class Command(BaseCommand):
    help = 'Usuwa stare pomiary z bazy danych, aby zapobiec jej przepełnieniu.'

    def handle(self, *args, **options):
        # 1. Oblicz datę graniczną (30 dni temu)
        retention_days = 30
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        self.stdout.write(f"🧹 Rozpoczynam czyszczenie danych starszych niż {cutoff_date.date()}...")

        # 2. Znajdź stare rekordy
        old_readings = Reading.objects.filter(timestamp__lt=cutoff_date)
        count = old_readings.count()

        if count > 0:
            # 3. Usuń je (w paczkach, żeby nie zatkać bazy przy milionach rekordów)
            # Django delete() radzi sobie z tym dobrze, ale przy gigantycznych bazach robi się to pętlą.
            # Dla < 1mln rekordów delete() jest ok.
            old_readings.delete()
            self.stdout.write(self.style.SUCCESS(f"✅ Usunięto {count} starych pomiarów."))
        else:
            self.stdout.write(self.style.SUCCESS("✅ Brak starych danych do usunięcia."))