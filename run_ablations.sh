#!/bin/bash

# Source .env file to get API keys
if [ -f .env ]; then
  export $(cat .env | xargs)
fi

INSTANCES="django__django-10914 django__django-10924 pallets__flask-4045 psf__requests-2148 scikit-learn__scikit-learn-10297 scikit-learn__scikit-learn-10508 sympy__sympy-11400 sympy__sympy-11870 pytest-dev__pytest-11143 matplotlib__matplotlib-22711"
MODEL="claude-haiku-4-5-20251001"

echo "Starting Ablation: Focus 15"
uv run python scripts/run_swebench.py --focus-only --steps-per-focus 15 --model $MODEL --output-dir results/ablation_15 --instance-ids $INSTANCES > logs/ablation_15.log 2>&1 &

echo "Starting Ablation: Focus 30"
uv run python scripts/run_swebench.py --focus-only --steps-per-focus 30 --model $MODEL --output-dir results/ablation_30 --instance-ids $INSTANCES > logs/ablation_30.log 2>&1 &

echo "Starting Ablation: Auto Focus"
uv run python scripts/run_swebench.py --focus-only --steps-per-focus 0 --model $MODEL --output-dir results/ablation_auto --instance-ids $INSTANCES > logs/ablation_auto.log 2>&1 &

echo "All ablations started in background. Check logs/ablation_*.log for progress."
