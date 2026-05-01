#!/usr/bin/env bash
# run_trend_perf_report.sh — wrapper invoked by launchd on 2026-05-07.
#
# 1. git pull the repo
# 2. run scripts/trend_perf_report.py
# 3. notify (solo-founder-os fan_out if env-configured, else osascript)
# 4. self-uninstall — unload + remove the plist so it never fires again
#
# Manual invocation also works: `bash scripts/run_trend_perf_report.sh`.
# The date guard ensures plist re-fires (e.g. annually) become no-ops.

set -u

REPO="/Users/alexji/Desktop/orallexa-marketing-agent"
TARGET_DATE="2026-05-07"
PLIST="$HOME/Library/LaunchAgents/com.alexji.marketing-agent-trend-perf.plist"
LOG="$HOME/.marketing_agent/trend_perf_$(date -u +%Y-%m-%d).log"
mkdir -p "$(dirname "$LOG")"

today="$(date -u +%Y-%m-%d)"
{
    echo "==> $(date -u +%FT%TZ) starting trend_perf_report wrapper (today=$today, target=$TARGET_DATE)"
    if [ "$today" != "$TARGET_DATE" ]; then
        echo "    date guard: today != $TARGET_DATE; exiting without running."
        exit 0
    fi

    cd "$REPO" || { echo "❌ cannot cd $REPO"; exit 2; }
    git pull --rebase --autostash || echo "⚠ git pull failed; continuing with local copy"

    out_file="docs/trend_perf_${today}.md"
    PYTHONPATH=. python3 scripts/trend_perf_report.py --out "$out_file" \
        > /tmp/trend_perf_run.txt 2>&1
    rc=$?
    cat /tmp/trend_perf_run.txt

    if [ $rc -ne 0 ]; then
        msg="❌ trend_perf_report exited rc=$rc — see $LOG"
    else
        # Last non-empty line of the script output is the verdict.
        verdict="$(grep -E '^[⚠✅⚖❌]' /tmp/trend_perf_run.txt | tail -1)"
        msg="📊 marketing-agent retro $today: ${verdict:-(verdict missing — see $out_file)}"
    fi

    # Try solo-founder-os notifier fan-out; fall back to macOS native.
    if python3 -c "import solo_founder_os" 2>/dev/null; then
        python3 - <<EOF || true
from solo_founder_os.notifier import fan_out
fan_out(["ntfy", "telegram", "slack"], """${msg//\"/\\\"}""",
         title="marketing-agent trend retro")
EOF
    fi
    osascript -e "display notification \"${msg//\"/\\\"}\" with title \"marketing-agent retro\" sound name \"Glass\"" 2>/dev/null || true

    # Self-uninstall — never fire again.
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "==> $(date -u +%FT%TZ) wrapper done; plist removed."
} >> "$LOG" 2>&1
