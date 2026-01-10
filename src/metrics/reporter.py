"""Metrics reporting and visualization."""

from pathlib import Path

from rich.console import Console
from rich.table import Table

from .tracker import BenchmarkResults


def print_comparison_report(results: BenchmarkResults) -> None:
    """Print a comparison report to the console."""
    console = Console()

    summary = results.calculate_summary()
    baseline = summary.get("baseline", {})
    focus = summary.get("focus", {})
    deltas = summary.get("deltas", {})

    # Header
    console.print()
    console.print(f"[bold blue]Benchmark Results: {results.benchmark_name}[/bold blue]")
    console.print(f"Model: {results.model}")
    console.print(f"Timestamp: {results.timestamp}")
    console.print()

    # Main comparison table
    table = Table(title="Agent Comparison")
    table.add_column("Metric", style="cyan")
    table.add_column("Baseline", justify="right")
    table.add_column("Focus", justify="right")
    table.add_column("Delta", justify="right")

    def format_delta(key: str) -> str:
        delta_key = f"{key}_delta_pct"
        if delta_key in deltas:
            val = deltas[delta_key]
            color = "green" if val < 0 else "red"
            # For success rate, higher is better
            if "success" in key:
                color = "green" if val > 0 else "red"
            return f"[{color}]{val:+.1f}%[/{color}]"
        return "-"

    def format_value(val: float, fmt: str = ".1f") -> str:
        if isinstance(val, float):
            return f"{val:{fmt}}"
        return str(val)

    # Success rate
    table.add_row(
        "Success Rate",
        f"{baseline.get('success_rate', 0) * 100:.1f}%",
        f"{focus.get('success_rate', 0) * 100:.1f}%",
        format_delta("success_rate"),
    )

    # Token usage
    table.add_row(
        "Avg Total Tokens",
        format_value(baseline.get("avg_total_tokens", 0), ",.0f"),
        format_value(focus.get("avg_total_tokens", 0), ",.0f"),
        format_delta("avg_total_tokens"),
    )

    # LLM calls
    table.add_row(
        "Avg LLM Calls",
        format_value(baseline.get("avg_llm_calls", 0)),
        format_value(focus.get("avg_llm_calls", 0)),
        format_delta("avg_llm_calls"),
    )

    # Tool calls
    table.add_row(
        "Avg Tool Calls",
        format_value(baseline.get("avg_tool_calls", 0)),
        format_value(focus.get("avg_tool_calls", 0)),
        "-",
    )

    # Wall time
    table.add_row(
        "Avg Wall Time (s)",
        format_value(baseline.get("avg_wall_time", 0)),
        format_value(focus.get("avg_wall_time", 0)),
        format_delta("avg_wall_time"),
    )

    # Message count
    table.add_row(
        "Avg Messages",
        format_value(baseline.get("avg_message_count", 0)),
        format_value(focus.get("avg_message_count", 0)),
        "-",
    )

    console.print(table)

    # Focus-specific metrics
    if focus:
        console.print()
        focus_table = Table(title="Focus Agent Metrics")
        focus_table.add_column("Metric", style="cyan")
        focus_table.add_column("Value", justify="right")

        focus_table.add_row(
            "Avg Compressions per Run",
            format_value(focus.get("avg_compressions", 0)),
        )
        focus_table.add_row(
            "Avg Messages Dropped per Run",
            format_value(focus.get("avg_messages_dropped", 0)),
        )

        console.print(focus_table)

    # Per-problem breakdown
    console.print()
    problems_table = Table(title="Per-Problem Results")
    problems_table.add_column("Problem", style="cyan")
    problems_table.add_column("Baseline", justify="center")
    problems_table.add_column("Focus", justify="center")

    # Group by problem
    problem_ids = set(r.problem_id for r in results.runs)
    for problem_id in sorted(problem_ids):
        baseline_runs = [
            r for r in results.runs if r.problem_id == problem_id and r.agent_type == "baseline"
        ]
        focus_runs = [
            r for r in results.runs if r.problem_id == problem_id and r.agent_type == "focus"
        ]

        baseline_status = (
            "[green]✓[/green]" if any(r.success for r in baseline_runs) else "[red]✗[/red]"
        )
        focus_status = "[green]✓[/green]" if any(r.success for r in focus_runs) else "[red]✗[/red]"

        problems_table.add_row(problem_id, baseline_status, focus_status)

    console.print(problems_table)
    console.print()


def generate_markdown_report(results: BenchmarkResults) -> str:
    """Generate a markdown report."""
    summary = results.calculate_summary()
    baseline = summary.get("baseline", {})
    focus = summary.get("focus", {})
    deltas = summary.get("deltas", {})

    lines = [
        f"# Benchmark Results: {results.benchmark_name}",
        "",
        f"**Model:** {results.model}",
        f"**Timestamp:** {results.timestamp}",
        "",
        "## Summary",
        "",
        "| Metric | Baseline | Focus | Delta |",
        "|--------|----------|-------|-------|",
    ]

    def format_delta(key: str) -> str:
        delta_key = f"{key}_delta_pct"
        if delta_key in deltas:
            val = deltas[delta_key]
            return f"{val:+.1f}%"
        return "-"

    lines.append(
        f"| Success Rate | {baseline.get('success_rate', 0) * 100:.1f}% | "
        f"{focus.get('success_rate', 0) * 100:.1f}% | {format_delta('success_rate')} |"
    )
    lines.append(
        f"| Avg Total Tokens | {baseline.get('avg_total_tokens', 0):,.0f} | "
        f"{focus.get('avg_total_tokens', 0):,.0f} | {format_delta('avg_total_tokens')} |"
    )
    lines.append(
        f"| Avg LLM Calls | {baseline.get('avg_llm_calls', 0):.1f} | "
        f"{focus.get('avg_llm_calls', 0):.1f} | {format_delta('avg_llm_calls')} |"
    )
    lines.append(
        f"| Avg Wall Time (s) | {baseline.get('avg_wall_time', 0):.1f} | "
        f"{focus.get('avg_wall_time', 0):.1f} | {format_delta('avg_wall_time')} |"
    )

    lines.extend(
        [
            "",
            "## Focus Agent Metrics",
            "",
            f"- Avg Compressions per Run: {focus.get('avg_compressions', 0):.1f}",
            f"- Avg Messages Dropped per Run: {focus.get('avg_messages_dropped', 0):.1f}",
            "",
        ]
    )

    return "\n".join(lines)


def load_and_compare(results_dir: Path) -> None:
    """Load all results from a directory and print comparison."""
    console = Console()

    json_files = list(results_dir.glob("*.json"))
    if not json_files:
        console.print(f"[red]No results found in {results_dir}[/red]")
        return

    for json_file in sorted(json_files):
        console.print(f"[dim]Loading {json_file.name}...[/dim]")
        results = BenchmarkResults.load(json_file)
        print_comparison_report(results)
