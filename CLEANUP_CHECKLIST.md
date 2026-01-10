# Repository Cleanup Checklist

## ✅ What to KEEP (Essential for Publication)

### Core Code
- ✅ `src/agents/base.py` - Base agent class
- ✅ `src/agents/baseline.py` - Baseline agent (needed for comparison)
- ✅ `src/agents/focus.py` - **Main contribution**
- ✅ `src/tools/focus.py` - start_focus/complete_focus tools
- ✅ `src/tools/coding.py` - Coding tools
- ✅ `src/benchmarks/swebench.py` - SWE-bench integration
- ✅ `src/metrics.py` - Metrics tracking

### Essential Scripts
- ✅ `scripts/run_final_experiment.py` - **Main reproduction script**
- ✅ `scripts/visualize_trajectory.py` - **Generates sawtooth graph**
- ✅ `run_experiment.sh` - One-command runner

### Paper & Documentation
- ✅ `paper.tex` - **The paper**
- ✅ `sawtooth.png` - **Figure 2**
- ✅ `README.md` - Main documentation
- ✅ `PUBLICATION_READY.md` - Submission guide
- ✅ `PAPER_SUBMISSION_README.md` - Package guide
- ✅ `EXPERIMENT_RESULTS.md` - Detailed findings

### Experimental Data (Final Run Only)
- ✅ `results/final_experiment_20260110_132709.json` - **Full data with trajectories**
- ✅ `results/predictions_baseline_20260110_132709.json` - For Docker eval
- ✅ `results/predictions_focus_20260110_132709.json` - For Docker eval
- ✅ `results/final_experiment_20260110_132709_sawtooth.png` - Backup of figure
- ✅ `claude-haiku-4-5-20251001_baseline.baseline_haiku_final.json` - **Docker results**
- ✅ `claude-haiku-4-5-20251001_focus.focus_haiku_final.json` - **Docker results**

### Configuration
- ✅ `pyproject.toml` - Dependencies
- ✅ `uv.lock` - Lock file
- ✅ `.gitignore` - Updated for publication

---

## ❌ What to REMOVE (Junk/Exploratory)

### Old Experimental Scripts (Not Needed for Reproduction)
- ❌ `scripts/run_focus_benchmark.py` - Superseded by run_final_experiment.py
- ❌ `scripts/run_mini_benchmark.py` - Early prototype
- ❌ `scripts/run_memory_test.py` - Exploratory (has errors)
- ❌ `scripts/check_django_task.py` - One-off debugging
- ❌ `scripts/check_flask_task.py` - One-off debugging
- ❌ `scripts/check_pylint_task.py` - One-off debugging
- ❌ `scripts/analyze_progress.py` - Analysis helper
- ❌ `scripts/analyze_results.py` - Analysis helper
- ❌ `scripts/trace_tokens.py` - Debugging tool
- ❌ `scripts/list_repos.py` - Exploration script

### Old Documentation (Superseded)
- ❌ `SUMMARY.md` - Old summary, replaced by EXPERIMENT_RESULTS.md
- ❌ `NEXT_STEPS.md` - Process notes, not needed for users

### Log Files (Generated, Not Source)
- ❌ `*.log` - All log files
- ❌ `experiment_log.txt` - Experiment output
- ❌ `focus_run.log` - Old run log
- ❌ `full_focus_run.log` - Old run log
- ❌ `logs/` directory - Large Docker logs (19MB!)

### Old Experimental Results (72 files!)
- ❌ `results/mini_*.json` - Early mini benchmarks
- ❌ `results/swebench_lite_*_2026-01-0[1-9]*.json` - Old attempts
- ❌ `results/predictions_*_202601[0-1][0-9]*.json` - Old predictions (except final)

### Environment Files
- ❌ `.env` - **CRITICAL: Contains API key!**
- ❌ `.env.local` - If exists

### Temporary/Cache
- ❌ `__pycache__/` - Python cache
- ❌ `.pytest_cache/` - Test cache
- ❌ `.DS_Store` - macOS metadata
- ❌ `tmp*/` - Temporary directories

---

## 🔍 Files to REVIEW Before Publishing

### Check These Manually:
1. **README.md** - Update with GitHub-specific instructions
2. **src/config.py** - Make sure no hardcoded secrets
3. **scripts/run_swebench.py** - Keep or remove? (Alternative runner)
4. **scripts/inspect_swebench.py** - Useful utility or junk?

---

## 🚨 CRITICAL: Security Check

Before making public, verify NO secrets in:
```bash
# Run these checks:
grep -r "sk-ant-" . --exclude-dir=.git --exclude-dir=.venv
grep -r "ANTHROPIC_API_KEY=sk" . --exclude-dir=.git --exclude-dir=.venv
cat .env  # Make sure this file will be deleted!
```

---

## 📊 Size Reduction Expected

**Before cleanup:**
- Total: ~40MB (with .venv) / ~20MB (without .venv)
- logs/: 19MB
- results/: 920KB (72 files)

**After cleanup:**
- Total: ~1-2MB
- logs/: Removed
- results/: ~50KB (3 essential files)

**~95% size reduction!**

---

## 🏃 Run Cleanup

```bash
# 1. Run automated cleanup
./cleanup_for_publication.sh

# 2. Remove old scripts manually
rm scripts/run_focus_benchmark.py
rm scripts/run_mini_benchmark.py
rm scripts/run_memory_test.py
rm scripts/check_*.py
rm scripts/analyze_*.py
rm scripts/trace_tokens.py
rm scripts/list_repos.py

# 3. Remove old docs
rm SUMMARY.md
rm NEXT_STEPS.md

# 4. Verify cleanup
git status
git diff

# 5. Commit
git add -A
git commit -m "Clean up repository for public release

- Remove exploratory scripts and old experiments
- Keep only final experiment results (N=5, Docker-verified)
- Remove all logs and temporary files
- Update .gitignore for publication
- Remove .env file (API keys)

Core contribution preserved:
- Focus agent implementation
- Reproduction scripts
- Paper with real results
- Final experimental data
"
```

---

## ✅ Final Verification

Before making public:
- [ ] `.env` file removed
- [ ] No API keys in code
- [ ] Only 3 result files in results/
- [ ] No log files
- [ ] Paper has real sawtooth.png
- [ ] README updated for public use
- [ ] All scripts run without errors
- [ ] Repository size < 5MB

---

## 📦 What Users Get

**After cleanup, users can:**
1. Read paper.tex (with real results)
2. See sawtooth.png (real trajectory)
3. Run `./run_experiment.sh` (reproduce with their API key)
4. Read source code (src/)
5. See final results (results/ - 3 files)
6. Verify Docker eval (2 JSON reports)

**Clean, focused, reproducible!**
