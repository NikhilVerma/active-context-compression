# Benchmark Artifacts

This directory contains the raw logs and metric files from our experiments.

## Logs (`logs/raw/`)
*   `haiku_suite_n10.log`: The full N=10 run using Claude Haiku, showing the -57% token reduction.
*   `sonnet_triple_green.log`: The run where Claude Sonnet successfully solved `pallets/flask-5063`.

## Metrics (`results/metrics/`)
*   `haiku_n10_summary.json`: Aggregate statistics for the N=10 run.
*   `sonnet_flask_success.json`: Metrics for the successful Flask run showing Focus efficiency.

## How to Verify
You can reproduce these results by running:
```bash
# Install dependencies
uv sync

# Run the benchmark (warning: costs API credits)
uv run scripts/run_swebench.py --limit 10 --model claude-haiku-4-5-20251001
```
