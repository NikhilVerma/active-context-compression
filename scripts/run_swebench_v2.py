#!/usr/bin/env python3
"""
Run SWE-bench with optimized scaffold matching best practices.

Key improvements over v1:
- 2 tools only: bash (persistent) + str_replace_editor
- Better prompting: "use tools 100+ times", "implement tests first"
- Optional extended thinking for Claude models
- Higher step limits (200+)
- Haiku as default model

Usage:
    # Run with defaults (Haiku, N=5)
    uv run python scripts/run_swebench_v2.py

    # Run with extended thinking (Claude only)
    uv run python scripts/run_swebench_v2.py --extended-thinking

    # Run specific instances
    uv run python scripts/run_swebench_v2.py --instance-ids django__django-11039

    # Focus agent only
    uv run python scripts/run_swebench_v2.py --focus-only
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

# Load .env file if present
from dotenv import load_dotenv
load_dotenv()

# Check for required API key
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("Error: ANTHROPIC_API_KEY not set.")
    print("Please set it via:")
    print("  1. Environment variable: export ANTHROPIC_API_KEY=sk-ant-...")
    print("  2. Or create a .env file with: ANTHROPIC_API_KEY=sk-ant-...")
    sys.exit(1)

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from src.agents import SWEBenchAgent, SWEBenchFocusAgent
from src.benchmarks import load_swebench_lite, setup_swebench_workspace, get_task_prompt
from src.config import (
    DEFAULT_MODEL,
    DEFAULT_MAX_STEPS,
    DEFAULT_THINKING_BUDGET,
    get_docker_socket,
    setup_docker_env,
)


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
    max_steps: int,
    extended_thinking: bool,
    thinking_budget: int,
) -> tuple[str, dict, str | None]:
    """Run agent and extract the patch (git diff) it produces."""
    workspace = Path(tempfile.mkdtemp(prefix=f"swebench_{instance.instance_id}_"))

    try:
        # Setup workspace
        if not setup_swebench_workspace(instance, workspace):
            return "", {}, "Failed to setup workspace"

        # Create agent
        if agent_type == "baseline":
            agent = SWEBenchAgent(
                model=model,
                workspace=workspace,
                max_steps=max_steps,
                provider=provider,
                extended_thinking=extended_thinking,
                thinking_budget=thinking_budget,
            )
        else:
            agent = SWEBenchFocusAgent(
                model=model,
                workspace=workspace,
                max_steps=max_steps,
                provider=provider,
                extended_thinking=extended_thinking,
                thinking_budget=thinking_budget,
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
        except Exception:
            patch = ""

        return patch, result.metrics, None

    except Exception as e:
        import traceback
        return "", {}, f"{str(e)}\n{traceback.format_exc()}"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def run_agent_sync(args):
    """Synchronous wrapper for async agent run."""
    return asyncio.run(run_agent_for_patch(*args))


def print_summary(results: dict, agent_types: list[str], instances: list) -> None:
    """Print a summary table of results."""
    table = Table(title="Results Summary")
    table.add_column("Instance", style="cyan")
    
    for agent_type in agent_types:
        table.add_column(f"{agent_type.title()} Patch", justify="center")
        table.add_column(f"{agent_type.title()} Tokens", justify="right")
    
    for instance in instances:
        row = [instance.instance_id[:40]]
        for agent_type in agent_types:
            key = f"{instance.instance_id}_{agent_type}"
            if key in results:
                r = results[key]
                has_patch = "✓" if r["patch"] else "✗"
                tokens = r["metrics"].get("total_input_tokens", 0) + r["metrics"].get("total_output_tokens", 0)
                tokens_str = f"{tokens:,}"
                row.extend([has_patch, tokens_str])
            else:
                row.extend(["?", "?"])
        table.add_row(*row)
    
    console.print(table)


async def main():
    parser = argparse.ArgumentParser(
        description="Run SWE-bench with optimized scaffold (v2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument("--provider", default="anthropic")
    parser.add_argument(
        "--limit", type=int, default=5, help="Number of instances to run"
    )
    parser.add_argument("--instance-ids", nargs="+", help="Specific instance IDs")
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--max-workers", type=int, default=2, help="Parallel workers")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help=f"Max steps per run (default: {DEFAULT_MAX_STEPS})",
    )
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--focus-only", action="store_true")
    parser.add_argument(
        "--extended-thinking",
        action="store_true",
        help="Enable extended thinking (Claude models only, 128K budget)",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=DEFAULT_THINKING_BUDGET,
        help=f"Thinking budget tokens (default: {DEFAULT_THINKING_BUDGET})",
    )
    parser.add_argument("--skip-eval", action="store_true", help="Skip Docker evaluation")

    args = parser.parse_args()

    # Load instances
    console.print("[dim]Loading SWE-bench Lite dataset...[/dim]")
    instances = load_swebench_lite(limit=args.limit, instance_ids=args.instance_ids)

    if not instances:
        console.print("[red]No instances found![/red]")
        return

    console.print(f"\n[bold]SWE-bench v2 Run[/bold]")
    console.print(f"  Model: {args.model}")
    console.print(f"  Instances: {len(instances)}")
    console.print(f"  Max steps: {args.max_steps}")
    console.print(f"  Extended thinking: {args.extended_thinking}")
    console.print(f"  Workers: {args.max_workers}")

    # Determine agent types
    agent_types = []
    if not args.focus_only:
        agent_types.append("baseline")
    if not args.baseline_only:
        agent_types.append("focus")

    console.print(f"  Agents: {', '.join(agent_types)}")

    # Prepare all tasks
    tasks = []
    for instance in instances:
        for agent_type in agent_types:
            tasks.append((
                agent_type,
                instance,
                args.model,
                args.provider,
                args.max_steps,
                args.extended_thinking,
                args.thinking_budget,
            ))

    # Run agents
    results = {}
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
                task_args = future_to_task[future]
                agent_type, instance = task_args[0], task_args[1]
                try:
                    patch, metrics, error = future.result()

                    key = f"{instance.instance_id}_{agent_type}"
                    results[key] = {
                        "instance_id": instance.instance_id,
                        "agent_type": agent_type,
                        "model": args.model,
                        "patch": patch,
                        "metrics": metrics,
                        "error": error,
                    }

                    status = "✓" if patch else ("✗ " + (error[:30] if error else "no patch"))
                    progress.update(
                        main_task,
                        description=f"[{agent_type}] {instance.instance_id[:30]} {status}",
                    )
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")

                progress.advance(main_task)

    # Print summary
    console.print("\n")
    print_summary(results, agent_types, instances)

    # Save predictions
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for agent_type in agent_types:
        predictions = []
        for instance in instances:
            key = f"{instance.instance_id}_{agent_type}"
            if key in results:
                predictions.append({
                    "instance_id": instance.instance_id,
                    "model_name_or_path": f"{args.model}_{agent_type}_v2",
                    "model_patch": results[key]["patch"],
                })

        pred_file = args.output_dir / f"predictions_{agent_type}_v2_{timestamp}.json"
        pred_file.write_text(json.dumps(predictions, indent=2))
        console.print(f"[dim]Saved: {pred_file}[/dim]")

    # Save detailed metrics
    metrics_file = args.output_dir / f"metrics_v2_{timestamp}.json"
    metrics_file.write_text(json.dumps(results, indent=2, default=str))
    console.print(f"[dim]Saved: {metrics_file}[/dim]")

    if args.skip_eval:
        console.print("\n[yellow]Skipping Docker evaluation (--skip-eval)[/yellow]")
        return

    # Run official SWE-bench evaluation
    console.print("\n[bold]Phase 2: Running SWE-bench Docker evaluation...[/bold]")

    if not verify_docker():
        console.print("[red]Docker not available. Skipping evaluation.[/red]")
        return

    for agent_type in agent_types:
        pred_file = args.output_dir / f"predictions_{agent_type}_v2_{timestamp}.json"
        run_id = f"{agent_type}_v2_{timestamp}"

        console.print(f"\n[cyan]Evaluating {agent_type}...[/cyan]")

        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "swebench.harness.run_evaluation",
                    "--predictions_path", str(pred_file),
                    "--run_id", run_id,
                    "--max_workers", str(args.max_workers),
                    "--dataset_name", "princeton-nlp/SWE-bench_Lite",
                ],
                timeout=3600,
                env=os.environ,
            )
        except subprocess.TimeoutExpired:
            console.print("[red]Evaluation timed out![/red]")
        except FileNotFoundError:
            console.print("[red]swebench not installed! Run: uv add swebench[/red]")
        except Exception as e:
            console.print(f"[red]Evaluation failed: {e}[/red]")

    console.print("\n[bold green]Done![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
