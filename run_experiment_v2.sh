#!/bin/bash
# Run the v2 SWE-bench experiment with Haiku
#
# This script matches Anthropic's best-practice scaffold:
# - 2 tools: bash (persistent) + str_replace_editor
# - Better prompting: "use tools 100+ times", "implement tests first"
# - 200 max steps
# - Haiku model by default
#
# Usage:
#   ./run_experiment_v2.sh                    # Run with defaults (5 instances, both agents)
#   ./run_experiment_v2.sh --limit 10         # Run 10 instances
#   ./run_experiment_v2.sh --extended-thinking # Enable extended thinking (Claude only)
#   ./run_experiment_v2.sh --focus-only       # Only run Focus agent

set -e

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY not set"
    echo ""
    echo "Please set it via:"
    echo "  export ANTHROPIC_API_KEY=sk-ant-..."
    echo "  or create a .env file with: ANTHROPIC_API_KEY=sk-ant-..."
    exit 1
fi

echo "=== SWE-bench v2 Experiment ==="
echo "Model: Claude Haiku 4.5"
echo "Tools: bash + str_replace_editor"
echo "Max steps: 200"
echo ""

uv run python scripts/run_swebench_v2.py "$@"
