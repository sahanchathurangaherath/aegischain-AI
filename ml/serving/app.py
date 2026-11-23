from datetime import date
import logging
from typing import Any
from fastapi import BackgroundTasks, FastAPI
import numpy as np
import polars as pl
from prometheus_client import Counter, generate_latest
from pydantic import BaseModel, Field
from starlette.responses import Response

from features.contracts import DataContractViolation, validate_demand_frame
from models.baseline import baseline_ma7

logger = logging.getLogger(__name__)

PREDICTIONS_TOTAL = Counter(
    "aegis_ml_predictions_total",
    "Total forecast predictions served by model stage and degradation status",
    ["model_stage", "degraded"],
)

app = FastAPI(title="AegisChain Forecast Model Service", version="1.0.0")

MODEL_REGISTRY: dict[str, Any] = {
    "Production": None,
    "Staging": None,
}
SHADOW_PREDICTION_LOG: list[dict[str, Any]] = []


class HistoryPoint(BaseModel):
    date: date
    quantity: float
    is_promo: int = 0


class ForecastRequest(BaseModel):
    product_code: str = Field(..., min_length=1)
    warehouse_code: str = Field(default="WH-MAIN-01")
    segment: str = Field(default="FAST")
    horizon_days: int = Field(default=14, ge=1, le=90)
    lead_time_days: int = Field(default=7, ge=1, le=90)
    history: list[HistoryPoint]


class ForecastResponse(BaseModel):
    product_code: str
    warehouse_code: str
    model_version: str
    degraded: bool
    q10: list[float]
    q50: list[float]
    q90: list[float]
    safety_stock: float
    reorder_point: float
    target_coverage: float


def _run_shadow_prediction(req: ForecastRequest, history_vals: list[float]) -> None:
    """Asynchronously score the Staging (Challenger) model without impacting caller latency."""
    challenger = MODEL_REGISTRY.get("Staging")
    if challenger is None:
        return
    try:
        preds = challenger(history_vals, req.horizon_days)
        SHADOW_PREDICTION_LOG.append(
            {
                "product_code": req.product_code,
                "warehouse_code": req.warehouse_code,
                "model_stage": "Staging",
                "q50_sum": round(float(np.sum(preds["q50"])), 2),
                "q90_sum": round(float(np.sum(preds["q90"])), 2),
            }
        )
        PREDICTIONS_TOTAL.labels(model_stage="Staging", degraded="false").inc()
    except Exception as exc:
        logger.warning("Shadow challenger prediction failed: %s", exc)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "production_model_loaded": MODEL_REGISTRY["Production"] is not None,
        "staging_shadow_loaded": MODEL_REGISTRY["Staging"] is not None,
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type="text/plain")


@app.post("/predict", response_model=ForecastResponse)
async def predict(req: ForecastRequest, background_tasks: BackgroundTasks) -> ForecastResponse:
    rows = [
        {
            "product_code": req.product_code,
            "warehouse_code": req.warehouse_code,
            "segment": req.segment,
            "date": pt.date,
            "quantity": float(pt.quantity),
            "is_promo": int(pt.is_promo),
        }
        for pt in req.history
    ]
    history_vals = [max(0.0, float(pt.quantity)) for pt in req.history]

    degraded = False
    model_version = "lgbm-cqr-v1"
    try:
        df = pl.DataFrame(rows)
        validate_demand_frame(df)

        champion = MODEL_REGISTRY.get("Production")
        if champion is None:
            raise RuntimeError("No Production model loaded in registry")

        out = champion(history_vals, req.horizon_days)
        q10 = [round(float(x), 2) for x in out["q10"]]
        q50 = [round(float(x), 2) for x in out["q50"]]
        q90 = [round(float(x), 2) for x in out["q90"]]

        if MODEL_REGISTRY.get("Staging") is not None:
            background_tasks.add_task(_run_shadow_prediction, req, history_vals)

    except (DataContractViolation, RuntimeError, Exception) as exc:
        logger.warning("Degrading forecast to baseline_ma7 for %s: %s", req.product_code, exc)
        degraded = True
        model_version = "baseline_ma7"
        ma = baseline_ma7(history_vals, horizon=req.horizon_days)
        q50 = [round(float(x), 2) for x in ma]
        q10 = [round(max(0.0, float(x) * 0.8), 2) for x in ma]
        q90 = [round(float(x) * 1.2, 2) for x in ma]

    PREDICTIONS_TOTAL.labels(model_stage="Production", degraded=str(degraded).lower()).inc()

    lt = min(req.lead_time_days, len(q50))
    p50_lt = sum(q50[:lt])
    p90_lt = sum(q90[:lt])
    safety_stock = round(max(0.0, p90_lt - p50_lt), 2)
    reorder_point = round(p50_lt + safety_stock, 2)

    return ForecastResponse(
        product_code=req.product_code,
        warehouse_code=req.warehouse_code,
        model_version=model_version,
        degraded=degraded,
        q10=q10,
        q50=q50,
        q90=q90,
        safety_stock=safety_stock,
        reorder_point=reorder_point,
        target_coverage=0.90,
    )
