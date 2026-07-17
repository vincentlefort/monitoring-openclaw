#!/bin/bash
# run-monitoring-tick.sh — NTV DRY_RUN tick + dashboard export + git push.
#
# HOTFIX 2026-07-17 (audit INC-2): the old */5min crontab entry disappeared
# silently on 2026-07-01 during a scripted crontab rewrite. The scheduler now
# lives in systemd user units (ntv-monitoring.timer), which are files on disk
# and cannot be wiped by crontab edits:
#   ~/.config/systemd/user/ntv-monitoring.service
#   ~/.config/systemd/user/ntv-monitoring.timer
#
# SAFETY: DRY_RUN only. This pipeline never places orders. AUTO_EXECUTION
# stays false in kraken_auto_spot_ntv/config.yaml. No API keys used.
set -u
cd /home/openclaw/monitoring-site || exit 1

LOG=/home/openclaw/scripts/monitoring.log
{
    echo "=== ntv-monitoring tick $(date -Iseconds) ==="

    bash update-data.sh
    UPDATE_STATUS=$?

    # Dashboard deployment (Vercel serves the git repo) — best effort,
    # a push failure must never block the tick itself.
    git add data/ >/dev/null 2>&1
    if ! git diff --cached --quiet 2>/dev/null; then
        git commit -m "auto update" >/dev/null 2>&1 || true
        git push >/dev/null 2>&1 || echo "WARN: git push failed (non-blocking)"
    fi

    echo "=== tick done status=$UPDATE_STATUS $(date -Iseconds) ==="
    exit $UPDATE_STATUS
} >> "$LOG" 2>&1
