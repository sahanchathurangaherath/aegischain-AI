from dataclasses import dataclass
import lightgbm as lgb
import numpy as np
import polars as pl

from features.pipeline import FEATURE_COLUMNS


@dataclass
class QuantileForecast:
    q10: np.ndarray
    q50: np.ndarray
    q90: np.ndarray
    conformal_offset: float
    target_coverage: float = 0.90


class ConformalQuantileForecaster:
    """
    Global Quantile LightGBM (q=0.10, 0.50, 0.90) calibrated with
    Conformalized Quantile Regression (CQR) for guaranteed interval coverage.
    """

    def __init__(self, alpha: float = 0.10, random_state: int = 42):
        self.alpha = alpha
        self.random_state = random_state
        self.models: dict[float, lgb.LGBMRegressor] = {}
        self.conformal_q_hat: float = 0.0

    def _make_regressor(self, quantile: float) -> lgb.LGBMRegressor:
        return lgb.LGBMRegressor(
            objective="quantile",
            alpha=quantile,
            n_estimators=120,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=15,
            random_state=self.random_state,
            verbose=-1,
        )

    def fit(self, train_df: pl.DataFrame, cal_df: pl.DataFrame) -> "ConformalQuantileForecaster":
        X_train = train_df.select(FEATURE_COLUMNS).to_numpy()
        y_train = train_df["quantity"].to_numpy()

        for q in (0.10, 0.50, 0.90):
            reg = self._make_regressor(q)
            reg.fit(X_train, y_train)
            self.models[q] = reg

        X_cal = cal_df.select(FEATURE_COLUMNS).to_numpy()
        y_cal = cal_df["quantity"].to_numpy()
        if len(y_cal) > 0:
            raw_q10 = self.models[0.10].predict(X_cal)
            raw_q90 = self.models[0.90].predict(X_cal)
            nonconformity = np.maximum(raw_q10 - y_cal, y_cal - raw_q90)
            n = len(nonconformity)
            level = min(1.0, np.ceil((1.0 - self.alpha) * (n + 1)) / n)
            self.conformal_q_hat = float(np.quantile(nonconformity, level))

        return self

    def predict(self, df: pl.DataFrame) -> QuantileForecast:
        X = df.select(FEATURE_COLUMNS).to_numpy()
        raw_q10 = self.models[0.10].predict(X)
        raw_q50 = np.maximum(0.0, self.models[0.50].predict(X))
        raw_q90 = self.models[0.90].predict(X)

        cal_q10 = np.maximum(0.0, raw_q10 - self.conformal_q_hat)
        cal_q90 = np.maximum(raw_q50, raw_q90 + self.conformal_q_hat)

        return QuantileForecast(
            q10=cal_q10,
            q50=raw_q50,
            q90=cal_q90,
            conformal_offset=self.conformal_q_hat,
            target_coverage=round(1.0 - self.alpha, 2),
        )
