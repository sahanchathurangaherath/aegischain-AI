import numpy as np


def compute_psi(
    reference: np.ndarray,
    current: np.ndarray,
    bins: int = 10,
    eps: float = 1e-6,
) -> float:
    """
    Compute Population Stability Index (PSI) between reference and current distributions.
      PSI < 0.10 : no significant shift
      0.10-0.20  : moderate shift
      PSI >= 0.20: significant drift (triggers alert / retraining)
    """
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    if ref.size == 0 or cur.size == 0:
        return 0.0

    quantiles = np.linspace(0.0, 1.0, bins + 1)
    edges = np.unique(np.quantile(ref, quantiles))
    if edges.size < 2:
        return 0.0

    ref_counts, _ = np.histogram(ref, bins=edges)
    cur_counts, _ = np.histogram(cur, bins=edges)

    ref_pct = np.clip(ref_counts / max(1, ref.size), eps, 1.0)
    cur_pct = np.clip(cur_counts / max(1, cur.size), eps, 1.0)

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return round(max(0.0, psi), 4)


def check_feature_drift(
    reference: np.ndarray,
    current: np.ndarray,
    threshold: float = 0.20,
) -> dict[str, object]:
    psi = compute_psi(reference, current)
    return {
        "psi": psi,
        "threshold": threshold,
        "drift_detected": psi >= threshold,
    }
