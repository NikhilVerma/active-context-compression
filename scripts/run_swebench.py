#!/usr/bin/env python3
"""Run SWE-bench Lite benchmark comparing baseline vs time travel agents."""

import argparse
import asyncio
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from src.agents import BaselineAgent, TimeTravelAgent
from src.benchmarks import (
    load_swebench_lite,
    setup_swebench_workspace,
    check_swebench_solution,
    get_task_prompt,
)
from src.metrics import MetricsTracker, print_comparison_report
from src.tools import get_coding_tools


async def run_instance(
    agent_type: str,
    instance,
    model: str,
    provider: str,
) -> tuple[bool, dict, str | None]:
    """Run a single SWE-bench instance with an agent."""
    # Create temporary workspace
    workspace = Path(tempfile.mkdtemp(prefix=f"swebench_{instance.instance_id}_"))

    try:
        # Setup the workspace (clone repo, checkout commit)
        if not setup_swebench_workspace(instance, workspace):
            return False, {}, "Failed to setup workspace"

        # Create tools for this workspace
        tools = get_coding_tools(workspace)

        # Create the appropriate agent
        if agent_type == "baseline":
            agent = BaselineAgent(
                model=model,
                tools=tools,
                provider=provider,
                max_steps=75,  # SWE-bench problems are harder
            )
        else:
            agent = TimeTravelAgent(
                model=model,
                tools=tools,
                provider=provider,
                max_steps=75,
            )

        # Get the task prompt
        task = get_task_prompt(instance)

        # Run the agent
        result = await agent.run(task, workspace)

        # Check if the solution passes tests
        solution_correct = check_swebench_solution(instance, workspace)

        return solution_correct, result.metrics, None

    except Exception as e:
        return False, {}, str(e)

    finally:
        shutil.rmtree(workspace, ignore_errors=True)


async def main():
    parser = argparse.ArgumentParser(description="Run SWE-bench Lite benchmark")
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Model to use (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "openai"],
        help="API provider (default: anthropic)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of instances to run (default: 10)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory to save results (default: results/)",
    )
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="Only run baseline agent",
    )
    parser.add_argument(
        "--time-travel-only",
        action="store_true",
        help="Only run time travel agent",
    )
    parser.add_argument(
        "--instance-ids",
        nargs="+",
        help="Specific instance IDs to run",
    )

    args = parser.parse_args()
    console = Console()

    # Load SWE-bench Lite
    console.print("[dim]Loading SWE-bench Lite dataset...[/dim]")
    instances = load_swebench_lite(limit=args.limit)

    if args.instance_ids:
        instances = [i for i in instances if i.instance_id in args.instance_ids]

    if not instances:
        console.print("[red]No instances to run![/red]")
        return

    console.print(f"[bold]Running {len(instances)} SWE-bench instances with model {args.model}[/bold]")
    console.print()

    # Determine which agents to run
    agent_types = []
    if not args.time_travel_only:
        agent_types.append("baseline")
    if not args.baseline_only:
        agent_types.append("time_travel")

    # Initialize metrics tracker
    tracker = MetricsTracker(benchmark_name="swebench_lite", model=args.model)

    # Run each instance with each agent type
    total_runs = len(instances) * len(agent_types)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        main_task = progress.add_task("Running benchmark...", total=total_runs)

        for instance in instances:
            for agent_type in agent_types:
                short_id = instance.instance_id.split("__")[-1][:30]
                progress.update(main_task, description=f"[{agent_type}] {short_id}")

                try:
                    success, metrics, error = await run_instance(
                        agent_type=agent_type,
                        instance=instance,
                        model=args.model,
                        provider=args.provider,
                    )

                    tracker.record_run(
                        problem_id=instance.instance_id,
                        agent_type=agent_type,
                        success=success,
                        metrics=metrics,
                        error=error,
                    )

                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    tracker.record_run(
                        problem_id=instance.instance_id,
                        agent_type=agent_type,
                        success=False,
                        metrics={},
                        error=str(e),
                    )

                progress.advance(main_task)

    # Save results
    output_path = tracker.save(args.output_dir)
    console.print(f"\n[dim]Results saved to {output_path}[/dim]")

    # Print comparison report
    print_comparison_report(tracker.results)


if __name__ == "__main__":
    asyncio.run(main())
