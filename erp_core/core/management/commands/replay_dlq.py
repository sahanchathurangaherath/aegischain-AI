from django.core.management.base import BaseCommand
from core.models import OutboxEvent


class Command(BaseCommand):
    help = "Reset dead-lettered OutboxEvent rows so the worker retries them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--event-type",
            type=str,
            default=None,
            help="Optional event_type filter (e.g., BalanceBelowReorderPoint).",
        )

    def handle(self, *args, **options):
        qs = OutboxEvent.objects.filter(dead_letter=True)
        if options["event_type"]:
            qs = qs.filter(event_type=options["event_type"])

        count = qs.update(
            dead_letter=False,
            attempts=0,
            last_error=None,
            processed_at=None,
        )
        self.stdout.write(self.style.SUCCESS(f"Re-queued {count} dead-letter outbox event(s)."))
