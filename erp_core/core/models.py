from django.db import models
from django.utils import timezone
import uuid


class TimeStampedModel(models.Model):
    """
    Abstract base model that adds created and updated timestamps
    to all models that inherit from it
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """
    Abstract base model that uses UUID as primary key
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class Meta:
        abstract = True


class ActiveModel(models.Model):
    """
    Abstract base model that adds is_active flag for soft deletes
    """
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True



class OutboxEvent(models.Model):
    """
    Transactional outbox event written in the same database transaction as
    business writes and polled by the aegis_ai worker using FOR UPDATE SKIP LOCKED.
    """

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event_type = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    dead_letter = models.BooleanField(default=False, db_index=True)
    last_error = models.TextField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['processed_at', 'dead_letter', 'created_at']),
        ]

    def __str__(self):
        status = 'DLQ' if self.dead_letter else ('DONE' if self.processed_at else 'PENDING')
        return f"[{status}] {self.event_type} ({self.event_id})"


class Assessment(models.Model):
    """
    System 1 reflex assessment record. Also serves as Episodic Memory once
    `outcome` and `outcome_at` are populated by the nightly outcome join job.
    """

    event_id = models.UUIDField(db_index=True)
    agent_name = models.CharField(max_length=64)
    product_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    warehouse_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    supplier_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    risk_level = models.CharField(max_length=16, db_index=True)
    escalated = models.BooleanField(default=False, db_index=True)
    escalation_reason = models.CharField(max_length=32, default='none')
    findings = models.JSONField(default=dict)
    recommendations = models.JSONField(default=list)
    data_sufficiency = models.FloatField(default=0.0)
    calibrated_coverage = models.FloatField(null=True, blank=True)
    latency_ms = models.FloatField(default=0.0)
    model_version = models.CharField(max_length=64, default='rules-v1')
    degraded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Filled later by the nightly outcome join job (Phase 2)
    outcome = models.JSONField(null=True, blank=True)
    outcome_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.agent_name} [{self.risk_level}] ({self.event_id})"



class Deliberation(models.Model):
    """
    System 2 deliberative reasoning record storing assembled context budgets,
    tool calls, citations, prompt version, token counts, and estimated cost.
    """

    event_id = models.UUIDField(db_index=True)
    trigger_reason = models.CharField(max_length=32)
    prompt_version = models.CharField(max_length=32, db_index=True)
    model_name = models.CharField(max_length=64)
    assembled_context = models.JSONField(default=dict)
    tool_calls = models.JSONField(default=list)
    conclusion = models.TextField()
    proposed_action = models.JSONField(null=True, blank=True)
    citations = models.JSONField(default=list)
    terminated_by = models.CharField(max_length=32, default='completed')
    tokens_in = models.IntegerField(default=0)
    tokens_out = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    latency_ms = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Deliberation [{self.trigger_reason}] {self.model_name} ({self.event_id})"


class SupplierProfile(models.Model):
    """
    Entity memory for supplier performance, rebuilt periodically from
    completed shipments and episodic assessment outcomes.
    """

    supplier_code = models.CharField(max_length=64, unique=True)
    lead_time_p50 = models.FloatField(default=0.0)
    lead_time_p90 = models.FloatField(default=0.0)
    on_time_rate_90d = models.FloatField(default=100.0)
    seasonal_notes = models.JSONField(default=dict)
    incident_count_1y = models.IntegerField(default=0)
    source_window = models.CharField(max_length=32, default='90d')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['supplier_code']

    def __str__(self):
        return f"SupplierProfile {self.supplier_code} (p50={self.lead_time_p50}d, p90={self.lead_time_p90}d)"
