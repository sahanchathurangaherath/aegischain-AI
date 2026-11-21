import json
from typing import Any
from prometheus_client import Counter, Gauge
import psycopg
import structlog

from config.settings import settings
from system1.reflex import System1Reflex
from system2.deliberate import run_deliberation

logger = structlog.get_logger(__name__)

EVENTS_PROCESSED = Counter(
    "aegis_events_processed_total",
    "Total outbox events processed by the System 1 worker",
    ["status", "escalation_reason"],
)
OUTBOX_LAG_SECONDS = Gauge(
    "aegis_outbox_lag_seconds",
    "Age in seconds of the oldest unprocessed outbox event",
)
OUTBOX_DLQ_COUNT = Gauge(
    "aegis_outbox_dlq_count",
    "Number of dead-lettered outbox events awaiting replay",
)

SELECT_OUTBOX_SQL = """
SELECT id, event_id, event_type, payload, attempts, created_at
FROM core_outboxevent
WHERE processed_at IS NULL AND dead_letter = FALSE
ORDER BY created_at ASC
FOR UPDATE SKIP LOCKED
LIMIT %s
"""

CHECK_COOLDOWN_SQL = """
SELECT EXISTS (
    SELECT 1
    FROM core_assessment
    WHERE product_code = %s
      AND warehouse_code = %s
      AND escalated = TRUE
      AND created_at >= NOW() - (%s * INTERVAL '1 hour')
)
"""

INSERT_ASSESSMENT_SQL = """
INSERT INTO core_assessment (
    event_id, agent_name, product_code, warehouse_code, supplier_code,
    risk_level, escalated, escalation_reason, findings, recommendations,
    data_sufficiency, calibrated_coverage, latency_ms, model_version,
    degraded, created_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, NOW())
"""

MARK_PROCESSED_SQL = """
UPDATE core_outboxevent
SET processed_at = NOW(), attempts = attempts + 1
WHERE id = %s
"""

MARK_FAILED_SQL = """
UPDATE core_outboxevent
SET attempts = attempts + 1,
    last_error = %s,
    dead_letter = (attempts + 1 >= %s)
WHERE id = %s
"""

QUEUE_HEALTH_SQL = """
SELECT
    COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(created_at))) FILTER (
        WHERE processed_at IS NULL AND dead_letter = FALSE
    ), 0) AS lag_seconds,
    COUNT(*) FILTER (WHERE dead_letter = TRUE) AS dlq_count
FROM core_outboxevent
"""


class OutboxConsumer:
    """Polls `core_outboxevent` using FOR UPDATE SKIP LOCKED and runs System 1."""

    def __init__(self, dsn: str, reflex: System1Reflex | None = None):
        self.dsn = dsn
        self.reflex = reflex or System1Reflex()

    async def refresh_queue_metrics(self, conn: psycopg.AsyncConnection) -> None:
        async with conn.cursor() as cur:
            await cur.execute(QUEUE_HEALTH_SQL)
            row = await cur.fetchone()
            if row:
                OUTBOX_LAG_SECONDS.set(float(row[0] or 0.0))
                OUTBOX_DLQ_COUNT.set(int(row[1] or 0))

    async def _has_recent_escalation(
        self,
        cur: psycopg.AsyncCursor,
        payload: dict[str, Any],
    ) -> bool:
        product_code = payload.get("product_code")
        warehouse_code = payload.get("warehouse_code")
        if not product_code or not warehouse_code:
            return False
        await cur.execute(
            CHECK_COOLDOWN_SQL,
            (product_code, warehouse_code, settings.ESCALATION_COOLDOWN_HOURS),
        )
        row = await cur.fetchone()
        return bool(row and row[0])

    async def process_batch(self, batch_size: int | None = None) -> int:
        """Fetch and process up to `batch_size` pending outbox events."""
        limit = batch_size or settings.OUTBOX_BATCH_SIZE
        processed_count = 0

        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(SELECT_OUTBOX_SQL, (limit,))
                    rows = await cur.fetchall()

                    for row in rows:
                        row_id, event_id, event_type, raw_payload, attempts, created_at = row
                        payload = (
                            raw_payload
                            if isinstance(raw_payload, dict)
                            else json.loads(raw_payload)
                        )
                        try:
                            recent = await self._has_recent_escalation(cur, payload)
                            outcome = await self.reflex.evaluate(
                                event_id=str(event_id),
                                event_type=event_type,
                                payload=payload,
                                recent_deliberation_exists=recent,
                            )

                            for result in outcome.results:
                                await cur.execute(
                                    INSERT_ASSESSMENT_SQL,
                                    (
                                        str(event_id),
                                        result.agent_name,
                                        payload.get("product_code"),
                                        payload.get("warehouse_code"),
                                        payload.get("supplier_code"),
                                        result.risk_level.value,
                                        outcome.escalated,
                                        outcome.escalation_reason,
                                        json.dumps(result.findings),
                                        json.dumps(result.recommendations),
                                        float(result.confidence),
                                        None,
                                        float(result.execution_time_ms or outcome.latency_ms),
                                        result.findings.get("forecast_method", "rules-v1"),
                                        False,
                                    ),
                                )

                            if outcome.escalated:
                                await run_deliberation(outcome, payload)

                            await cur.execute(MARK_PROCESSED_SQL, (row_id,))
                            EVENTS_PROCESSED.labels(
                                status="processed",
                                escalation_reason=outcome.escalation_reason,
                            ).inc()
                            processed_count += 1

                        except Exception as exc:
                            logger.error(
                                "outbox_event_failed",
                                row_id=row_id,
                                event_id=str(event_id),
                                attempts=attempts + 1,
                                error=str(exc),
                            )
                            await cur.execute(
                                MARK_FAILED_SQL,
                                (str(exc)[:1000], settings.OUTBOX_MAX_ATTEMPTS, row_id),
                            )
                            EVENTS_PROCESSED.labels(
                                status="failed",
                                escalation_reason="error",
                            ).inc()

            await self.refresh_queue_metrics(conn)

        return processed_count
