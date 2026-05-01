#!/usr/bin/env bash
# run_ph_day_reminder.sh — PH-day 5/4 manual-paste reminder.
#
# Fired by ~/Library/LaunchAgents/com.alexji.vibex-ph-day-reminder.plist
# at 2026-05-04 08:55 EDT (≈12:55 UTC). Sends a macOS notification
# reminding to manually paste the polished thread + cross-platform
# copies. Then self-uninstalls so it never fires again.
#
# Why a reminder + manual paste?
#   - X API secrets aren't configured in GH Actions, so queue/approved/
#     can't auto-publish on PH day even if pre-staged.
#   - Polished x-thread-ph-day.md is 5 separate tweets; queue's
#     1-file=1-post model doesn't cover thread posting.
#   - PH-day stakes mean manual paste is unambiguously safer.

set -u

REPO="/Users/alexji/Desktop/orallexa-marketing-agent"
TARGET_DATE="2026-05-04"
PLIST="$HOME/Library/LaunchAgents/com.alexji.vibex-ph-day-reminder.plist"
LOG="$HOME/.marketing_agent/ph_day_reminder_$(date -u +%Y-%m-%d).log"
mkdir -p "$(dirname "$LOG")"

today="$(date -u +%Y-%m-%d)"
{
    echo "==> $(date -u +%FT%TZ) ph-day reminder fired (today=$today, target=$TARGET_DATE)"
    if [ "$today" != "$TARGET_DATE" ]; then
        echo "    date guard: today != $TARGET_DATE; skipping reminder."
        exit 0
    fi

    msg="🚀 VibeXForge PH 5/4 — manual paste time. Open ~/Desktop/orallexa-marketing-agent/docs/vibex-launch/polished/x-thread-ph-day.md and post the 5-tweet thread on X. Then bluesky-, mastodon-, linkedin-, jike-ph-day.md cross-post."

    osascript -e "display notification \"${msg//\"/\\\"}\" with title \"VibeXForge PH-day — manual paste\" sound name \"Glass\"" 2>/dev/null || true
    osascript -e "display alert \"VibeXForge PH-day reminder\" message \"${msg//\"/\\\"}\" buttons {\"OK\"}" 2>/dev/null &

    # Best-effort solo-founder-os notify too (push to phone if configured).
    if python3 -c "import solo_founder_os" 2>/dev/null; then
        python3 - <<EOF || true
from solo_founder_os.notifier import fan_out
fan_out(["ntfy", "telegram", "slack"],
         """${msg//\"/\\\"}""",
         title="VibeXForge PH-day reminder")
EOF
    fi

    # Self-uninstall — never fire again.
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "==> $(date -u +%FT%TZ) reminder done; plist removed."
} >> "$LOG" 2>&1
