# Focus: Autonomous Memory Management for LLM Agents

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-green)

**Focus** is an agentic architecture that enables autonomous context management in LLM agents. Agents decide when to compress their work by calling `start_focus` and `complete_focus` tools, consolidating completed work into persistent learnings while pruning verbose exploration history. This prevents context overflow but involves a fundamental trade-off between task completion and accuracy.

## 📄 Paper

**[Active Context Compression: Autonomous Memory Management in LLM Agents](paper.pdf)**

Read the paper: [paper.pdf](paper.pdf) | [LaTeX source](paper.tex)

## 🚀 Key Features

* **Model-Controlled Compression:** The LLM autonomously decides when to compress. No artificial timers or heuristics.
* **Biological Inspiration:** Mimics "exploration vs. consolidation" phases seen in *Physarum polycephalum* (slime mold).
* **SWE-bench Verified:** Evaluated using the official Docker-based harness on real software engineering tasks.
* **Prevents Context Overflow:** Enables task completion where baseline agents crash due to context limits.
* **Trade-off Revealed:** Achieves 34% message reduction but with 20% accuracy cost due to information loss.

## 🛠️ Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/NikhilVerma/active-context-compression.git
    cd active-context-compression
    ```

2. **Install dependencies (using uv):**

    ```bash
    uv sync
    ```

3. **Set up environment:**
    Create a `.env` file with your API keys:

    ```bash
    ANTHROPIC_API_KEY=sk-ant-...
    ```

4. **Docker Requirement:**
    You must have Docker installed and running (Docker Desktop or OrbStack) for the evaluation harness.

## 🏃‍♂️ Running Benchmarks

We use the **official SWE-bench evaluation harness** (Docker-based) to ensure reproducible, leaderboard-quality results.

### Reproduce Paper Results (N=5 instances)

```bash
./run_experiment.sh
```

This runs both Baseline and Focus agents on the same 5 instances used in the paper, then evaluates with Docker.

### Custom Evaluation

```bash
# Test on specific instances
uv run python scripts/run_swebench.py \
  --model claude-haiku-4-5-20251001 \
  --instance-ids mwaskom__seaborn-2848 pallets__flask-4045

# Test with different model
uv run python scripts/run_swebench.py \
  --model claude-3-5-sonnet-20241022 \
  --limit 10
```

## 📊 Results

From our Docker-verified A/B comparison on N=5 SWE-bench Lite instances using Claude Haiku 4.5:

| Metric | Baseline | Focus (Ours) | Delta |
|--------|----------|--------------|-------|
| **Task Completion** | 4/5 (80%)* | 5/5 (100%) | +1 task |
| **Task Success (Tests Pass)** | 4/4 (100%) | 3/5 (60%) | -20% |
| **Avg Message Count** | 101.5 | 67.2 | **-34%** |
| **Avg Total Tokens** | 2.44M | 2.71M | +11% |
| **Compressions per Task** | 0 | 2.0 | - |

\* Baseline crashed on one instance (seaborn) due to context overflow at 209K tokens.

**Key Finding:** Focus prevents context overflow, enabling completion of otherwise impossible tasks, but at the cost of 20% accuracy reduction due to information loss during compression. This reveals a fundamental **completion-correctness trade-off** in context compression strategies.

## 🧠 How It Works

The agent has two simple tools:

1. **`start_focus(description, goal)`** - "I'm about to investigate X"
2. **`complete_focus(outcome, learnings, next_action)`** - "I'm done, here's what I learned"

When `complete_focus` is called:

* All messages since `start_focus` are compressed into a "Knowledge" entry
* The verbose tool outputs and exploration logs are deleted
* The preserved learnings remain in context for future use

The model decides autonomously when to compress based on task completion, not arbitrary step counts.

## 🤝 Contributing

Open an issue or PR to discuss improvements.

## 📜 License

MIT
