# Time Travel Benchmark - Progress & Next Steps

## What We Did

### 1. Built the Benchmark Framework

- Created agent harness with baseline and time-travel variants
- Implemented the `time_travel` tool that lets agents drop N messages and inject a learning
- Built metrics tracking (tokens, LLM calls, tool calls, success rate, wall time)
- Created 5 hand-crafted "mini benchmark" problems
- Added SWE-bench Lite loader for more rigorous testing later

### 2. Ran Initial Experiment

- **Model**: Claude 3.5 Haiku
- **Problems**: 2 (hidden_config, bug_hunt)
- **Runs**: 4 total (2 problems × 2 agents)

### 3. Results (Inconclusive)

| Metric | Baseline | Time Travel | Delta |
|--------|----------|-------------|-------|
| Success Rate | 100% | 100% | 0% |
| Avg Tokens | 8,540 | 15,362 | +79.9% |
| Avg LLM Calls | 6.0 | 8.0 | +33.3% |

**Key finding**: Time travel agent performed *worse* because:

- It never used the `time_travel` tool (0 invocations)
- Problems were too easy — solved in ~6 calls without hitting dead ends
- Extra overhead from longer system prompt explaining time travel

---

## What To Do Next

### Priority 1: Create Harder Problems

The current problems don't trigger enough exploration/backtracking. Need problems where:

- [ ] Agent is actively misled by red herrings for 10+ messages
- [ ] Multiple plausible approaches exist, most of which fail
- [ ] Information is scattered across many files, requiring search
- [ ] Solution requires trying and abandoning multiple strategies

Ideas:

- Large codebase with misleading variable names
- Bug that looks like it's in file A but is actually in file B
- Config that depends on another config that depends on another
- Test failure caused by subtle interaction between modules

### Priority 2: Improve Time Travel Prompt

Current prompt might be too passive. Consider:

- [ ] More explicit instruction: "After 5+ unsuccessful attempts, consider time_travel"
- [ ] Add examples in the system prompt showing when to use it
- [ ] Experiment with "forcing" time travel after N failed tool calls

### Priority 3: Test With Stronger Models

- [ ] Run with Claude 3.5 Sonnet (better at tool use)
- [ ] Run with Claude 3 Opus (more thoughtful, might use time travel strategically)
- [ ] Compare across model tiers

### Priority 4: Run More Problems

- [ ] Run all 5 mini benchmark problems
- [ ] Run SWE-bench Lite subset (10-50 problems)
- [ ] Get statistically significant sample size

### Priority 5: Analyze When Time Travel Helps

- [ ] Identify problem characteristics that benefit from time travel
- [ ] Measure correlation: problems with more dead ends → more time travel benefit?
- [ ] Track: does time travel reduce total tokens when actually used?

---

## Files Reference

| File | Purpose |
|------|---------|
| `src/tools/time_travel.py` | The time_travel tool definition |
| `src/agents/time_travel.py` | Agent with time travel capability |
| `src/agents/baseline.py` | Control agent (no time travel) |
| `src/benchmarks/mini.py` | Hand-crafted problems |
| `scripts/run_mini_benchmark.py` | Run mini benchmark |
| `results/*.json` | Benchmark results |

## Running Commands

```bash
# Run specific problems
uv run python scripts/run_mini_benchmark.py --model claude-haiku-4-5-20251001 --problems hidden_config bug_hunt

# Run all mini benchmark problems
uv run python scripts/run_mini_benchmark.py --model claude-haiku-4-5-20251001

# Run SWE-bench (slower, harder)
uv run python scripts/run_swebench.py --limit 10

# Analyze results
uv run python scripts/analyze_results.py results/
```
