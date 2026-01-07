# Time Travel Benchmark

Testing whether AI agents benefit from "time travel" — actively managing their context by dropping unproductive exploration paths and keeping only the learnings.

## The Hypothesis

Agents that can call a `time_travel()` tool to:
1. Extract a learning from their current exploration
2. Drop the last N messages from context
3. Continue with the learning injected

...will outperform baseline agents (that keep everything in context) on:
- Token efficiency
- Task completion rate
- Time to solution

## Quick Start

```bash
# Install dependencies
uv sync

# Set API keys
export ANTHROPIC_API_KEY=your_key
export OPENAI_API_KEY=your_key

# Run mini benchmark (5-10 custom problems, fast iteration)
python scripts/run_mini_benchmark.py

# Run SWE-bench Lite subset (slower, more rigorous)
python scripts/run_swebench.py --limit 50

# Analyze results
python scripts/analyze_results.py results/
```

## Project Structure

```
src/
├── agents/
│   ├── base.py          # Abstract agent interface
│   ├── baseline.py      # Agent without time travel
│   └── time_travel.py   # Agent with time travel tool
├── benchmarks/
│   ├── mini.py          # Hand-crafted problems for quick iteration
│   └── swebench.py      # SWE-bench Lite loader
├── tools/
│   ├── base.py          # Tool interface
│   ├── time_travel.py   # The time_travel() tool
│   └── coding.py        # Standard coding tools (read, write, run)
└── metrics/
    ├── tracker.py       # Per-run metrics collection
    └── reporter.py      # Aggregate and compare results

scripts/
├── run_mini_benchmark.py
├── run_swebench.py
└── analyze_results.py

tests/
└── ...
```

## Experimental Design

### Independent Variable
- **Baseline agent**: Standard context management (keep everything, maybe summarize at limit)
- **Time travel agent**: Has access to `time_travel(learning, steps_back)` tool

### Dependent Variables
- **Success rate**: Did the agent solve the problem?
- **Token usage**: Total input + output tokens
- **Steps taken**: Number of LLM calls
- **Time to solution**: Wall clock time

### Controls
- Same model (Claude 3.5 Sonnet or GPT-4o)
- Same temperature (0)
- Same max steps (50)
- Same tool set (except time_travel for experimental)
