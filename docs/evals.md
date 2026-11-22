# System 2 Evaluation & Memory Ablation Log

## Evaluation Metrics & Regression Gate

Defined in `aegis_ai/tests/evals/scenarios.yaml` and enforced by `.github/workflows/eval.yml`:

- **Tool-Selection Accuracy Gate:** `>= 0.85`
- **Citation Rate Gate:** `>= 0.90`
- **Write Safety Invariant:** `0` direct write executions inside the agent loop (all writes must return `proposed=True, executed=False`).

## How to Run Locally

```powershell
cd aegis_ai
# Offline deterministic replay gate
uv run python tests/evals/runner.py

# Live Gemini evaluation
uv run python tests/evals/runner.py --live

# Memory ablation runs
uv run python tests/evals/runner.py --live --ablate episodic
uv run python tests/evals/runner.py --live --ablate semantic
uv run python tests/evals/runner.py --live --ablate entity
```

## Memory Ablation Results

| Run | Tool-Selection Accuracy | Write-Proposal Accuracy | Citation Rate | Avg Cost / Case (USD) | p95 Latency (ms) |
| --- | --- | --- | --- | --- | --- |
| All memory on | TBD (run `--live`) | TBD | TBD | TBD | TBD |
| No episodic (`--ablate episodic`) | TBD | TBD | TBD | TBD | TBD |
| No semantic (`--ablate semantic`) | TBD | TBD | TBD | TBD | TBD |
| No entity (`--ablate entity`) | TBD | TBD | TBD | TBD | TBD |
