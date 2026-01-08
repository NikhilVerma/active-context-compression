
import json
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

def analyze_results():
    console = Console()
    results_dir = Path("results")
    
    # Find most recent results for flask-5063
    baseline_files = sorted(results_dir.glob("*baseline*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    focus_files = sorted(results_dir.glob("*focus*.json"), key=lambda p: p.stat().st_mtime, reverse=True) # Note: script might name them differently depending on args
    
    # Actually the script saves files with timestamp. We just look for files containing "swebench_lite" and the model name
    all_files = sorted(results_dir.glob("swebench_lite_claude-sonnet-4-5*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not all_files:
        console.print("[red]No results found yet.[/red]")
        return

    console.print(f"[bold]Analyzing {len(all_files)} result files...[/bold]")
    
    table = Table(title="Benchmark Progress")
    table.add_column("Timestamp")
    table.add_column("Agent")
    table.add_column("Status")
    table.add_column("Tokens")
    table.add_column("Time (s)")
    table.add_column("Compressions")
    
    for p in all_files[:5]: # Show top 5 recent
        try:
            data = json.loads(p.read_text())
            runs = data.get("runs", [])
            for run in runs:
                agent = run.get("agent_type", "unknown")
                success = "✓" if run.get("success") else "✗"
                tokens = run.get("total_tokens", 0)
                time = run.get("wall_time_seconds", 0)
                compressions = run.get("compressions", 0)
                
                table.add_row(
                    data.get("timestamp", "")[:19],
                    agent,
                    success,
                    f"{tokens:,}",
                    f"{time:.1f}",
                    str(compressions)
                )
        except Exception as e:
            pass
            
    console.print(table)
    console.print("\n[dim]Run 'cat logs/baseline_flask.log' or 'cat logs/focus_flask.log' to see live output.[/dim]")

if __name__ == "__main__":
    analyze_results()
