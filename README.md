# Focus: Active Context Compression for LLM Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Focus** is an experimental architecture for LLM agents that enables "Active Context Compression." Instead of passively accumulating context until failure, the agent actively explores, summarizes key learnings, and deletes unproductive history—mimicking the biological efficiency of *Physarum polycephalum* (slime mold).

## The Problem
Standard agents use an "Append-Only" context strategy. This leads to:
1.  **Exponential Cost:** Re-reading the entire history for every step.
2.  **Context Poisoning:** Getting confused by previous failed attempts.
3.  **Hard Limits:** Crashing when the context window is full.

## The Solution: Focus Agent
The Focus Agent introduces a "Sawtooth" context pattern:
1.  **Explore:** Run tools and investigate.
2.  **Consolidate:** Stop, summarize findings into a "Knowledge" block.
3.  **Withdraw:** Delete the raw logs of the exploration path.

## Results (SWE-bench Lite)
Evaluated on 10 diverse software engineering tasks using `claude-haiku-4-5-20251001`:

| Metric | Baseline | Focus (Ours) | Delta |
| :--- | :--- | :--- | :--- |
| **Avg Tokens** | 2,871,599 | 1,229,816 | **-57.2%** |
| **Avg Wall Time** | 286.7s | 180.3s | **-37.1%** |
| **Final Context** | 97 messages | 16.5 messages | **-83.0%** |

In a targeted test with `claude-sonnet-4-5`, the Focus Agent **successfully solved** the `pallets/flask-5063` task while using **66% fewer tokens** than the baseline.

## Quick Start

### Prerequisites
- Python 3.10+
- `uv` (recommended) or `pip`
- `ANTHROPIC_API_KEY`

### Installation
```bash
git clone https://github.com/yourusername/focus-agent.git
cd focus-agent
uv sync
```

### Running the Benchmark
To replicate our results on SWE-bench Lite:

```bash
# Run a specific instance (e.g., Flask)
uv run scripts/run_swebench.py --instance-ids pallets__flask-5063 --model claude-sonnet-4-5-20250929

# Run the full N=10 suite (Warning: expensive!)
uv run scripts/run_swebench.py --limit 10 --model claude-haiku-4-5-20251001
```

## Paper & Artifacts
*   📄 **[Read the Paper](paper.pdf)** (Compile `paper.tex` to generate)
*   📊 **[View Raw Logs](logs/raw/)**
*   📈 **[View Metrics](results/metrics/)**

## Citation
If you use this work, please cite:

```bibtex
@misc{focus2026,
  title={Active Context Compression: Enabling "Immortal" Agents},
  author={Verma, Nikhil},
  year={2026},
  publisher={GitHub}
}
```
