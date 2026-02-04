from django.core.management.base import BaseCommand
from inventory.models import InventoryScan


class Command(BaseCommand):
    help = 'Process pending inventory scans'

    def handle(self, *args, **options):
        pending_scans = InventoryScan.objects.filter(is_processed=False)
        count = pending_scans.count()
        
        self.stdout.write(f'Found {count} pending scans...')
        
        processed = 0
        for scan in pending_scans:
            scan.process_scan()
            processed += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully processed {processed} scans')
        )