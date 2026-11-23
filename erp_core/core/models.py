from decimal import Decimal
import uuid
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


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



class AuditEvent(models.Model):
    """
    Append-only security and governance audit log. In production Postgres,
    UPDATE and DELETE are revoked at the database role level.
    """

    event_type = models.CharField(max_length=64, db_index=True)
    actor = models.CharField(max_length=128)
    deliberation_id = models.UUIDField(null=True, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.event_type}] by {self.actor} @ {self.created_at}"


class ApprovalRequest(TimeStampedModel):
    """
    Human-in-the-Loop (HITL) action gate for AI-proposed procurement writes.
    Enforces idempotency, dual-approval thresholds, and captures human overrides
    (`ai_recommended_qty` vs `final_approved_qty`) for downstream evaluation.
    """

    ALLOWED_ACTIONS = {'CREATE_PO', 'CREATE_TRANSFER'}

    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved As-Is'),
        ('MODIFIED', 'Approved With Modification'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    ]

    REVERSIBILITY_CHOICES = [
        ('reversible', 'Reversible'),
        ('irreversible', 'Irreversible'),
    ]

    idempotency_key = models.CharField(max_length=128, unique=True)
    action_type = models.CharField(max_length=64)
    deliberation_id = models.UUIDField(db_index=True)
    product = models.ForeignKey('inventory.Product', on_delete=models.PROTECT)
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.PROTECT)
    supplier = models.ForeignKey(
        'procurement.Supplier',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )

    ai_recommended_qty = models.PositiveIntegerField()
    final_approved_qty = models.PositiveIntegerField(null=True, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    value_usd = models.DecimalField(max_digits=12, decimal_places=2)
    reversibility = models.CharField(
        max_length=16,
        choices=REVERSIBILITY_CHOICES,
        default='reversible',
    )

    override_reason = models.CharField(max_length=64, blank=True)
    override_notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='PENDING')
    approvers = models.JSONField(default=list)
    resulting_po = models.ForeignKey(
        'procurement.PurchaseOrder',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Approval [{self.status}] {self.action_type} x{self.ai_recommended_qty} (${self.value_usd})"

    def decide(
        self,
        *,
        approver_id: str,
        decision: str,
        final_qty: int | None = None,
        override_reason: str = '',
        override_notes: str = '',
        dual_approval_threshold: Decimal = Decimal('10000.00'),
        dry_run: bool = False,
    ) -> 'ApprovalRequest':
        """Record a human approval/modification/rejection atomically."""
        from datetime import timedelta
        from procurement.models import PurchaseOrder, PurchaseOrderItem

        if self.action_type not in self.ALLOWED_ACTIONS:
            raise ValidationError(f"Action '{self.action_type}' is not in ALLOWED_ACTIONS.")

        with transaction.atomic():
            req = ApprovalRequest.objects.select_for_update().get(pk=self.pk)
            if req.status != 'PENDING':
                raise ValidationError(f"ApprovalRequest is already finalized ({req.status}).")

            if decision == 'REJECTED':
                req.status = 'REJECTED'
                req.override_reason = override_reason
                req.override_notes = override_notes
                req.approvers = list(dict.fromkeys([*req.approvers, approver_id]))
                req.save()
                AuditEvent.objects.create(
                    event_type='APPROVAL_REJECTED',
                    actor=approver_id,
                    deliberation_id=req.deliberation_id,
                    payload={'approval_id': req.pk, 'reason': override_reason},
                )
                return req

            if decision not in ('APPROVED', 'MODIFIED'):
                raise ValidationError(f"Invalid decision: {decision}")

            if decision == 'MODIFIED':
                if not final_qty or final_qty <= 0:
                    raise ValidationError("final_qty > 0 is required for MODIFIED decision.")
                if not override_reason:
                    raise ValidationError("override_reason is required when modifying AI quantity.")
                req.final_approved_qty = final_qty
                req.override_reason = override_reason
                req.override_notes = override_notes
            else:
                req.final_approved_qty = req.ai_recommended_qty

            if approver_id not in req.approvers:
                req.approvers = [*req.approvers, approver_id]

            if req.value_usd >= dual_approval_threshold and len(req.approvers) < 2:
                req.save(
                    update_fields=[
                        'approvers',
                        'final_approved_qty',
                        'override_reason',
                        'override_notes',
                        'updated_at',
                    ]
                )
                AuditEvent.objects.create(
                    event_type='APPROVAL_FIRST_SIGNATURE',
                    actor=approver_id,
                    deliberation_id=req.deliberation_id,
                    payload={'approval_id': req.pk, 'value_usd': str(req.value_usd)},
                )
                return req

            req.status = decision
            if not dry_run and req.action_type == 'CREATE_PO' and req.supplier_id:
                po = PurchaseOrder.objects.create(
                    po_number=f"PO-AI-{req.pk}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                    supplier=req.supplier,
                    warehouse=req.warehouse,
                    expected_delivery_date=timezone.now().date() + timedelta(days=req.supplier.lead_time_days),
                    status='DRAFT',
                    created_by=approver_id,
                    notes=f"Generated from ApprovalRequest #{req.pk} (deliberation {req.deliberation_id})",
                )
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    product=req.product,
                    quantity_ordered=req.final_approved_qty,
                    unit_price=req.unit_price,
                )
                req.resulting_po = po

            req.save()
            AuditEvent.objects.create(
                event_type='APPROVAL_EXECUTED' if not dry_run else 'APPROVAL_DRY_RUN',
                actor=approver_id,
                deliberation_id=req.deliberation_id,
                payload={
                    'approval_id': req.pk,
                    'decision': decision,
                    'ai_qty': req.ai_recommended_qty,
                    'final_qty': req.final_approved_qty,
                    'po_id': req.resulting_po_id,
                },
            )
            return req
