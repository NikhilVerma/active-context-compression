"""Metrics tracking for benchmark runs."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RunMetrics:
    """Metrics for a single agent run."""

    problem_id: str
    agent_type: str  # "baseline" or "focus"
    model: str
    success: float  # Changed from bool to float (0.0 - 1.0)
    error: str | None = None

    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Execution metrics
    llm_calls: int = 0
    tool_calls: int = 0
    wall_time_seconds: float = 0.0
    message_count: int = 0

    # Focus-specific metrics
    compressions: int = 0
    messages_dropped: int = 0
    knowledge_entries: int = 0

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class BenchmarkResults:
    """Aggregated results for a benchmark run."""

    benchmark_name: str
    model: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    runs: list[RunMetrics] = field(default_factory=list)

    def add_run(self, run: RunMetrics) -> None:
        """Add a run to the results."""
        self.runs.append(run)

    def get_baseline_runs(self) -> list[RunMetrics]:
        """Get all baseline runs."""
        return [r for r in self.runs if r.agent_type == "baseline"]

    def get_focus_runs(self) -> list[RunMetrics]:
        """Get all focus runs."""
        return [r for r in self.runs if r.agent_type == "focus"]

    def calculate_summary(self) -> dict[str, Any]:
        """Calculate summary statistics."""
        baseline = self.get_baseline_runs()
        focus = self.get_focus_runs()

        def summarize(runs: list[RunMetrics]) -> dict[str, Any]:
            if not runs:
                return {}

            # success is now a float (0.0 to 1.0)
            avg_success = sum(r.success for r in runs) / len(runs)

            return {
                "count": len(runs),
                "success_rate": avg_success,
                "avg_input_tokens": sum(r.input_tokens for r in runs) / len(runs),
                "avg_output_tokens": sum(r.output_tokens for r in runs) / len(runs),
                "avg_total_tokens": sum(r.total_tokens for r in runs) / len(runs),
                "avg_llm_calls": sum(r.llm_calls for r in runs) / len(runs),
                "avg_tool_calls": sum(r.tool_calls for r in runs) / len(runs),
                "avg_wall_time": sum(r.wall_time_seconds for r in runs) / len(runs),
                "avg_message_count": sum(r.message_count for r in runs) / len(runs),
            }

        baseline_summary = summarize(baseline)
        focus_summary = summarize(focus)

        # Add focus-specific metrics
        if focus:
            focus_summary["avg_compressions"] = sum(r.compressions for r in focus) / len(focus)
            focus_summary["avg_messages_dropped"] = sum(r.messages_dropped for r in focus) / len(
                focus
            )
            focus_summary["avg_knowledge_entries"] = sum(
                getattr(r, "knowledge_entries", 0) for r in focus
            ) / len(focus)

        # Calculate deltas
        deltas = {}
        if baseline_summary and focus_summary:
            for key in ["success_rate", "avg_total_tokens", "avg_llm_calls", "avg_wall_time"]:
                if key in baseline_summary and key in focus_summary:
                    baseline_val = baseline_summary[key]
                    focus_val = focus_summary[key]
                    if baseline_val != 0:
                        deltas[f"{key}_delta_pct"] = (
                            (focus_val - baseline_val) / baseline_val
                        ) * 100

        return {
            "baseline": baseline_summary,
            "focus": focus_summary,
            "deltas": deltas,
        }

    def save(self, path: Path) -> None:
        """Save results to a JSON file."""
        data = {
            "benchmark_name": self.benchmark_name,
            "model": self.model,
            "timestamp": self.timestamp,
            "runs": [asdict(r) for r in self.runs],
            "summary": self.calculate_summary(),
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path) -> "BenchmarkResults":
        """Load results from a JSON file."""
        data = json.loads(path.read_text())

        results = cls(
            benchmark_name=data["benchmark_name"],
            model=data["model"],
            timestamp=data["timestamp"],
        )

        for run_data in data["runs"]:
            results.runs.append(RunMetrics(**run_data))

        return results


class MetricsTracker:
    """Track metrics during a benchmark run."""

    def __init__(self, benchmark_name: str, model: str):
        self.results = BenchmarkResults(benchmark_name=benchmark_name, model=model)

    def record_run(
        self,
        problem_id: str,
        agent_type: str,
        success: float | bool,  # Allow float or bool
        metrics: dict[str, Any],
        error: str | None = None,
    ) -> RunMetrics:
        """Record a single run."""
        # Convert bool to float (0.0 or 1.0)
        success_val = float(success) if isinstance(success, bool) else success

        run = RunMetrics(
            problem_id=problem_id,
            agent_type=agent_type,
            model=self.results.model,
            success=success_val,
            error=error,
            input_tokens=metrics.get("total_input_tokens", 0),
            output_tokens=metrics.get("total_output_tokens", 0),
            total_tokens=metrics.get("total_input_tokens", 0)
            + metrics.get("total_output_tokens", 0),
            llm_calls=metrics.get("llm_calls", 0),
            tool_calls=metrics.get("tool_calls", 0),
            wall_time_seconds=metrics.get("wall_time_seconds", 0.0),
            message_count=metrics.get("message_count", 0),
            # Focus metrics
            compressions=metrics.get("compressions", 0),
            messages_dropped=metrics.get("messages_dropped", 0),
            knowledge_entries=metrics.get("knowledge_entries", 0),
        )

        self.results.add_run(run)
        return run

    def save(self, output_dir: Path) -> Path:
        """Save results to the output directory."""
        filename = f"{self.results.benchmark_name}_{self.results.model}_{self.results.timestamp.replace(':', '-')}.json"
        path = output_dir / filename
        self.results.save(path)
        return path
