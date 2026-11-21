from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Assessment, OutboxEvent


@admin.register(OutboxEvent)
class OutboxEventAdmin(ModelAdmin):
    list_display = [
        'event_id',
        'event_type',
        'created_at',
        'processed_at',
        'attempts',
        'dead_letter',
    ]
    list_filter = ['event_type', 'dead_letter', 'processed_at']
    search_fields = ['event_id', 'event_type', 'last_error']
    readonly_fields = ['event_id', 'created_at', 'processed_at']
    actions = ['replay_dead_letters']

    def replay_dead_letters(self, request, queryset):
        updated = queryset.filter(dead_letter=True).update(
            dead_letter=False,
            attempts=0,
            last_error=None,
            processed_at=None,
        )
        self.message_user(request, f"Re-queued {updated} dead-letter outbox event(s).")
    replay_dead_letters.short_description = "Replay selected dead-letter events"


@admin.register(Assessment)
class AssessmentAdmin(ModelAdmin):
    list_display = [
        'event_id',
        'agent_name',
        'product_code',
        'warehouse_code',
        'risk_level',
        'escalated',
        'escalation_reason',
        'model_version',
        'latency_ms',
        'created_at',
    ]
    list_filter = ['agent_name', 'risk_level', 'escalated', 'escalation_reason', 'degraded']
    search_fields = ['event_id', 'product_code', 'warehouse_code', 'supplier_code']
    readonly_fields = ['event_id', 'created_at']
