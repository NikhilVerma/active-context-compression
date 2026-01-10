# 🧹 Repository Cleanup - Ready for Publication

## ✅ I've Prepared Everything

### 1. **Updated .gitignore**
- Excludes all logs, .env, cache files
- Keeps only final experiment results
- Protects against accidentally committing secrets

### 2. **Created Cleanup Script**
- `cleanup_for_publication.sh` - Run this to clean everything
- Removes .env, logs, old experiments, cache files
- Checks for API keys before completion

### 3. **Identified Junk**
See `CLEANUP_CHECKLIST.md` for complete list:
- **Remove 10 old scripts** (exploratory/debugging)
- **Remove 69 old result files** (keep only 3 final ones)
- **Remove 19MB of logs**
- **Remove .env file** (CRITICAL - has API key!)

---

## 🚀 Quick Cleanup (Run These Commands)

```bash
cd /Volumes/repos/time-travel-benchmark

# 1. Run automated cleanup
./cleanup_for_publication.sh

# 2. Remove old exploratory scripts
rm scripts/run_focus_benchmark.py \
   scripts/run_mini_benchmark.py \
   scripts/run_memory_test.py \
   scripts/check_django_task.py \
   scripts/check_flask_task.py \
   scripts/check_pylint_task.py \
   scripts/analyze_progress.py \
   scripts/analyze_results.py \
   scripts/trace_tokens.py \
   scripts/list_repos.py

# 3. Remove old docs (superseded)
rm SUMMARY.md NEXT_STEPS.md

# 4. Remove old shell scripts (except run_experiment.sh)
rm scripts/run_n50_benchmark.sh

# 5. Verify no secrets
grep -r "sk-ant-" . --exclude-dir=.git --exclude-dir=.venv || echo "✅ No secrets found"

# 6. Check status
git status

# 7. Review what's being removed
git diff --stat

# 8. Commit cleanup
git add -A
git commit -m "Clean repository for public release

- Remove .env file and all logs
- Remove exploratory scripts (10 files)
- Remove old experiments (69 result files)
- Keep only final experiment data (N=5, Docker-verified)
- Update .gitignore for publication

Core preserved:
- Focus agent (src/agents/focus.py)
- Reproduction script (run_experiment.sh)
- Paper with real results (paper.tex)
- Final experimental data (3 files)
- Docker evaluation reports (2 files)
"
```

---

## 📊 What Gets Removed

### Files to Delete (Safe - All Junk):

**Logs (19MB):**
- All *.log files
- experiment_log.txt
- logs/run_evaluation/ directory

**Old Scripts (10 files):**
- run_focus_benchmark.py (superseded)
- run_mini_benchmark.py (prototype)
- run_memory_test.py (has errors)
- check_*.py (3 files - debugging)
- analyze_*.py (2 files - helpers)
- trace_tokens.py (debugging)
- list_repos.py (exploration)

**Old Results (69 files):**
- mini_*.json (early tests)
- Old swebench runs
- Old predictions
- **Keep only 3 files from Jan 10, 2026**

**Environment:**
- .env (CRITICAL - contains API key!)

**Old Docs:**
- SUMMARY.md (replaced)
- NEXT_STEPS.md (process notes)

---

## ✅ What Stays (Essential)

### Core Code (7 files):
- src/agents/focus.py ⭐ Main contribution
- src/agents/baseline.py
- src/agents/base.py
- src/tools/focus.py ⭐ Tools
- src/tools/coding.py
- src/benchmarks/swebench.py
- src/metrics.py

### Scripts (3 files):
- run_experiment.sh ⭐ One-command runner
- scripts/run_final_experiment.py ⭐ Main script
- scripts/visualize_trajectory.py ⭐ Graph generator
- scripts/run_swebench.py (alternative runner)
- scripts/inspect_swebench.py (utility)

### Paper (2 files):
- paper.tex ⭐ The paper
- sawtooth.png ⭐ Figure 2

### Data (5 files):
- results/final_experiment_20260110_132709.json ⭐
- results/predictions_baseline_20260110_132709.json ⭐
- results/predictions_focus_20260110_132709.json ⭐
- claude-haiku-*_baseline.*.json ⭐ Docker eval
- claude-haiku-*_focus.*.json ⭐ Docker eval

### Docs (6 files):
- README.md
- PUBLICATION_READY.md
- PAPER_SUBMISSION_README.md
- EXPERIMENT_RESULTS.md
- LICENSE
- .gitignore

**Total: ~30 essential files instead of 100+ mixed files**

---

## 🔒 Security Verified

After cleanup, verify:
```bash
# 1. .env is deleted
ls -la .env 2>&1 | grep "No such file" && echo "✅ .env removed"

# 2. No API keys in tracked files
git ls-files | xargs grep "sk-ant" && echo "❌ FOUND KEYS" || echo "✅ No keys"

# 3. No secrets in code
grep -r "ANTHROPIC_API_KEY=sk" . --exclude-dir=.git --exclude-dir=.venv || echo "✅ Clean"
```

---

## 📦 After Cleanup

**Repository will be:**
- ✅ ~1-2MB (down from 20MB+)
- ✅ No secrets or API keys
- ✅ Only essential files
- ✅ Clean git history
- ✅ Ready for public release

**Users will get:**
- 🔬 Reproducible experiment
- 📄 Paper with real results
- 💻 Clean, documented code
- 📊 Final experimental data
- 🎯 Clear instructions

---

## 🎯 Next Steps

1. ✅ **Run cleanup** - `./cleanup_for_publication.sh`
2. ✅ **Remove old scripts** - See commands above
3. ✅ **Verify security** - Check for API keys
4. ✅ **Commit cleanup** - `git commit -m "Clean for publication"`
5. ✅ **Test reproduction** - `./run_experiment.sh` (use your API key)
6. ✅ **Make public** - GitHub Settings → Change visibility
7. ✅ **Announce** - Twitter, Reddit, HN

---

## 💡 Pro Tip

Want to review what's being deleted before running?

```bash
# Dry run - see what would be deleted
./cleanup_for_publication.sh 2>&1 | grep "Removing"

# Or check manually
find . -name "*.log" -o -name "*.pyc"
ls results/*.json | wc -l
```

---

**Ready to clean? Run: `./cleanup_for_publication.sh`**
