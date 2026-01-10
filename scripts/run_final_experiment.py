#!/usr/bin/env python3
"""
Run final SWE-bench experiment with trajectory logging for paper.

This script:
1. Runs both Baseline and Focus agents on N=5 instances
2. Logs step-by-step trajectory data (for sawtooth visualization)
3. Saves predictions for Docker evaluation
4. Outputs comprehensive metrics with trajectory

Usage:
    export DOCKER_HOST=unix:///Users/nikhilverma/.orbstack/run/docker.sock
    uv run python scripts/run_final_experiment.py
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from src.agents import BaselineAgent, FocusAgent
from src.benchmarks import load_swebench_lite, setup_swebench_workspace, get_task_prompt
from src.tools import get_coding_tools


console = Console()

# The 5 instances we're evaluating
INSTANCE_IDS = [
    "mwaskom__seaborn-2848",
    "pallets__flask-4045",
    "psf__requests-2148",
    "pylint-dev__pylint-5859",
    "scikit-learn__scikit-learn-10297",
]

MODEL = "claude-haiku-4-5-20251001"
MAX_STEPS = 75


async def run_single_instance(agent_type: str, instance, model: str):
    """Run one agent on one instance and return results + trajectory."""
    workspace = Path(tempfile.mkdtemp(prefix=f"swebench_{instance.instance_id}_"))

    try:
        # Setup workspace
        setup_swebench_workspace(instance, workspace)

        # Create agent
        tools = get_coding_tools(workspace)
        if agent_type == "baseline":
            agent = BaselineAgent(
                model=model, tools=tools, max_steps=MAX_STEPS, provider="anthropic"
            )
        else:
            agent = FocusAgent(
                model=model, tools=tools, max_steps=MAX_STEPS, provider="anthropic", console=console
            )

        # Get task prompt
        task = get_task_prompt(instance)

        # Run agent
        console.print(f"\n[cyan]Running {agent_type} on {instance.instance_id}...[/cyan]")
        result = await agent.run(task, workspace)

        # Extract patch
        import subprocess

        patch_result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        patch = patch_result.stdout

        # Clean up workspace
        import shutil

        shutil.rmtree(workspace, ignore_errors=True)

        return {
            "instance_id": instance.instance_id,
            "agent_type": agent_type,
            "model": model,
            "success": result.success,
            "patch": patch,
            "metrics": result.metrics,
            "error": result.error,
        }

    except Exception as e:
        console.print(f"[red]Error on {instance.instance_id}: {e}[/red]")
        import traceback

        traceback.print_exc()
        return {
            "instance_id": instance.instance_id,
            "agent_type": agent_type,
            "model": model,
            "success": False,
            "patch": "",
            "metrics": {},
            "error": str(e),
        }


async def main():
    """Run the experiment."""
    console.print("[bold]Final SWE-bench Experiment[/bold]")
    console.print(f"Model: {MODEL}")
    console.print(f"Instances: {len(INSTANCE_IDS)}")
    console.print(f"Max steps: {MAX_STEPS}\n")

    # Load dataset
    console.print("Loading SWE-bench Lite...")
    instances = load_swebench_lite()

    # Filter to our 5 instances
    test_instances = [i for i in instances if i.instance_id in INSTANCE_IDS]
    console.print(f"Loaded {len(test_instances)} instances\n")

    all_results = []

    # Run baseline then focus for each instance
    for instance in test_instances:
        # Run baseline
        baseline_result = await run_single_instance("baseline", instance, MODEL)
        all_results.append(baseline_result)

        # Run focus
        focus_result = await run_single_instance("focus", instance, MODEL)
        all_results.append(focus_result)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = Path("results") / f"final_experiment_{timestamp}.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)

    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)

    console.print(f"\n[green]Results saved to {results_file}[/green]")

    # Generate predictions files
    baseline_preds = []
    focus_preds = []

    for result in all_results:
        pred = {
            "instance_id": result["instance_id"],
            "model_name_or_path": f"{MODEL}_{result['agent_type']}",
            "model_patch": result["patch"],
        }

        if result["agent_type"] == "baseline":
            baseline_preds.append(pred)
        else:
            focus_preds.append(pred)

    baseline_file = Path("results") / f"predictions_baseline_{timestamp}.json"
    focus_file = Path("results") / f"predictions_focus_{timestamp}.json"

    with open(baseline_file, "w") as f:
        json.dump(baseline_preds, f, indent=2)

    with open(focus_file, "w") as f:
        json.dump(focus_preds, f, indent=2)

    console.print(f"[green]Predictions saved:[/green]")
    console.print(f"  Baseline: {baseline_file}")
    console.print(f"  Focus: {focus_file}")

    # Print summary
    console.print("\n[bold]Summary:[/bold]")

    baseline_results = [r for r in all_results if r["agent_type"] == "baseline"]
    focus_results = [r for r in all_results if r["agent_type"] == "focus"]

    for agent_type, results in [("Baseline", baseline_results), ("Focus", focus_results)]:
        console.print(f"\n[cyan]{agent_type}:[/cyan]")

        total_tokens = sum(
            r["metrics"].get("total_input_tokens", 0) + r["metrics"].get("total_output_tokens", 0)
            for r in results
        )
        total_messages = sum(r["metrics"].get("message_count", 0) for r in results)
        total_compressions = sum(r["metrics"].get("compressions", 0) for r in results)

        console.print(f"  Avg tokens: {total_tokens / len(results):,.0f}")
        console.print(f"  Avg messages: {total_messages / len(results):.1f}")
        console.print(f"  Avg compressions: {total_compressions / len(results):.1f}")

    console.print(f"\n[yellow]Next steps:[/yellow]")
    console.print(f"1. Run Docker evaluation:")
    console.print(f"   export DOCKER_HOST=unix:///Users/nikhilverma/.orbstack/run/docker.sock")
    console.print(
        f"   python -m swebench.harness.run_evaluation --predictions_path {baseline_file} --run_id baseline_{timestamp} --max_workers 1"
    )
    console.print(
        f"   python -m swebench.harness.run_evaluation --predictions_path {focus_file} --run_id focus_{timestamp} --max_workers 1"
    )
    console.print(f"2. Generate sawtooth visualization:")
    console.print(f"   uv run python scripts/visualize_trajectory.py {results_file}")


if __name__ == "__main__":
    asyncio.run(main())
