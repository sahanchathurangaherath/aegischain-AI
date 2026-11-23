import numpy as np


def baseline_ma7(history: list[float] | np.ndarray, horizon: int = 14) -> np.ndarray:
    """Frozen 7-day moving average baseline (baseline_ma7)."""
    arr = np.asarray(history, dtype=float)
    if arr.size == 0:
        return np.zeros(horizon, dtype=float)
    avg = float(np.mean(arr[-7:])) if arr.size >= 7 else float(np.mean(arr))
    return np.full(horizon, max(0.0, avg), dtype=float)


def seasonal_naive(
    history: list[float] | np.ndarray,
    horizon: int = 14,
    season_length: int = 7,
) -> np.ndarray:
    """Weekly seasonal naive baseline repeating the last `season_length` observations."""
    arr = np.asarray(history, dtype=float)
    if arr.size == 0:
        return np.zeros(horizon, dtype=float)
    if arr.size < season_length:
        return baseline_ma7(arr, horizon)
    tail = arr[-season_length:]
    preds = [float(tail[i % season_length]) for i in range(horizon)]
    return np.maximum(0.0, np.asarray(preds, dtype=float))
