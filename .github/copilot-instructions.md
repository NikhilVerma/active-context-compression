# .github/copilot-instructions.md

This is a benchmark project for testing whether AI agents benefit from "time travel" - the ability to actively drop unproductive context and keep only learnings.

## Project Structure

- `src/agents/` - Agent implementations (baseline and time_travel)
- `src/benchmarks/` - Benchmark problems (mini custom + SWE-bench Lite)
- `src/tools/` - Tool definitions including the time_travel tool
- `src/metrics/` - Metrics tracking and reporting
- `scripts/` - Benchmark runners and analysis
- `tests/` - Unit tests

## Running the Benchmark

```bash
# Install dependencies
uv sync

# Set API keys
export ANTHROPIC_API_KEY=your_key

# Run mini benchmark (quick iteration)
python scripts/run_mini_benchmark.py

# Run SWE-bench (more rigorous)
python scripts/run_swebench.py --limit 10
```

## Key Files

- `src/tools/time_travel.py` - The core time_travel tool implementation
- `src/agents/time_travel.py` - Agent that uses time travel
- `src/benchmarks/mini.py` - Hand-crafted benchmark problems

## Development Guidelines

- Use `uv` for dependency management
- Run `pytest` before committing
- Keep benchmark problems self-contained (no external dependencies)
