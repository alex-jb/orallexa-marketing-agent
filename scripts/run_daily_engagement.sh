#!/usr/bin/env bash
# run_daily_engagement.sh — fetch X metrics for every posted item +
# feed bandit. Closes the post → engagement → bandit loop.
#
# Fired by ~/Library/LaunchAgents/com.alexji.marketing-agent-daily-engagement.plist
# at 06:30 EDT daily — after overnight engagement settles, before the
# 14:00 UTC daily.yml cron writes new drafts.
#
# What it does:
#   1. For each queue/posted/*.md with a `<!-- posted_id: ... -->` footer:
#      - Run `marketing-agent engage --post-id <id>` (writes to engagement DB)
#   2. For each post with `variant_key: x:<style>`:
#      - Read peak like count from engagement DB via marketing_agent.engagement
#      - Call `marketing-agent bandit from-engagement x:<style> --engagement <n>`
#   3. Log to ~/.marketing_agent/engage_<UTC date>.log
#   4. Best-effort notify (osascript + solo-founder-os fan_out if configured)
#
# Idempotent: bandit gets re-updated each day with the latest peak metric.
# That's intentional — viral posts compound their reward signal over time.

set -u

REPO="/Users/alexji/Desktop/orallexa-marketing-agent"
ENV_FILE="$HOME/Desktop/orallexa-twitter-bot/.env"
LOG="$HOME/.marketing_agent/engage_$(date -u +%Y-%m-%d).log"
mkdir -p "$(dirname "$LOG")"

{
    echo "==> $(date -u +%FT%TZ) daily engagement run start"

    cd "$REPO" || { echo "❌ cannot cd $REPO"; exit 2; }

    # Load X creds (gh secrets aren't visible to local shell). The
    # engage path uses X_BEARER_TOKEN preferentially (v0.17.x fix).
    if [ -f "$ENV_FILE" ]; then
        # shellcheck disable=SC1090
        set -a
        # Only source X_* lines to avoid clobbering shell state.
        eval "$(grep '^X_' "$ENV_FILE" | sed 's/^/export /')"
        set +a
    else
        echo "⚠️  $ENV_FILE not found; engage will likely 401."
    fi

    posted_count=0
    bandit_updates=0
    skipped=0

    shopt -s nullglob
    for f in queue/posted/*.md; do
        # Extract posted_id from the trailing HTML comment
        post_id=$(grep -oE '<!-- posted_id: [^ ]+ -->' "$f" \
                       | head -1 | sed -E 's/<!-- posted_id: (.+) -->/\1/')
        if [ -z "$post_id" ]; then
            skipped=$((skipped + 1))
            continue
        fi

        # If posted_id is a URL (e.g. https://x.com/.../status/123), pull
        # the trailing numeric id.
        if [[ "$post_id" == *"/"* ]]; then
            post_id="${post_id##*/}"
        fi

        echo "→ engage post_id=$post_id  ($(basename "$f"))"
        eng_out=$(PYTHONPATH=. python3 -m marketing_agent engage \
                       --post-id "$post_id" 2>&1 \
                       | grep -v -E "Warning|warnings.warn|NotOpenSSL")
        echo "$eng_out"
        posted_count=$((posted_count + 1))

        # Feed bandit if this post had a variant_key tag
        vk=$(grep -m1 '^variant_key:' "$f" | awk '{print $2}')
        if [ -n "$vk" ] && [ "$vk" != "None" ] && [ "$vk" != "(none)" ]; then
            # Pull current peak like count from the engage output
            likes=$(echo "$eng_out" | awk '/^[ \t]+like[ \t]/ {print $2; exit}')
            if [ -n "$likes" ]; then
                echo "  bandit update: $vk likes=$likes"
                PYTHONPATH=. python3 -m marketing_agent bandit \
                    from-engagement "$vk" --engagement "$likes" 2>&1 \
                    | grep -v -E "Warning|warnings.warn|NotOpenSSL" | tail -1
                bandit_updates=$((bandit_updates + 1))
            fi
        fi
    done
    shopt -u nullglob

    echo
    echo "📊 bandit report:"
    PYTHONPATH=. python3 -m marketing_agent bandit report --min-pulls 1 2>&1 \
        | grep -v -E "Warning|warnings.warn|NotOpenSSL"

    summary="📊 daily engage: ${posted_count} posts pulled · ${bandit_updates} bandit updates · ${skipped} skipped"
    echo
    echo "$summary"

    osascript -e "display notification \"${summary//\"/\\\"}\" with title \"marketing-agent daily engage\" sound name \"Tink\"" 2>/dev/null || true
    if python3 -c "import solo_founder_os" 2>/dev/null; then
        python3 - <<EOF || true
from solo_founder_os.notifier import fan_out
fan_out(["ntfy", "telegram", "slack"], """${summary//\"/\\\"}""",
         title="marketing-agent daily engage")
EOF
    fi

    echo "==> $(date -u +%FT%TZ) done"
} >> "$LOG" 2>&1
