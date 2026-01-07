# Time Travel Benchmark

Testing whether AI agents benefit from **focus-based context compression** - the ability to progressively compress completed work into learnings while keeping context lean for long-running tasks.

## The Problem

LLM agents working on complex tasks face context exhaustion. As they explore code, read files, and try different approaches, their context fills up with details. Eventually they either:

- Hit token limits
- Become slower and more expensive
- Get lost in their own exploration history

## The Solution: Focus-Based Compression

Instead of keeping every detail of every exploration, agents can:

1. **Start a focus** when beginning a distinct piece of work
2. **Complete the focus** when done, compressing the detailed work into key learnings
3. **Preserve learnings** in a persistent "KNOWLEDGE" section
4. **Drop the details** to keep context lean

This enables agents to run much longer on multi-branch tasks without multi-agent handoffs or external memory systems.

## Key Findings

**FocusAgent with auto-compression (10 steps per focus):**

- ✅ **Succeeded** on hidden_config problem
- 📊 **151K tokens** (54% reduction vs baseline)
- 🔄 **5 focus cycles**, 134 messages compressed
- 🎯 **Final context**: Only 12 messages

**Baseline Agent (no compression):**

- ❌ **Failed** (max steps exceeded)
- 📊 **332K tokens**  
- 📝 **112 messages** (overwhelmed by details)

## Installation

```bash
# Requires uv (https://github.com/astral-sh/uv)
uv sync

# Set API key
export ANTHROPIC_API_KEY=your_key
```

## Usage

### Run Focus Agent Benchmark

```bash
# Quick test on one problem
uv run python scripts/run_focus_benchmark.py \
  --problems hidden_config \
  --focus-only \
  --steps-per-focus 10

# Full comparison (baseline vs focus)
uv run python scripts/run_focus_benchmark.py \
  --steps-per-focus 15

# Disable auto-focus (let model use tools naturally - not recommended)
uv run python scripts/run_focus_benchmark.py \
  --no-auto-focus
```

### Run Original Time Travel Benchmark

```bash
# Compare baseline vs reset_context tool
uv run python scripts/run_mini_benchmark.py
```

## Project Structure

```
src/
  agents/
    base.py          # Base agent interface
    baseline.py      # Standard agent (control)
    time_travel.py   # Agent with reset_context tool
    focus.py         # Agent with auto-focus management ⭐
  tools/
    base.py          # Tool interface
    coding.py        # File I/O, grep, etc.
    time_travel.py   # reset_context tool
    focus.py         # start_focus / complete_focus tools ⭐
  benchmarks/
    mini.py          # Hand-crafted problems
    swebench.py      # SWE-bench integration
  metrics/
    tracker.py       # Metrics collection
    reporter.py      # Result analysis
scripts/
  run_mini_benchmark.py   # Original benchmark runner
  run_focus_benchmark.py  # Focus agent benchmark ⭐
  analyze_results.py      # Result analysis
```

## How Focus Agent Works

```python
# Auto-start focus at beginning
self._auto_start_focus("Initial exploration", "Understand the problem")

# Every N steps, check if should auto-complete
if self._steps_in_current_focus >= self._steps_per_focus:
    self._auto_complete_focus()
    
# Extract learnings from messages
learnings = self._extract_learnings_from_messages()

# Compress: truncate messages back to safe point
safe_point = self._find_safe_truncation_point(start_index)
self.messages = self.messages[:safe_point]

# Rebuild system message with accumulated knowledge
self._rebuild_messages_with_knowledge()

# Add continuation message
self._add_message(Message(role=USER, content="Focus completed. Continue..."))

# Start new focus for next phase
self._auto_start_focus("Continuing work", "Complete remaining tasks")
```

## Why Auto-Compression?

**Models don't self-invoke meta-cognitive tools.** We tested with:

- 10 explicit nudges in system prompt → 0 uses
- Frustration detection + nudging → 0 uses
- Making tools available → 0 uses

**Automatic triggering works:**

- Behavioral signals (frustration detection) → Improved results
- Time-based cycles (every N steps) → **54% token reduction + success** ⭐

This aligns with how other tool-learning papers work:

- **Reflexion**: Programmatic reset between trials
- **Toolformer**: Fine-tuning for tool use
- **LATM**: Automatic memory management

## Key Insights

1. **LLMs don't naturally use novel meta-cognitive tools** even when explicitly instructed
2. **Programmatic triggers work better** than expecting self-invocation
3. **Structured compression beats simple context dropping** (preserve learnings explicitly)
4. **Focus-based compression enables longer-running tasks** without multi-agent complexity
5. **Time-based cycles are simple and effective** (every 10-15 steps)

## Configuration

```python
FocusAgent(
    model="claude-haiku-4-5-20251001",
    auto_focus=True,          # Enable auto-compression
    steps_per_focus=15,       # Compress every 15 steps
    max_steps=50,             # Total step limit
)
```

## Results Format

```json
{
  "problem_id": "hidden_config",
  "agent_type": "focus",
  "success": true,
  "total_tokens": 151621,
  "llm_calls": 48,
  "time_travels": 5,
  "messages_dropped": 134,
  "message_count": 12,
  "wall_time_seconds": 97.72
}
```

## Development

```bash
# Run tests
uv run pytest

# Format code
uv run black .
uv run ruff check --fix .

# Add new benchmark problem
# Edit src/benchmarks/mini.py, add to get_mini_benchmark()
```

## Related Work

- **Reflexion** ([Shinn et al. 2023](https://arxiv.org/abs/2303.11366)): Self-reflection between trials
- **LATM** ([Liang et al. 2024](https://arxiv.org/abs/2409.00234)): Long-term memory for agents
- **Toolformer** ([Schick et al. 2023](https://arxiv.org/abs/2302.04761)): Teaching LLMs to use tools
- **Self-RAG** ([Asai et al. 2023](https://arxiv.org/abs/2310.11511)): Self-reflective retrieval

**Key difference**: We compress mid-run during a single continuous task, rather than learning between trials or using external memory stores.

## License

MIT
