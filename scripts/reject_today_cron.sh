#!/usr/bin/env bash
# reject_today_cron.sh — bulk-reject cron-generated drafts from today.
#
# On PH day (5/4) the daily.yml cron writes ~12 generic drafts to
# queue/pending/. They're harmless (won't auto-post), but they pollute
# the bandit feedback signal and clutter the queue. This helper moves
# every queue/pending/<today's UTC date>* file to queue/rejected/ in
# one shot, so PH-day cleanup is a single command.
#
# Usage:
#   bash scripts/reject_today_cron.sh                 # reject UTC today's
#   bash scripts/reject_today_cron.sh 20260504        # reject specific date
#   bash scripts/reject_today_cron.sh 20260504 dry    # preview only

set -u
cd "$(dirname "$0")/.."   # run from repo root

DATE="${1:-$(date -u +%Y%m%d)}"
DRY="${2:-}"

shopt -s nullglob
matches=( queue/pending/${DATE}T*.md )
shopt -u nullglob

if [ "${#matches[@]}" -eq 0 ]; then
    echo "(nothing matches queue/pending/${DATE}T*.md — exiting)"
    exit 0
fi

echo "found ${#matches[@]} draft(s) for $DATE in queue/pending/:"
for f in "${matches[@]}"; do
    plat=$(grep -m1 '^platform:' "$f" | awk '{print $2}')
    proj=$(grep -m1 '^project:'  "$f" | sed 's/^project: //')
    echo "  · $(basename "$f")  [${plat:-?}] ${proj:-?}"
done

if [ "$DRY" = "dry" ]; then
    echo "(dry-run — no files moved)"
    exit 0
fi

echo
read -r -p "move all to queue/rejected/? [y/N] " ans
case "${ans:-N}" in
    y|Y|yes) ;;
    *) echo "(aborted)"; exit 0;;
esac

for f in "${matches[@]}"; do
    git mv "$f" "queue/rejected/$(basename "$f")"
done

echo "moved ${#matches[@]} → queue/rejected/. Commit + push manually:"
echo "  git commit -m 'chore(queue): reject ${#matches[@]} cron drafts ($DATE)'"
echo "  git push"
