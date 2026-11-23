from datetime import date, timedelta
from pathlib import Path
import numpy as np
import polars as pl


SEGMENTS = {
    "FAST": {"skus": 6, "base": 45.0, "noise": 6.0, "zero_prob": 0.0, "days": 365, "holding": 0.04, "stockout": 4.50},
    "SLOW": {"skus": 4, "base": 6.0, "noise": 2.0, "zero_prob": 0.25, "days": 365, "holding": 0.12, "stockout": 12.00},
    "INTERMITTENT": {"skus": 4, "base": 18.0, "noise": 5.0, "zero_prob": 0.72, "days": 365, "holding": 0.08, "stockout": 18.00},
    "NEW": {"skus": 3, "base": 20.0, "noise": 4.0, "zero_prob": 0.05, "days": 35, "holding": 0.06, "stockout": 8.00},
}


def generate_demand_dataset(
    end_date: date = date(2026, 10, 31),
    seed: int = 42,
) -> pl.DataFrame:
    """
    Generate synthetic daily demand across four supply chain SKU segments:
    FAST, SLOW, INTERMITTENT (zero-inflated), and NEW (cold-start).
    """
    rng = np.random.default_rng(seed)
    rows: list[dict] = []

    for segment, cfg in SEGMENTS.items():
        for idx in range(1, cfg["skus"] + 1):
            sku = f"SKU-{segment[:4]}-{idx:03d}"
            n_days = cfg["days"]
            start = end_date - timedelta(days=n_days - 1)
            sku_scale = rng.uniform(0.8, 1.25)

            for d_offset in range(n_days):
                current_date = start + timedelta(days=d_offset)
                dow = current_date.weekday()
                weekly = 1.18 if dow in (4, 5) else (0.82 if dow == 6 else 1.0)
                annual = 1.0 + 0.15 * np.sin(2.0 * np.pi * current_date.timetuple().tm_yday / 365.0)
                trend = 1.0 + 0.0004 * d_offset
                is_promo = int(rng.random() < 0.06)
                promo_lift = 1.45 if is_promo else 1.0

                if rng.random() < cfg["zero_prob"]:
                    qty = 0.0
                else:
                    mean_demand = cfg["base"] * sku_scale * weekly * annual * trend * promo_lift
                    qty = max(0.0, float(rng.normal(mean_demand, cfg["noise"])))

                rows.append(
                    {
                        "product_code": sku,
                        "warehouse_code": "WH-MAIN-01",
                        "segment": segment,
                        "date": current_date,
                        "quantity": round(qty, 2),
                        "is_promo": is_promo,
                        "holding_cost_per_day": cfg["holding"],
                        "stockout_penalty_per_unit": cfg["stockout"],
                    }
                )

    return pl.DataFrame(rows).sort(["product_code", "date"])


if __name__ == "__main__":
    out_path = Path(__file__).resolve().parent / "synthetic_demand.parquet"
    df = generate_demand_dataset()
    df.write_parquet(out_path)
    print(f"Generated {df.height} rows across {df['product_code'].n_unique()} SKUs -> {out_path}")
