#!/usr/bin/env python3
"""
Generate sawtooth visualization from trajectory data.

Usage:
    uv run python scripts/visualize_trajectory.py results/final_experiment_20260110_123456.json
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


def load_results(filepath):
    """Load results JSON."""
    with open(filepath) as f:
        return json.load(f)


def plot_sawtooth(results, output_path="sawtooth.png"):
    """Generate sawtooth plot showing message count over time."""

    # Find one good baseline and one good focus result with trajectories
    baseline_result = None
    focus_result = None

    for result in results:
        if result["agent_type"] == "baseline" and result["metrics"].get("trajectory"):
            if not baseline_result or len(result["metrics"]["trajectory"]) > len(
                baseline_result["metrics"]["trajectory"]
            ):
                baseline_result = result
        elif result["agent_type"] == "focus" and result["metrics"].get("trajectory"):
            if not focus_result or len(result["metrics"]["trajectory"]) > len(
                focus_result["metrics"]["trajectory"]
            ):
                focus_result = result

    if not baseline_result or not focus_result:
        print("Error: No results with trajectory data found")
        return

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot baseline (linear growth)
    baseline_traj = baseline_result["metrics"]["trajectory"]
    baseline_steps = [t["step"] for t in baseline_traj]
    baseline_messages = [t["message_count"] for t in baseline_traj]

    ax.plot(
        baseline_steps,
        baseline_messages,
        "r-o",
        linewidth=2,
        markersize=4,
        label="Baseline",
        alpha=0.7,
    )

    # Plot focus (sawtooth)
    focus_traj = focus_result["metrics"]["trajectory"]
    focus_steps = [t["step"] for t in focus_traj]
    focus_messages = [t["message_count"] for t in focus_traj]
    focus_compressions = [t["compressions_so_far"] for t in focus_traj]

    ax.plot(focus_steps, focus_messages, "b-o", linewidth=2, markersize=4, label="Focus", alpha=0.7)

    # Mark compression points (where compressions_so_far increases)
    compression_points = []
    prev_compressions = 0
    for i, t in enumerate(focus_traj):
        if t["compressions_so_far"] > prev_compressions:
            compression_points.append((t["step"], t["message_count"]))
            prev_compressions = t["compressions_so_far"]

    if compression_points:
        comp_x, comp_y = zip(*compression_points)
        ax.scatter(comp_x, comp_y, c="green", s=100, marker="v", label="Compression", zorder=5)

    # Labels and formatting
    ax.set_xlabel("Step", fontsize=12)
    ax.set_ylabel("Context Size (Messages)", fontsize=12)
    ax.set_title(
        "Context Growth: Baseline vs. Focus\n(Real Data from SWE-bench)",
        fontsize=14,
        fontweight="bold",
    )
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(True, alpha=0.3, linestyle="--")

    # Add instance ID as subtitle
    ax.text(
        0.5,
        0.97,
        f"Instance: {focus_result['instance_id']}",
        ha="center",
        va="top",
        transform=ax.transAxes,
        fontsize=10,
        style="italic",
        alpha=0.7,
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved visualization to {output_path}")

    # Also print some stats
    print(f"\nBaseline Stats:")
    print(f"  Final messages: {baseline_messages[-1]}")
    print(f"  Total steps: {len(baseline_steps)}")

    print(f"\nFocus Stats:")
    print(f"  Final messages: {focus_messages[-1]}")
    print(f"  Total steps: {len(focus_steps)}")
    print(f"  Compressions: {focus_traj[-1]['compressions_so_far']}")
    print(f"  Reduction: {(1 - focus_messages[-1] / baseline_messages[-1]) * 100:.1f}%")


def main():
    if len(sys.argv) < 2:
        print("Usage: python visualize_trajectory.py <results_file.json>")
        sys.exit(1)

    results_file = Path(sys.argv[1])
    if not results_file.exists():
        print(f"Error: {results_file} not found")
        sys.exit(1)

    results = load_results(results_file)
    output_path = results_file.parent / f"{results_file.stem}_sawtooth.png"

    plot_sawtooth(results, output_path)


if __name__ == "__main__":
    main()
