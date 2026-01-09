#!/bin/bash

# Source .env file to get API keys
if [ -f .env ]; then
  export $(cat .env | xargs)
fi

# 5 "Easier" Instances
INSTANCES="mwaskom__seaborn-2848 pallets__flask-4045 psf__requests-2148 pylint-dev__pylint-5859 scikit-learn__scikit-learn-10297"
# Using Sonnet 4.5
MODEL="claude-sonnet-4-5-20250929"

echo "Starting Sonnet 4.5 Sanity Check (Proper Docker Eval, Easy N=5): Focus 15"
# Note: Using the new canonical scripts/run_swebench.py which now supports --steps-per-focus
uv run python scripts/run_swebench.py --focus-only --steps-per-focus 15 --model $MODEL --output-dir results/sonnet_4_5_proper --instance-ids $INSTANCES > logs/sonnet_4_5_proper.log 2>&1 &

echo "Sonnet 4.5 PROPER run started in background. Check logs/sonnet_4_5_proper.log"
