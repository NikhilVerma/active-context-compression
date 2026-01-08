#!/usr/bin/env python3
"""Run the mini benchmark comparing baseline vs focus agents."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.agents import BaselineAgent, FocusAgent
from src.benchmarks import (
    cleanup_workspace,
    create_workspace_for_problem,
    get_mini_benchmark,
)
from src.metrics import MetricsTracker, print_comparison_report
from src.tools import get_coding_tools


async def run_problem(
    agent_type: str,
    problem,
    model: str,
    provider: str,
    console: Console,
) -> tuple[bool, dict]:
    """Run a single problem with an agent."""
    workspace = create_workspace_for_problem(problem)

    try:
        # Create tools for this workspace
        tools = get_coding_tools(workspace)

        # Create the appropriate agent
        if agent_type == "baseline":
            agent = BaselineAgent(
                model=model,
                tools=tools,
                provider=provider,
            )
        else:
            agent = FocusAgent(
                model=model,
                tools=tools,
                provider=provider,
                auto_focus=True,
                steps_per_focus=15,
                console=console,
            )

        # Run the agent
        result = await agent.run(problem.task, workspace)

        # Check if the solution is correct
        solution_correct = problem.check_solution(workspace, result.output)

        return solution_correct, result.metrics

    finally:
        cleanup_workspace(workspace)


async def main():
    parser = argparse.ArgumentParser(description="Run mini benchmark")
    parser.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="Model to use (default: claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "openai"],
        help="API provider (default: anthropic)",
    )
    parser.add_argument(
        "--problems",
        nargs="+",
        help="Specific problem IDs to run (default: all)",
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
        "--focus-only",
        action="store_true",
        help="Only run focus agent",
    )

    args = parser.parse_args()
    console = Console()

    # Get problems
    problems = get_mini_benchmark()
    if args.problems:
        problems = [p for p in problems if p.id in args.problems]

    if not problems:
        console.print("[red]No problems to run![/red]")
        return

    console.print(f"[bold]Running {len(problems)} problems with model {args.model}[/bold]")
    console.print()

    # Determine which agents to run
    agent_types = []
    if not args.focus_only:
        agent_types.append("baseline")
    if not args.baseline_only:
        agent_types.append("focus")

    # Initialize metrics tracker
    tracker = MetricsTracker(benchmark_name="mini", model=args.model)

    # Run each problem with each agent type
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for problem in problems:
            for agent_type in agent_types:
                task_desc = f"[{agent_type}] {problem.name}"
                task = progress.add_task(task_desc, total=None)

                try:
                    success, metrics = await run_problem(
                        agent_type=agent_type,
                        problem=problem,
                        model=args.model,
                        provider=args.provider,
                        console=console,
                    )

                    tracker.record_run(
                        problem_id=problem.id,
                        agent_type=agent_type,
                        success=success,
                        metrics=metrics,
                    )

                    status = "[green]✓[/green]" if success else "[red]✗[/red]"
                    progress.update(task, description=f"{task_desc} {status}")

                except Exception as e:
                    console.print(f"[red]Error running {problem.id} with {agent_type}: {e}[/red]")
                    tracker.record_run(
                        problem_id=problem.id,
                        agent_type=agent_type,
                        success=False,
                        metrics={},
                        error=str(e),
                    )

                progress.remove_task(task)

    # Save results
    output_path = tracker.save(args.output_dir)
    console.print(f"\n[dim]Results saved to {output_path}[/dim]")

    # Print comparison report
    print_comparison_report(tracker.results)


if __name__ == "__main__":
    asyncio.run(main())
