# AegisChain — ERP Backend & Frontend Implementation Plan

**Companion plan to [`docs/implementation_plan.md`](./implementation_plan.md) (AI DevOps & MLOps Edition).**

Repository: `sahanchathurangaherath/aegischain-AI`
Plan date: 2026-11-16
Scope: Upgrading `erp_core/` into an AI-native supply chain backend + building the `frontend/` AI Control Tower.
Target effort: **65–85 hours** total (40–50h ERP backend upgrades + 25–35h Next.js AI Control Tower).

---

## Why a Separate Plan?

Keeping the **ERP + Frontend Plan** separate from the **Main AI/MLOps Plan** gives you a clean architectural boundary:
1. **The Main Plan (`aegis_ai` + `ml`)** focuses on System 1/System 2 orchestration, memory, guardrails, Quantile LightGBM, Conformal Prediction, Shadow Deployment, and CI evaluation gates.
2. **This Plan (`erp_core` + `frontend`)** focuses on domain completeness, transactional integrity, supply chain unit economics, Human-in-the-Loop (HITL) workflows, and visual product experience.

### Synchronization Map (How Both Plans Connect)

| ERP / Frontend Phase | Complete Before / Alongside | Why the AI Layer Needs It |
| --- | --- | --- |
| **Phase E0** — ERP Bug Fixes, Concurrency & `django-unfold` | **Main Phase 0** | Fixes broken `TRANSFER` scans, race conditions, and unfinished methods (`pass`) in `erp_core`. Gives you an instant modern UI via `django-unfold`. |
| **Phase E1** — Supply Chain Economics, Multi-Sourcing & Outbox | **Main Phase 1** | Adds `OutboxEvent`, multi-supplier catalog (`SupplierProduct`), and holding/stockout costs needed by the System 1 reflex worker and simulator. |
| **Phase E2** — Unstructured Document Store & Outcome Join | **Main Phase 2** | Adds supplier PDF upload/chunking (`pgvector`) for Semantic Memory and the `join_outcomes` job for Episodic Memory. |
| **Phase E3** — HITL Approval Workflow & Preference Logging | **Main Phase 3** | Implements the `ApprovalRequest` state machine that turns AI proposals into real `PurchaseOrder` records and logs human overrides for MLOps. |
| **Phase E4** — Universal CSV / Webhook ERP Connector | **Main Phase 4 & 5** | Lets external pilot customers stream sales/inventory from SAP, Odoo, or Excel without migrating their company to your ERP. |
| **Phase F1** — 4-Screen Next.js "AI Control Tower" (`frontend/`) | **Main Phase 4 & 5** | Visualizes Quantile Fan Charts (`p10/p50/p90`), Agent Traces, PDF Citations, HITL Approvals, and Champion vs. Challenger MLOps metrics. |

---

## Global Tech Stack (ERP & Frontend)

| Layer | Choice | Notes |
| --- | --- | --- |
| ERP Backend | Django 5 + Django REST Framework | Existing `erp_core/` |
| API Schema | `drf-spectacular` (OpenAPI 3.0) | Replaces deprecated `drf-yasg`; auto-generates TypeScript client types for Next.js |
| Operational Admin UI | `django-unfold` + HTMX | Transforms Django Admin into a modern Tailwind back-office for CRUD in Phase E0 |
| AI Control Tower UI | Next.js 15 (App Router, TypeScript) | Dedicated 4-screen frontend for AI decisions, forecasts, and MLOps |
| Styling & Components | Tailwind CSS + `shadcn/ui` + Lucide Icons | Clean, high-density enterprise dashboard aesthetics |
| Data Visualization | `Recharts` | Renders Quantile Forecast fan charts (`p10`–`p90` shaded bands) and drift histograms |
| Data Fetching | `@tanstack/react-query` + `openapi-fetch` | Type-safe polling and mutations against `erp_core` and `aegis_ai` |
| PDF Parsing | `pypdf` / `pymupdf` | Extracts text from uploaded supplier contracts and incident reports |

---

## Phase E0 — Core ERP Fixes, Transactional Integrity & Instant Admin UI

**Goal:** Fix existing logic gaps in `erp_core/inventory/models.py`, `erp_core/procurement/models.py`, and `erp_core/sales/models.py`, enforce database row locking on stock movements, and install `django-unfold` so the ERP has a polished operational UI from Day 1.

**Effort:** 10–12 hours.

### What Exists Today vs. What Is Broken in `erp_core`

1. **`InventoryScan.process_scan()` (`erp_core/inventory/models.py`):**
   - Missing `TRANSFER` logic (`SCAN_TYPE_CHOICES` includes `'TRANSFER'`, but `process_scan()` ignores it).
   - No `destination_warehouse` field on `InventoryScan` for transfers.
   - No `transaction.atomic()` or `select_for_update()` — two concurrent scans for the same SKU will cause a lost-update race condition.
2. **`Warehouse.update_utilization()` (`erp_core/inventory/models.py`):**
   - Currently `pass`. Needs `unit_volume_cbm` on `Product` to calculate actual warehouse utilization.
3. **`Supplier.update_reliability_score()` (`erp_core/procurement/models.py`):**
   - Currently `pass`. Needs to compute on-time delivery rate and lead-time percentiles from `Shipment` and `PurchaseOrder` history.
4. **`SalesOrder` Stock Reservation & Fulfillment (`erp_core/sales/models.py`):**
   - Confirming a `SalesOrder` does not increment `InventoryBalance.quantity_reserved`, and shipping it does not deduct `quantity_on_hand`.

### Steps

**E0.1 — Fix `InventoryScan` Concurrency & `TRANSFER` Movements**

Add `destination_warehouse` (nullable `ForeignKey` to `Warehouse`) on `InventoryScan` and wrap `process_scan()` in a locked atomic transaction:

```python
# erp_core/inventory/models.py
from django.db import transaction
from django.core.exceptions import ValidationError

def process_scan(self):
    with transaction.atomic():
        scan = InventoryScan.objects.select_for_update().get(pk=self.pk)
        if scan.is_processed:
            return

        balance, _ = InventoryBalance.objects.select_for_update().get_or_create(
            product=scan.product,
            warehouse=scan.warehouse,
            defaults={"quantity_on_hand": 0},
        )

        if scan.scan_type == "IN":
            balance.quantity_on_hand += scan.quantity
        elif scan.scan_type == "OUT":
            if balance.quantity_available < scan.quantity:
                raise ValidationError("Insufficient available stock for OUT scan")
            balance.quantity_on_hand -= scan.quantity
        elif scan.scan_type == "TRANSFER":
            if not scan.destination_warehouse:
                raise ValidationError("destination_warehouse required for TRANSFER")
            if balance.quantity_available < scan.quantity:
                raise ValidationError("Insufficient available stock for TRANSFER")
            dest_balance, _ = InventoryBalance.objects.select_for_update().get_or_create(
                product=scan.product,
                warehouse=scan.destination_warehouse,
                defaults={"quantity_on_hand": 0},
            )
            balance.quantity_on_hand -= scan.quantity
            dest_balance.quantity_on_hand += scan.quantity
            dest_balance.save()
        elif scan.scan_type == "AUDIT":
            balance.update_variance(scan.quantity)
        elif scan.scan_type == "ADJUSTMENT":
            balance.quantity_on_hand = scan.quantity

        balance.save()
        scan.is_processed = True
        scan.processed_at = timezone.now()
        scan.save()
```

**E0.2 — Implement `Warehouse.update_utilization()` and `Supplier.update_reliability_score()`**

- Add `unit_volume_cbm = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0.01"))` to `Product`.
- Compute `Warehouse.current_utilization` as `sum(b.quantity_on_hand * b.product.unit_volume_cbm) / total_capacity * 100`.
- Compute `Supplier.on_time_delivery_rate` and `reliability_score` from completed `PurchaseOrder` and `Shipment` rows over the trailing 90 days.

**E0.3 — Wire `SalesOrder` State Machine (`confirm_order` and `fulfill_order`)**

- Transitioning `DRAFT → CONFIRMED` locks `InventoryBalance` rows and increments `quantity_reserved`.
- Transitioning `PACKED → SHIPPED` decrements both `quantity_reserved` and `quantity_on_hand` and creates an `OUT` `InventoryScan` record so sales history is automatically reflected in demand series.

**E0.4 — Replace `drf-yasg` with `drf-spectacular` & Install `django-unfold`**

```bash
cd erp_core && uv add drf-spectacular django-unfold
```

Configure `unfold` in `erp_core/config/settings.py` with sidebar navigation grouped into:
1. **Inventory & Warehouses** (`Product`, `Warehouse`, `InventoryBalance`, `InventoryScan`)
2. **Procurement & Suppliers** (`Supplier`, `PurchaseOrder`, `Shipment`)
3. **Sales & Fulfillment** (`SalesOrder`)
4. **AI Operations & Governance** (added in Phases E1–E3)

### Exit Criteria
- [ ] Unit tests verify `IN`, `OUT`, `TRANSFER`, `AUDIT`, and `ADJUSTMENT` scans under transaction locks
- [ ] Negative available stock on `OUT` or `TRANSFER` raises `ValidationError`
- [ ] Confirming and shipping a `SalesOrder` accurately updates `quantity_reserved` and `quantity_on_hand`
- [ ] `/admin/` renders with `django-unfold` and `/api/schema/` serves a valid OpenAPI 3.0 spec

---

## Phase E1 — Supply Chain Economics, Multi-Sourcing & Event Outbox

**Goal:** Give the ERP the economic parameters needed for real-world optimization (holding cost, stockout cost, MOQ, pack multiples, multi-supplier catalog) and emit transactional `OutboxEvent` records.

**Effort:** 10–14 hours.

### Steps

**E1.1 — Add Unit Economics & Ordering Constraints to `Product`**

Real reorder planning requires knowing how expensive it is to hold stock versus running out:

```python
# Additions to Product in erp_core/inventory/models.py
holding_cost_per_day = models.DecimalField(
    max_digits=8, decimal_places=4, default=Decimal("0.05"),
    help_text="Daily storage & capital cost per unit in USD"
)
stockout_penalty_per_unit = models.DecimalField(
    max_digits=10, decimal_places=2, default=Decimal("5.00"),
    help_text="Lost margin / penalty per unit short"
)
min_order_quantity = models.PositiveIntegerField(
    default=1, help_text="Minimum order quantity (MOQ)"
)
order_multiple = models.PositiveIntegerField(
    default=1, help_text="Order must be a multiple of this pack/pallet size"
)
max_stock_ceiling = models.PositiveIntegerField(
    default=10000, help_text="Hard guardrail ceiling for single-SKU stock"
)
demand_segment = models.CharField(
    max_length=20,
    choices=[("FAST", "Fast Mover"), ("SLOW", "Slow Mover"),
             ("INTERMITTENT", "Intermittent"), ("NEW", "New Product")],
    default="FAST"
)
```

**E1.2 — Add Multi-Sourcing Catalog (`SupplierProduct`) & Goods Receipt Quality (`GoodsReceipt`)**

Currently, `erp_core` has no link showing *which* suppliers sell *which* products or at what price/lead-time, making supplier switching during a disruption impossible.

```python
# erp_core/procurement/models.py
class SupplierProduct(TimeStampedModel):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="supplied_products")
    product = models.ForeignKey("inventory.Product", on_delete=models.CASCADE, related_name="supplier_options")
    supplier_sku = models.CharField(max_length=64, blank=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    lead_time_days = models.PositiveIntegerField(default=14)
    min_order_qty = models.PositiveIntegerField(default=1)
    is_primary = models.BooleanField(default=False)

    class Meta:
        unique_together = ("supplier", "product")
```

Also add `GoodsReceipt` on `PurchaseOrder` to record `received_qty`, `damaged_rejected_qty`, and `inspection_notes` so supplier quality ratings are data-driven.

**E1.3 — Add `OutboxEvent` and `Assessment` Models (`core/models.py`)**

Implement `OutboxEvent` and `Assessment` (as defined in Main Plan Phase 1.2 & 1.4). Emit outbox events inside the same database transaction whenever:
- `InventoryScan.process_scan()` completes → emits `InventoryMovementRecorded`
- `InventoryBalance.quantity_available` drops below `reorder_point` → emits `BalanceBelowReorderPoint`
- `Shipment.update_delay()` detects `delay_days > 0` → emits `ShipmentDelayed`
- `GoodsReceipt` records `damaged_rejected_qty > 0` → emits `SupplierQualityIncident`

### Exit Criteria
- [ ] Every product in seed data has realistic holding vs. stockout costs and primary + backup `SupplierProduct` rows
- [ ] Processing an `OUT` scan that crosses `reorder_point` writes both the balance update and `BalanceBelowReorderPoint` in a single atomic commit

---

## Phase E2 — Unstructured Document Store & Outcome Join

**Goal:** Enable the ERP to store and chunk unstructured supply chain documents (supplier contracts, SLA PDFs, delay emails, SOPs) for Phase 2 Semantic Memory, and run the nightly Outcome Join.

**Effort:** 10–12 hours.

### Steps

**E2.1 — Create the `documents` App in `erp_core`**

```python
# erp_core/documents/models.py
from pgvector.django import VectorField, HnswIndex

class SupplyChainDocument(TimeStampedModel):
    DOC_TYPES = [
        ("CONTRACT", "Supplier Contract / SLA"),
        ("SOP", "Standard Operating Procedure"),
        ("INCIDENT", "Disruption / Quality Incident Report"),
        ("INVOICE", "Commercial Invoice / Rate Card"),
    ]
    title = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES)
    supplier = models.ForeignKey("procurement.Supplier", null=True, blank=True, on_delete=models.SET_NULL)
    product = models.ForeignKey("inventory.Product", null=True, blank=True, on_delete=models.SET_NULL)
    file = models.FileField(upload_to="documents/%Y/%m/")
    severity = models.PositiveSmallIntegerField(default=0) # 0=routine, 1=warning, 2=critical
    valid_from = models.DateField(null=True, blank=True)
    is_indexed = models.BooleanField(default=False)

class DocumentChunk(models.Model):
    document = models.ForeignKey(SupplyChainDocument, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    chunk_text = models.TextField()
    embedding = VectorField(dimensions=384)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            HnswIndex(
                name="doc_chunk_emb_hnsw_idx",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]
```

**E2.2 — Build Document Ingestion & Hybrid Search Endpoint**

- When a PDF or Markdown document is uploaded in Django Admin or via `POST /api/documents/`, extract text, split into 400-token chunks with 50-token overlap, compute `bge-small-en-v1.5` embeddings, and store `DocumentChunk` rows.
- Expose `POST /api/documents/search/` supporting filtering by `supplier_code`, `product_code`, and hybrid score (`0.55 * cosine + 0.25 * recency + 0.20 * severity`).

**E2.3 — Build Entity Profiles (`SupplierProfile`, `ProductProfile`) & `join_outcomes` Job**

- Implement `python manage.py join_outcomes` (evaluates past `Assessment` rows against actual `SalesOrder` demand, stockout events, and `Shipment` arrival dates).
- Implement `python manage.py rebuild_entity_profiles` to compute empirical `lead_time_p50`, `lead_time_p90`, and `on_time_rate_90d` per supplier.

### Exit Criteria
- [ ] Uploading a sample supplier contract PDF in Django Admin automatically populates `DocumentChunk` rows with 384-dim embeddings
- [ ] `POST /api/documents/search/` returns ranked passages with source URI, document ID, and chunk index for citation
- [ ] `join_outcomes` populates `Assessment.outcome` on historical seeded assessments

---

## Phase E3 — Human-in-the-Loop (HITL) Approval & Preference Capture API

**Goal:** Turn AI recommendations into governed ERP actions (`PurchaseOrder` creation or stock transfers) with strict idempotency, dual-approval thresholds, and human-modification tracking for MLOps.

**Effort:** 8–10 hours.

### Steps

**E3.1 — Implement `ApprovalRequest` and `AuditEvent` in `core/models.py`**

Include fields that capture **human feedback** when an operator edits an AI recommendation before approving:

```python
class ApprovalRequest(TimeStampedModel):
    STATUS_CHOICES = [
        ("PENDING", "Pending Review"),
        ("APPROVED", "Approved As-Is"),
        ("MODIFIED", "Approved With Modification"),
        ("REJECTED", "Rejected"),
        ("EXPIRED", "Expired"),
    ]
    idempotency_key = models.CharField(max_length=128, unique=True)
    action_type = models.CharField(max_length=64) # CREATE_PO | CREATE_TRANSFER
    deliberation_id = models.UUIDField(db_index=True)
    product = models.ForeignKey("inventory.Product", on_delete=models.PROTECT)
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT)
    supplier = models.ForeignKey("procurement.Supplier", null=True, blank=True, on_delete=models.PROTECT)

    # AI Proposal vs Human Decision (MLOps Preference Dataset)
    ai_recommended_qty = models.PositiveIntegerField()
    final_approved_qty = models.PositiveIntegerField(null=True, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    value_usd = models.DecimalField(max_digits=12, decimal_places=2)
    reversibility = models.CharField(max_length=16, default="reversible")

    override_reason = models.CharField(
        max_length=64, blank=True,
        help_text="Why the human changed or rejected the AI quantity (e.g., CASHFLOW, MOQ, PROMO_ENDED)"
    )
    override_notes = models.TextField(blank=True)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    approvers = models.JSONField(default=list)
    resulting_po = models.ForeignKey("procurement.PurchaseOrder", null=True, blank=True, on_delete=models.SET_NULL)
```

**E3.2 — Build the Execution Transaction (`/api/approvals/{id}/decide/`)**

When a user submits `{"decision": "APPROVED" | "MODIFIED" | "REJECTED", "final_qty": 450, "override_reason": "..."}`:
1. Lock the `ApprovalRequest` row (`select_for_update()`).
2. Check role permissions and dual-approval rules (`value_usd >= DUAL_APPROVAL_THRESHOLD` requires 2 distinct users).
3. Enforce MOQ and `order_multiple` rounding rules from `SupplierProduct`.
4. If approved/modified, automatically create the `PurchaseOrder` and `PurchaseOrderItem`, link `resulting_po`, and write an immutable row to `AuditEvent`.

### Exit Criteria
- [ ] Approving an `ApprovalRequest` atomically creates a valid `PurchaseOrder` and logs an `AuditEvent`
- [ ] Re-submitting the same `idempotency_key` or clicking Approve twice never creates duplicate POs
- [ ] Modifying the AI quantity requires an `override_reason` and stores both `ai_recommended_qty` and `final_approved_qty`

---

## Phase E4 — Universal ERP Ingestion Connector (CSV / Webhook)

**Goal:** Allow external businesses (using SAP, Odoo, Tally, or Excel) to feed daily inventory and sales into `erp_core` without manual entry.

**Effort:** 6–8 hours.

### Steps

**E4.1 — Staging & Column Mapping Endpoint (`POST /api/ingest/csv/`)**

Accepts a CSV upload (`inventory_snapshot.csv` or `daily_sales.csv`) plus a tenant/source mapping profile:
1. Validates headers and data types with `Pandera` (no negative stock, valid dates, known or auto-provisioned SKU codes).
2. Upserts `Product`, `InventoryBalance`, and daily sales movement records inside an atomic batch.
3. Emits `OutboxEvent` records only for SKUs that crossed risk thresholds during the batch import.
4. Returns a structured ingestion summary (`rows_processed`, `rows_rejected`, `validation_errors`, `events_triggered`).

### Exit Criteria
- [ ] Uploading a 1,000-row CSV updates inventory balances, rejects malformed rows with clear line numbers, and triggers System 1 assessments in under 5 seconds

---

## Phase F1 — The 4-Screen Next.js "AI Control Tower" Frontend

**Goal:** Build a focused, high-impact Next.js frontend (`frontend/`) for supply chain operators and MLOps engineers—while keeping routine master-data CRUD in `django-unfold`.

**Effort:** 25–35 hours (build in Phase 4/5 once forecast models and System 2 traces exist).

### Architecture & Directory Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Sidebar navigation + live system status bar
│   │   ├── page.tsx                # Screen 1: Stockout & Risk Radar
│   │   ├── deliberations/
│   │   │   └── [id]/page.tsx       # Screen 2: Agent Deliberation & Trace Room
│   │   ├── approvals/
│   │   │   └── page.tsx            # Screen 3: HITL Action & Approval Gate
│   │   └── mlops/
│   │       └── page.tsx            # Screen 4: MLOps, Shadow Mode & Drift Health
│   ├── components/
│   │   ├── charts/
│   │   │   ├── QuantileFanChart.tsx    # Historical + p50 line + p10-p90 shaded band + ROP line
│   │   │   └── CostSimulatorCard.tsx   # Holding cost vs Stockout cost curve
│   │   ├── agent/
│   │   │   ├── TraceWaterfall.tsx      # Step-by-step tool calls & latency bars
│   │   │   ├── CitationDrawer.tsx      # Displays highlighted PDF chunks from pgvector
│   │   │   └── WhatIfPromptBar.tsx     # Natural-language scenario trigger
│   │   └── approvals/
│   │       └── ApprovalDecisionModal.tsx # Approve / Modify Qty + Override Reason selector
│   └── lib/
│       └── api.ts                  # Typed client generated from drf-spectacular OpenAPI schema
├── Dockerfile                      # Multi-stage Node 22 Alpine standalone build
└── package.json
```

### The 4 Core Screens

#### Screen 1: Stockout & Risk Radar (`/`)
- **Top KPI Ribbon:** Active Critical SKUs, Pending Approvals ($ value), 14-Day Projected Fill Rate, System 1 vs. System 2 Escalation Ratio.
- **Priority Risk Table:** Filterable by Warehouse, Demand Segment (`FAST`, `SLOW`, `INTERMITTENT`, `NEW`), and Risk Level. Shows `Days of Supply`, `Current Available`, `Reorder Point`, and `Recommended Order Qty`.
- **Interactive Quantile Fan Chart (`QuantileFanChart.tsx`):** Clicking any SKU renders:
  - Solid line for trailing 60-day actual demand,
  - Dashed line for `p50` median forecast over the next 14 days,
  - Shaded area for the Conformal `p10–p90` uncertainty interval,
  - Horizontal threshold lines for `Safety Stock` and `Reorder Point`.

#### Screen 2: Agent Deliberation & Decision Room (`/deliberations/[id]`)
- **Left Pane — Context & Blackboard:** Shows the exact token budget allocation (`assembled_context` bar chart: System, State, Entity, Episodic, Semantic) and any conflicts resolved (e.g., *"Live ERP stock overrode stale entity profile"*).
- **Center Pane — Tool Call & Reasoning Trace:** Visual step-by-step timeline of what the agent called (`get_inventory_balance`, `get_forecast`, `get_supplier_risk`), latency per tool, and the final synthesized conclusion.
- **Right Pane — Verifiable Citations & Supplier Options:** Clickable badges (`[Doc #14, Chunk 3]`, `[Assessment #892]`) that open the exact supplier contract clause or past stockout outcome. Shows Primary vs. Backup supplier comparison (`SupplierProduct`) for switching suppliers during a delay.
- **Bottom Bar — "What-If" Scenario Runner:** Input box allowing the planner to ask *"What if SUP-001 lead time increases by 10 days?"* and see the updated deliberation trace live.

#### Screen 3: Human-in-the-Loop Approval Gate (`/approvals`)
- **Action Cards:** Each card shows an AI-proposed Purchase Order with:
  - Expected stockout cost avoided vs. PO total cost (`value_usd`),
  - Guardrail badges (`Ceiling Check: PASSED`, `MOQ / Pack Multiple: Rounded to 200`, `Canary Check: CLEAN`),
  - Three actions:
    1. **Approve As-Is** (1 click → creates PO in `erp_core`),
    2. **Modify & Approve** (opens slider/input for quantity + mandatory dropdown for `override_reason`),
    3. **Reject** (logs rejection reason to episodic memory).

#### Screen 4: MLOps, Shadow Mode & Platform Health (`/mlops`)
- **Champion vs. Challenger (Shadow Mode) Scoreboard:** Side-by-side table comparing `Production` (`v1.2`) vs. `Staging` (`v1.3-shadow`) on live realized **MASE**, **WAPE**, and **90% Conformal Coverage** per SKU segment.
- **Feature Drift Status:** Displays latest weekly Evidently PSI scores per feature (`lag_7`, `rolling_mean_14`, `lead_time_days`) with green/amber/red status badges.
- **System Reliability & Cost:** Outbox consumer lag (`aegis_outbox_lag_seconds`), Dead-Letter Queue count with a **"Replay DLQ"** button, and trailing 60-minute LLM spend vs. the `MAX_USD_PER_HOUR` circuit breaker.

### Docker & Caddy Integration

Add `frontend` to `docker-compose.yml` under the `frontend` (or `core`) profile and route `/` in Caddy:

```
aegischain.example.com {
    reverse_proxy /api/*     erp:8000
    reverse_proxy /admin/*   erp:8000
    reverse_proxy /ai/*      ai:8001
    reverse_proxy /grafana/* grafana:3000
    reverse_proxy /*         frontend:3000
}
```

### Exit Criteria
- [ ] TypeScript types in `frontend/` are auto-generated from `erp_core` and `aegis_ai` OpenAPI schemas (`npm run generate-types`)
- [ ] Clicking **Approve** or **Modify** on Screen 3 updates the database and reflects the created `PurchaseOrder` link immediately
- [ ] Screen 1 renders the Conformal Quantile Fan Chart (`p10/p50/p90`) for any selected SKU
- [ ] Screen 4 displays live Champion vs. Shadow Challenger metrics and Outbox/Circuit-Breaker status
