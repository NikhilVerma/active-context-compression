#!/usr/bin/env python3
"""Analyze and compare benchmark results."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console

from src.metrics import BenchmarkResults, generate_markdown_report, load_and_compare


def main():
    parser = argparse.ArgumentParser(description="Analyze benchmark results")
    parser.add_argument(
        "results_dir",
        type=Path,
        nargs="?",
        default=Path("results"),
        help="Directory containing results JSON files (default: results/)",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Generate markdown report",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for markdown report",
    )

    args = parser.parse_args()
    console = Console()

    if not args.results_dir.exists():
        console.print(f"[red]Results directory not found: {args.results_dir}[/red]")
        return

    json_files = list(args.results_dir.glob("*.json"))
    if not json_files:
        console.print(f"[yellow]No results found in {args.results_dir}[/yellow]")
        return

    if args.markdown:
        # Generate markdown report for all results
        reports = []
        for json_file in sorted(json_files):
            results = BenchmarkResults.load(json_file)
            reports.append(generate_markdown_report(results))

        full_report = "\n\n---\n\n".join(reports)

        if args.output:
            args.output.write_text(full_report)
            console.print(f"[green]Markdown report saved to {args.output}[/green]")
        else:
            console.print(full_report)
    else:
        # Print comparison report
        load_and_compare(args.results_dir)


if __name__ == "__main__":
    main()
