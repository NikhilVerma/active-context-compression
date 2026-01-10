#!/usr/bin/env python3
"""
Run SWE-bench Lite benchmark using the OFFICIAL SWE-bench evaluation harness.

This script:
1. Runs agents to generate patches (in parallel)
2. Saves patches in SWE-bench format
3. Calls the official SWE-bench evaluation harness (Docker-based)

Requirements:
- Docker installed and running (supports Docker Desktop and OrbStack)
- uv add swebench

Usage:
    # Run N=5 with Sonnet (default)
    uv run python scripts/run_swebench_proper.py --limit 5

    # Run N=10 with Haiku
    uv run python scripts/run_swebench_proper.py --model claude-haiku-4-5-20251001 --limit 10

    # Run specific instances
    uv run python scripts/run_swebench_proper.py --instance-ids django__django-11039 django__django-12284

    # Generate patches only (skip Docker evaluation)
    uv run python scripts/run_swebench_proper.py --skip-eval
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    get_docker_socket,
    setup_docker_env,
    DEFAULT_MODEL_SMART,
    DEFAULT_MAX_STEPS,
    DEFAULT_STEPS_PER_FOCUS,
    DEFAULT_MAX_WORKERS,
)

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from src.agents import BaselineAgent, FocusAgent
from src.benchmarks import load_swebench_lite, setup_swebench_workspace, get_task_prompt
from src.metrics import MetricsTracker
from src.tools import get_coding_tools


console = Console()


def verify_docker():
    """Verify Docker is available and configured."""
    if not setup_docker_env():
        console.print("[red]Docker socket not found![/red]")
        console.print("Please ensure Docker Desktop or OrbStack is running.")
        return False

    socket = get_docker_socket()

    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            timeout=10,
            env=os.environ,
        )
        if result.returncode != 0:
            console.print(f"[red]Docker not accessible: {result.stderr}[/red]")
            return False
        console.print(f"[dim]Docker socket: {socket}[/dim]")
        return True
    except Exception as e:
        console.print(f"[red]Docker error: {e}[/red]")
        return False


async def run_agent_for_patch(
    agent_type: str,
    instance,
    model: str,
    provider: str,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> tuple[str, dict, str | None]:
    """Run agent and extract the patch (git diff) it produces."""
    workspace = Path(tempfile.mkdtemp(prefix=f"swebench_{instance.instance_id}_"))

    try:
        # Setup workspace
        if not setup_swebench_workspace(instance, workspace):
            return "", {}, "Failed to setup workspace"

        # Create agent
        tools = get_coding_tools(workspace)
        if agent_type == "baseline":
            agent = BaselineAgent(
                model=model,
                tools=tools,
                provider=provider,
                max_steps=max_steps,
            )
        else:
            agent = FocusAgent(
                model=model,
                tools=tools,
                provider=provider,
                max_steps=max_steps,
                console=Console(quiet=True),
            )

        # Run agent
        task = get_task_prompt(instance)
        result = await agent.run(task, workspace)

        # Get the patch (git diff)
        try:
            diff_result = subprocess.run(
                ["git", "diff"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )
            patch = diff_result.stdout
        except Exception as e:
            patch = ""

        return patch, result.metrics, None

    except Exception as e:
        return "", {}, str(e)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def run_agent_sync(args):
    """Synchronous wrapper for async agent run."""
    agent_type, instance, model, provider, max_steps = args
    return asyncio.run(run_agent_for_patch(agent_type, instance, model, provider, max_steps))


async def main():
    parser = argparse.ArgumentParser(
        description="Run SWE-bench with official evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run N=5 with Sonnet (default)
  uv run python scripts/run_swebench_proper.py --limit 5

  # Run N=10 with Haiku (cheaper, tests if Focus helps weaker models)
  uv run python scripts/run_swebench_proper.py --model claude-haiku-4-5-20251001 --limit 10

  # Run specific instances
  uv run python scripts/run_swebench_proper.py --instance-ids django__django-11039

  # Generate patches only (skip Docker evaluation)
  uv run python scripts/run_swebench_proper.py --skip-eval
        """,
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_SMART,
        help=f"Model to use (default: {DEFAULT_MODEL_SMART})",
    )
    parser.add_argument("--provider", default="anthropic")
    parser.add_argument(
        "--limit", type=int, default=5, help="Number of instances to run (default: 5)"
    )
    parser.add_argument("--instance-ids", nargs="+", help="Specific instance IDs to run")
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"Parallel workers (default: {DEFAULT_MAX_WORKERS})",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help=f"Max steps per agent run (default: {DEFAULT_MAX_STEPS})",
    )
    parser.add_argument("--baseline-only", action="store_true", help="Only run baseline agent")
    parser.add_argument("--focus-only", action="store_true", help="Only run focus agent")
    parser.add_argument(
        "--steps-per-focus",
        type=int,
        default=DEFAULT_STEPS_PER_FOCUS,
        help="Number of steps before auto-completing focus (default: 15)",
    )
    parser.add_argument(
        "--skip-eval", action="store_true", help="Skip Docker evaluation (just generate patches)"
    )

    args = parser.parse_args()

    # Load instances
    console.print("[dim]Loading SWE-bench Lite dataset...[/dim]")
    instances = load_swebench_lite(limit=args.limit, instance_ids=args.instance_ids)

    if not instances:
        console.print("[red]No instances found![/red]")
        return

    console.print(f"[bold]Running {len(instances)} instances with {args.model}[/bold]")
    console.print(f"[dim]Max workers: {args.max_workers}[/dim]")

    # Determine agent types
    agent_types = []
    if not args.focus_only:
        agent_types.append("baseline")
    if not args.baseline_only:
        agent_types.append("focus")

    # Prepare all tasks
    tasks = []
    for instance in instances:
        for agent_type in agent_types:
            tasks.append((agent_type, instance, args.model, args.provider, args.max_steps))

    # Run agents in parallel
    results = {}
    tracker = MetricsTracker(benchmark_name="swebench_lite", model=args.model)

    console.print(f"\n[bold]Phase 1: Generating patches ({len(tasks)} runs)...[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        main_task = progress.add_task("Running agents...", total=len(tasks))

        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_task = {executor.submit(run_agent_sync, task): task for task in tasks}

            for future in as_completed(future_to_task):
                agent_type, instance, model, provider, max_steps = future_to_task[future]
                try:
                    patch, metrics, error = future.result()

                    # Store result
                    key = f"{instance.instance_id}_{agent_type}"
                    results[key] = {
                        "instance_id": instance.instance_id,
                        "agent_type": agent_type,
                        "model": model,
                        "patch": patch,
                        "metrics": metrics,
                        "error": error,
                    }

                    # Record metrics
                    tracker.record_run(
                        problem_id=instance.instance_id,
                        agent_type=agent_type,
                        success=0.0,  # Will be updated after evaluation
                        metrics=metrics,
                        error=error,
                    )

                    status = "✓" if patch else "✗"
                    progress.update(
                        main_task,
                        description=f"[{agent_type}] {instance.instance_id[:30]} {status}",
                    )
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")

                progress.advance(main_task)

    # Save patches in SWE-bench format
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for agent_type in agent_types:
        predictions = []
        for instance in instances:
            key = f"{instance.instance_id}_{agent_type}"
            if key in results:
                predictions.append(
                    {
                        "instance_id": instance.instance_id,
                        "model_name_or_path": f"{args.model}_{agent_type}",
                        "model_patch": results[key]["patch"],
                    }
                )

        pred_file = args.output_dir / f"predictions_{agent_type}_{timestamp}.json"
        pred_file.parent.mkdir(parents=True, exist_ok=True)
        pred_file.write_text(json.dumps(predictions, indent=2))
        console.print(f"[dim]Saved predictions to {pred_file}[/dim]")

    # Save metrics
    metrics_file = tracker.save(args.output_dir)
    console.print(f"[dim]Saved metrics to {metrics_file}[/dim]")

    if args.skip_eval:
        console.print("\n[yellow]Skipping Docker evaluation (--skip-eval)[/yellow]")
        console.print("To evaluate, run:")
        for agent_type in agent_types:
            pred_file = args.output_dir / f"predictions_{agent_type}_{timestamp}.json"
            console.print(f"  python -m swebench.harness.run_evaluation \\")
            console.print(f"    --predictions_path {pred_file} \\")
            console.print(f"    --run_id {agent_type}_{timestamp} \\")
            console.print(f"    --max_workers {args.max_workers}")
        return

    # Run official SWE-bench evaluation
    console.print("\n[bold]Phase 2: Running official SWE-bench evaluation...[/bold]")

    if not verify_docker():
        console.print("[red]Docker not available. Skipping evaluation.[/red]")
        console.print("Run evaluation manually with:")
        for agent_type in agent_types:
            pred_file = args.output_dir / f"predictions_{agent_type}_{timestamp}.json"
            console.print(
                f"  python -m swebench.harness.run_evaluation --predictions_path {pred_file} --run_id {agent_type}_{timestamp}"
            )
        return

    eval_results = {}

    for agent_type in agent_types:
        pred_file = args.output_dir / f"predictions_{agent_type}_{timestamp}.json"
        run_id = f"{agent_type}_{timestamp}"

        console.print(f"\n[cyan]Evaluating {agent_type} agent...[/cyan]")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "swebench.harness.run_evaluation",
                    "--predictions_path",
                    str(pred_file),
                    "--run_id",
                    run_id,
                    "--max_workers",
                    str(args.max_workers),
                    "--dataset_name",
                    "princeton-nlp/SWE-bench_Lite",
                ],
                capture_output=False,  # Show output in real-time
                timeout=3600,  # 1 hour timeout
                env=os.environ,  # Pass Docker socket env
            )
            eval_results[agent_type] = result.returncode == 0
        except subprocess.TimeoutExpired:
            console.print("[red]Evaluation timed out![/red]")
            eval_results[agent_type] = False
        except FileNotFoundError:
            console.print("[red]swebench not installed! Run: uv add swebench[/red]")
            eval_results[agent_type] = False
        except Exception as e:
            console.print(f"[red]Evaluation failed: {e}[/red]")
            eval_results[agent_type] = False

    # Print summary
    console.print("\n[bold]Evaluation Summary:[/bold]")
    for agent_type, success in eval_results.items():
        status = "[green]✓[/green]" if success else "[red]✗[/red]"
        console.print(f"  {agent_type}: {status}")

    # Point to results
    console.print(f"\n[dim]Results saved in: logs/run_evaluation/{timestamp}/[/dim]")
    console.print("\n[bold green]Done![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
