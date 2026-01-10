#!/bin/bash
# Cleanup script to prepare repository for public release
# Run this before making the repo public

set -e

echo "🧹 Cleaning up repository for publication..."

# 1. Remove sensitive files
echo "Removing .env file..."
rm -f .env
rm -f .env.local

# 2. Remove log files
echo "Removing log files..."
rm -f *.log
rm -f experiment_log.txt
rm -f focus_run.log
rm -f full_focus_run.log
rm -rf logs/run_evaluation/  # Large Docker logs

# 3. Remove Python cache
echo "Removing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# 4. Clean up old experimental results (keep only final)
echo "Cleaning up old experimental results..."
cd results
# Keep only final experiment files
find . -name "*.json" ! -name "final_experiment_20260110_132709.json" \
                       ! -name "predictions_baseline_20260110_132709.json" \
                       ! -name "predictions_focus_20260110_132709.json" \
                       -delete 2>/dev/null || true
cd ..

# Keep Docker evaluation results
# (claude-haiku*.json files in root)

# 5. Remove temporary files
echo "Removing temporary files..."
rm -rf tmp*/
rm -f *.tmp
rm -f *.bak
rm -f *~

# 6. Check for API keys
echo "Checking for API keys..."
if grep -r "sk-ant-" . --exclude-dir=.git --exclude-dir=.venv 2>/dev/null; then
    echo "⚠️  WARNING: Found potential API keys in code!"
    echo "Please review and remove them manually."
else
    echo "✅ No API keys found"
fi

# 7. Verify no secrets in tracked files
echo "Verifying no secrets..."
if git ls-files | xargs grep -l "sk-ant\|ANTHROPIC_API_KEY=sk" 2>/dev/null; then
    echo "⚠️  WARNING: Secrets found in tracked files!"
    echo "Run: git rm --cached <file> to untrack them"
else
    echo "✅ No secrets in tracked files"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Review cleaned repository"
echo "2. Test that experiments still run: ./run_experiment.sh"
echo "3. Commit cleanup: git add -A && git commit -m 'Clean up for publication'"
echo "4. Make repo public: GitHub → Settings → Danger Zone → Change visibility"
echo ""
echo "Files kept:"
echo "  - results/final_experiment_20260110_132709.json"
echo "  - results/predictions_*_20260110_132709.json"
echo "  - results/final_experiment_20260110_132709_sawtooth.png"
echo "  - claude-haiku-4-5-20251001_*.json (Docker eval)"
echo "  - All source code (src/, scripts/)"
echo "  - Paper (paper.tex, sawtooth.png)"
