#!/bin/bash
# Run N=50 SWE-bench Lite benchmark with Haiku 4.5
# This compares baseline vs focus agents

set -e

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY is not set"
    echo "Please run: export ANTHROPIC_API_KEY=your_key_here"
    exit 1
fi

# Create logs directory
mkdir -p logs

# Timestamp for log file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="logs/n50_benchmark_${TIMESTAMP}.log"

echo "Starting N=50 SWE-bench benchmark..."
echo "Model: claude-haiku-4-5-20251001"
echo "Log file: ${LOG_FILE}"
echo ""
echo "This will take several hours. You can monitor progress with:"
echo "  tail -f ${LOG_FILE}"
echo ""

# Run the benchmark
uv run python scripts/run_swebench.py \
    --model claude-haiku-4-5-20251001 \
    --limit 50 \
    --output-dir results \
    2>&1 | tee "${LOG_FILE}"

echo ""
echo "Benchmark complete! Results saved to results/"
echo "Log saved to ${LOG_FILE}"
