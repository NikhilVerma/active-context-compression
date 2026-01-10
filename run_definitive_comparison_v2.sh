#!/bin/bash

# Source .env file to get API keys
if [ -f .env ]; then
  export $(cat .env | grep -v '^#' | xargs)
fi

# 5 instances we already tested
INSTANCES="mwaskom__seaborn-2848 pallets__flask-4045 psf__requests-2148 pylint-dev__pylint-5859 scikit-learn__scikit-learn-10297"
MODEL="claude-sonnet-4-5-20250929"

echo "Starting DEFINITIVE A/B Comparison v2 (Baseline vs Focus MODEL-CONTROLLED)"
echo "Running BOTH agents on the same 5 instances"
echo "Focus agent uses MODEL-CONTROLLED compression (steps-per-focus=0)"
echo ""

# Run with BOTH baseline and focus, MODEL CONTROLLED
uv run python scripts/run_swebench.py \
  --model $MODEL \
  --instance-ids $INSTANCES \
  --steps-per-focus 0 \
  --output-dir results/definitive_comparison_v2 \
  --max-workers 2 \
  > logs/definitive_comparison_v2.log 2>&1 &

echo "Run started in background (PID $!)"
echo "Check logs/definitive_comparison_v2.log for progress"
