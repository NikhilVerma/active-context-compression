# Variables
UV := uv
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest
RUFF := $(UV) run ruff

# Default target
.DEFAULT_GOAL := help

.PHONY: all setup clean format lint test bench-mini bench-flask bench-swe-lite analysis help

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Create local .venv and install dependencies
	@echo "Creating local virtual environment (.venv)..."
	$(UV) venv
	@echo "Installing dependencies into .venv..."
	$(UV) sync
	@echo "Setup complete. Run 'source .venv/bin/activate' to enter it manually,"
	@echo "or simply use 'make <command>' which uses it automatically."

clean: ## Clean up build artifacts, cache, and temp files
	@echo "Cleaning up..."
	rm -rf dist build *.egg-info .pytest_cache .mypy_cache .ruff_cache .venv
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf logs/raw/*.log
	@echo "Clean complete. (Note: .venv was removed. Run 'make setup' to recreate)"

format: ## Format code using ruff (black compatible)
	@echo "Formatting code..."
	$(RUFF) format .

lint: ## Run linting (ruff check and fix)
	@echo "Running linters..."
	$(RUFF) check . --fix
	$(UV) run mypy src

test: ## Run unit tests
	@echo "Running tests..."
	$(PYTEST) tests/

# --- Benchmark Commands ---

bench-mini: ## Run the mini benchmark (Fast & Cheap) - Good for sanity check
	@echo "Running Mini Benchmark..."
	$(PYTHON) scripts/run_mini_benchmark.py

bench-flask: ## Run the Flask-5063 task (The "Green Checkmark" proof) using Sonnet
	@echo "Running Flask-5063 Benchmark (Baseline vs Focus)..."
	@echo "Warning: This requires Anthropic API credits."
	$(PYTHON) scripts/run_swebench.py --instance-ids pallets__flask-5063 --model claude-sonnet-4-5-20250929

bench-swe-lite: ## Run a suite of 10 SWE-bench Lite instances using Haiku (Expensive!)
	@echo "Running N=10 SWE-bench Suite..."
	$(PYTHON) scripts/run_swebench.py --limit 10 --model claude-haiku-4-5-20251001

analysis: ## Analyze active/recent benchmark logs
	$(PYTHON) scripts/analyze_progress.py

# --- Proper SWE-bench with Docker Evaluation ---

bench-proper: ## Run SWE-bench with official Docker evaluation (Sonnet, N=5)
	@echo "Running proper SWE-bench benchmark with Docker evaluation..."
	@echo "This uses the official SWE-bench harness for accurate results."
	$(PYTHON) scripts/run_swebench_proper.py \
		--model claude-sonnet-4-5-20250929 \
		--limit 5 \
		--max-workers 3

bench-proper-n10: ## Run SWE-bench N=10 with Docker evaluation (Sonnet)
	@echo "Running N=10 SWE-bench with Docker evaluation..."
	$(PYTHON) scripts/run_swebench_proper.py \
		--model claude-sonnet-4-5-20250929 \
		--limit 10 \
		--max-workers 4

bench-eval-only: ## Run Docker evaluation on existing predictions
	@echo "Running evaluation on existing predictions..."
	@echo "Usage: make bench-eval-only PRED=results/predictions_baseline_xxx.json"
	$(PYTHON) -m swebench.harness.run_evaluation \
		--predictions_path $(PRED) \
		--run_id eval_$(shell date +%Y%m%d_%H%M%S) \
		--max_workers 4 \
		--dataset_name "princeton-nlp/SWE-bench_Lite"

check-docker: ## Check Docker is configured correctly
	@echo "Checking Docker configuration..."
	@$(PYTHON) -c "from scripts.run_swebench_proper import verify_docker; verify_docker()"
