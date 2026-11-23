from guardrails.inputs import GuardrailViolation
from harness.loop import extract_citations


def validate_order_quantity_ceiling(
    raw_qty: int | float,
    *,
    historical_max_order_qty: int,
    warehouse_capacity_units: int,
    max_stock_ceiling: int | None = None,
) -> int:
    """
    Enforce a hard upper bound on recommended order quantity.
    Rejects with GuardrailViolation rather than silently clamping.
    """
    if raw_qty <= 0:
        raise GuardrailViolation(
            code="non_positive_order_qty",
            message=f"Order quantity must be positive, got {raw_qty}.",
            details={"raw_qty": raw_qty},
        )

    bounds = [max(1, 3 * historical_max_order_qty), max(1, warehouse_capacity_units)]
    if max_stock_ceiling is not None:
        bounds.append(max(1, max_stock_ceiling))
    ceiling = min(bounds)

    if raw_qty > ceiling:
        raise GuardrailViolation(
            code="order_qty_exceeds_ceiling",
            message=f"Order quantity {raw_qty} exceeds hard ceiling {ceiling}.",
            details={"raw_qty": raw_qty, "ceiling": ceiling},
        )

    return int(round(raw_qty))


def require_citations(conclusion: str, minimum: int = 1) -> list[str]:
    """Reject uncited System 2 recommendations before they reach a human."""
    citations = extract_citations(conclusion)
    if len(citations) < minimum:
        raise GuardrailViolation(
            code="missing_citations",
            message=f"Recommendation requires at least {minimum} citation(s), found {len(citations)}.",
            details={"found": citations, "minimum": minimum},
        )
    return citations
