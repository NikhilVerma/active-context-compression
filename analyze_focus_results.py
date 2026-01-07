#!/usr/bin/env python3
"""Quick analysis of focus benchmark results."""

import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent))

from src.metrics import BenchmarkResults, print_comparison_report
from src.metrics.tracker import RunMetrics

# Load the results file
results_file = Path("results/mini_focus_claude-haiku-4-5-20251001_2026-01-06T23-13-24.592728.json")
with open(results_file) as f:
    data = json.load(f)

# Create BenchmarkResults from the data
results = BenchmarkResults(
    benchmark_name=data["benchmark_name"],
    model=data["model"],
    timestamp=data["timestamp"],
    runs=[],
)

for run_data in data["runs"]:
    run = RunMetrics(
        problem_id=run_data["problem_id"],
        agent_type=run_data["agent_type"],
        model=run_data["model"],
        success=run_data["success"],
        error=run_data.get("error"),
        input_tokens=run_data["input_tokens"],
        output_tokens=run_data["output_tokens"],
        total_tokens=run_data["total_tokens"],
        llm_calls=run_data["llm_calls"],
        tool_calls=run_data["tool_calls"],
        wall_time_seconds=run_data["wall_time_seconds"],
        message_count=run_data["message_count"],
        compressions=run_data.get("compressions", run_data.get("time_travels", 0)),
        messages_dropped=run_data.get("messages_dropped", 0),
        timestamp=run_data["timestamp"],
        timestamp=run_data["timestamp"],
    )
    results.add_run(run)

# Print the report
print_comparison_report(results)
