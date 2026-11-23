import pandera.polars as pa
import polars as pl


class DataContractViolation(Exception):
    """Raised when an input DataFrame violates the upstream Pandera data contract."""


DEMAND_CONTRACT = pa.DataFrameSchema(
    {
        "product_code": pa.Column(pl.Utf8, nullable=False),
        "warehouse_code": pa.Column(pl.Utf8, nullable=False),
        "segment": pa.Column(
            pl.Utf8,
            checks=pa.Check.isin(["FAST", "SLOW", "INTERMITTENT", "NEW"]),
            nullable=False,
        ),
        "date": pa.Column(pl.Date, nullable=False),
        "quantity": pa.Column(pl.Float64, checks=pa.Check.greater_than_or_equal_to(0.0), nullable=False),
        "is_promo": pa.Column(pl.Int64, checks=pa.Check.isin([0, 1]), nullable=False),
    },
    strict=False,
)


def validate_demand_frame(df: pl.DataFrame) -> pl.DataFrame:
    """Validate demand frame against Pandera schema; raises DataContractViolation on error."""
    try:
        return DEMAND_CONTRACT.validate(df)
    except Exception as exc:
        raise DataContractViolation(f"Demand data contract violation: {exc}") from exc
