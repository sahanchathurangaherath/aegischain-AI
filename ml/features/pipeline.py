import polars as pl

from features.contracts import validate_demand_frame

FEATURE_COLUMNS = [
    "sku_idx",
    "segment_idx",
    "day_of_week",
    "day_of_year",
    "is_promo",
    "lag_1",
    "lag_7",
    "lag_14",
    "roll_mean_7",
    "roll_std_7",
    "roll_mean_28",
]

SEGMENT_MAP = {"FAST": 0, "SLOW": 1, "INTERMITTENT": 2, "NEW": 3}


def build_feature_frame(df: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, int]]:
    """
    Validate upstream data contract and engineer leak-free lag, rolling,
    and calendar features in Polars.
    """
    validated = validate_demand_frame(df).sort(["product_code", "date"])
    unique_skus = validated["product_code"].unique(maintain_order=True).to_list()
    sku_map = {sku: idx for idx, sku in enumerate(unique_skus)}

    featured = validated.with_columns(
        pl.col("product_code").replace_strict(sku_map, default=-1).cast(pl.Int64).alias("sku_idx"),
        pl.col("segment").replace_strict(SEGMENT_MAP, default=0).cast(pl.Int64).alias("segment_idx"),
        pl.col("date").dt.weekday().cast(pl.Int64).alias("day_of_week"),
        pl.col("date").dt.ordinal_day().cast(pl.Int64).alias("day_of_year"),
        pl.col("quantity").shift(1).over("product_code").alias("lag_1"),
        pl.col("quantity").shift(7).over("product_code").alias("lag_7"),
        pl.col("quantity").shift(14).over("product_code").alias("lag_14"),
        pl.col("quantity").shift(1).rolling_mean(window_size=7, min_samples=1).over("product_code").alias("roll_mean_7"),
        pl.col("quantity").shift(1).rolling_std(window_size=7, min_samples=2).over("product_code").fill_null(0.0).alias("roll_std_7"),
        pl.col("quantity").shift(1).rolling_mean(window_size=28, min_samples=1).over("product_code").alias("roll_mean_28"),
    ).drop_nulls(subset=["lag_1", "lag_7", "lag_14"])

    return featured, sku_map
