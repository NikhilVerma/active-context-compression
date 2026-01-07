# Summary: Focus-Based Context Compression

## What We Built

A system for testing whether AI agents benefit from **progressive context compression** - dropping completed work while preserving learnings.

## The Journey

1. **Initial hypothesis**: Can agents use a `reset_context` tool?
   - Result: ❌ Models never self-invoked the tool (0 uses despite 10 nudges)

2. **Frustration detection**: Force reset when agent is stuck
   - Result: ✅ Improved from 60% → 80% success, -30% tokens
   - Learning: Programmatic triggers work, self-invocation doesn't

3. **Focus-based compression**: Auto-manage compression cycles
   - Result: ⭐ **54% token reduction + solved problems baseline couldn't**
   - Method: Compress every N steps, preserve learnings in KNOWLEDGE section

## Final Implementation

### FocusAgent

Auto-manages context compression cycles:

```python
# Every N steps, compress completed work
if steps_in_focus >= steps_per_focus:
    # Extract key learnings
    learnings = extract_from_messages()

    # Truncate to safe point (preserve API message structure)
    messages = messages[:find_safe_truncation_point()]

    # Rebuild with learnings in KNOWLEDGE section
    rebuild_system_message_with_knowledge()

    # Continue with fresh context
    start_new_focus()
```

### Key Features

- **Persistent KNOWLEDGE section**: Accumulated learnings preserved across cycles
- **Safe truncation**: Respects Anthropic API message structure constraints
- **Automatic learning extraction**: Identifies files read/written, errors encountered
- **Configurable cycles**: `steps_per_focus` parameter controls compression frequency

## Results

### Hidden Config Problem

**Baseline Agent:**

- ❌ Failed (max steps exceeded)
- 332K tokens
- 112 messages
- Got lost in exploration

**FocusAgent (10 steps/focus):**

- ✅ Succeeded
- 151K tokens (54% reduction)
- 5 compression cycles
- 12 final messages

## Key Learnings

1. **Models don't use novel meta-cognitive tools naturally**
   - Even with explicit instructions
   - Even with nudging and examples
   - Requires programmatic triggers

2. **Structured compression beats naive dropping**
   - Explicitly preserve learnings
   - Maintain KNOWLEDGE section
   - Don't just drop messages randomly

3. **Simple time-based triggers work well**
   - Every 10-15 steps
   - No complex heuristics needed
   - Consistent and predictable

4. **API constraints matter**
   - Can't orphan tool_use blocks
   - Need safe truncation points
   - Message structure must be valid

5. **Compression enables longer tasks**
   - Keep context lean
   - Don't accumulate details
   - Focus on current work + past learnings

## Comparison to Related Work

| Approach | When | Scope | Trigger |
|----------|------|-------|---------|
| **Reflexion** | Between trials | Inter-trial | After failure |
| **LATM** | Ongoing | External memory | Automatic |
| **Our work** | Mid-run | In-context | Time-based |

**Key difference**: We compress during a single continuous task, not between trials or to external memory.

## Future Directions

1. **Smarter boundaries**: Detect topic shifts, not just step counts
2. **Hierarchical knowledge**: Short-term vs long-term learnings
3. **SWE-bench evaluation**: Test on real GitHub issues
4. **Multi-level compression**: Compress KNOWLEDGE section itself
5. **Adaptive cycles**: Vary `steps_per_focus` based on task complexity

## Code Quality

- ✅ All code formatted with **black** (line length 100)
- ✅ All imports sorted with **ruff**
- ✅ No linting errors
- ✅ Frustration code removed (simpler codebase)
- ✅ Comprehensive README added

## Artifacts

- **`src/agents/focus.py`**: FocusAgent implementation
- **`src/tools/focus.py`**: start_focus/complete_focus tools
- **`scripts/run_focus_benchmark.py`**: Benchmark runner
- **`results/mini_focus_*.json`**: Experimental results
- **`README.md`**: Complete documentation

## Quick Start (For New Users)

```bash
# Install
uv sync
export ANTHROPIC_API_KEY=your_key

# Run benchmark
uv run python scripts/run_focus_benchmark.py \
  --problems hidden_config \
  --focus-only \
  --steps-per-focus 10

# Expected output:
# ✅ Success: true
# 📊 Tokens: ~150K
# 🔄 Focus cycles: 5
```

## Status

**✅ Project Complete**

- Core implementation working
- Evidence of effectiveness
- Code cleaned and formatted
- Documentation comprehensive
- Ready for sharing/publication
