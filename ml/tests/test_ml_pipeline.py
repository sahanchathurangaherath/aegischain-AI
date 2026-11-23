from datetime import date, timedelta
from fastapi.testclient import TestClient
import numpy as np
import polars as pl
import pytest

from data.generator import generate_demand_dataset
from eval.backtest import run_benchmark
from eval.drift import check_feature_drift
from features.contracts import DataContractViolation, validate_demand_frame
from serving.app import MODEL_REGISTRY, SHADOW_PREDICTION_LOG, app


def test_pandera_rejects_negative_quantity():
    bad_df = pl.DataFrame(
        {
            "product_code": ["SKU-001"],
            "warehouse_code": ["WH-MAIN-01"],
            "segment": ["FAST"],
            "date": [date(2026, 10, 1)],
            "quantity": [-15.0],
            "is_promo": [0],
        }
    )
    with pytest.raises(DataContractViolation):
        validate_demand_frame(bad_df)


def test_psi_detects_shifted_distribution():
    rng = np.random.default_rng(7)
    ref = rng.normal(50.0, 5.0, size=500)
    same = rng.normal(50.2, 5.0, size=500)
    shifted = rng.normal(70.0, 8.0, size=500)

    assert check_feature_drift(ref, same)["drift_detected"] is False
    assert check_feature_drift(ref, shifted)["drift_detected"] is True


def test_serving_degrades_gracefully_and_runs_shadow_challenger():
    client = TestClient(app)
    today = date(2026, 10, 15)
    history = [
        {"date": (today - timedelta(days=10 - i)).isoformat(), "quantity": 25.0, "is_promo": 0}
        for i in range(10)
    ]

    MODEL_REGISTRY["Production"] = None
    MODEL_REGISTRY["Staging"] = None
    resp = client.post(
        "/predict",
        json={"product_code": "SKU-FAST-001", "horizon_days": 7, "lead_time_days": 7, "history": history},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["degraded"] is True
    assert data["model_version"] == "baseline_ma7"

    SHADOW_PREDICTION_LOG.clear()
    MODEL_REGISTRY["Production"] = lambda vals, h: {"q10": [20.0] * h, "q50": [25.0] * h, "q90": [32.0] * h}
    MODEL_REGISTRY["Staging"] = lambda vals, h: {"q10": [21.0] * h, "q50": [26.0] * h, "q90": [33.0] * h}

    resp2 = client.post(
        "/predict",
        json={"product_code": "SKU-FAST-001", "horizon_days": 7, "lead_time_days": 7, "history": history},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["degraded"] is False
    assert data2["safety_stock"] == 49.0
    assert len(SHADOW_PREDICTION_LOG) == 1
    assert SHADOW_PREDICTION_LOG[0]["model_stage"] == "Staging"

    MODEL_REGISTRY["Production"] = None
    MODEL_REGISTRY["Staging"] = None


def test_benchmark_produces_all_four_segments():
    df = generate_demand_dataset(seed=42)
    report = run_benchmark(df, test_days=14, cal_days=14)
    assert set(report["segments"].keys()) == {"FAST", "SLOW", "INTERMITTENT", "NEW"}
