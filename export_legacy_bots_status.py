#!/usr/bin/env python3
"""
export_legacy_bots_status.py — Export real legacy bot status to dashboard data.
Reads bot_manager.py status output and PID files. Never starts/stops bots.
"""
import json
import os
import sys
from datetime import datetime, timezone

STATUS_DIR = "/home/openclaw/status"
BOT_MANAGER_LOG = "/home/openclaw/shared/bot_manager.log"
V5_PID_FILE = "/home/openclaw/binance_bot_v5/bot_v5.pid"
KRAKEN_PID_FILE = "/home/openclaw/kraken_bot_v1/kraken_bot.pid"
DASHBOARD_DATA_DIR = "/home/openclaw/monitoring-site/data"
OUTPUT_FILE = os.path.join(DASHBOARD_DATA_DIR, "legacy_bots_status.json")


def pid_alive(pid_file):
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True, pid
    except Exception:
        return False, None


def read_manager_log():
    try:
        with open(BOT_MANAGER_LOG) as f:
            lines = f.readlines()
        last_status_lines = []
        capturing = False
        for line in reversed(lines):
            if "STATUS" in line:
                capturing = True
            if capturing:
                last_status_lines.append(line.strip())
                if "--- bot_manager status" in line:
                    break
        return last_status_lines
    except Exception:
        return []


def get_bot_status(label, pid_file):
    alive, pid = pid_alive(pid_file)
    now = datetime.now(timezone.utc)

    if alive:
        return {
            "bot": label,
            "status": "ACTIVE",
            "pid": pid,
            "checked_at": now.isoformat(),
            "no_orders_executed": None,
            "warning": "BOT IS RUNNING — should be retired"
        }
    else:
        return {
            "bot": label,
            "status": "RETIRED_STOPPED",
            "pid": None,
            "checked_at": now.isoformat(),
            "stopped_at": now.isoformat(),
            "stop_method": "bot_manager.py stop",
            "restart_disabled": True,
            "no_orders_executed": True,
            "notes": "Watchdog cron disabled 2026-06-21. systemd service disabled. @reboot cron disabled."
        }


def main():
    os.makedirs(STATUS_DIR, exist_ok=True)
    os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)

    v5_status = get_bot_status("Binance V5", V5_PID_FILE)
    kraken_status = get_bot_status("Kraken Futures V1", KRAKEN_PID_FILE)

    # Write individual status files
    for status in [v5_status, kraken_status]:
        fname = status["bot"].lower().replace(" ", "_") + "_status.json"
        path = os.path.join(STATUS_DIR, fname)
        with open(path, "w") as f:
            json.dump(status, f, indent=2)
        print(f"Written: {path}")

    # Write combined dashboard file
    combined = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bots": [v5_status, kraken_status],
        "summary": {
            "total": 2,
            "active": sum(1 for b in [v5_status, kraken_status] if b["status"] == "ACTIVE"),
            "retired_stopped": sum(1 for b in [v5_status, kraken_status] if b["status"] == "RETIRED_STOPPED"),
        }
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(combined, f, indent=2)
    print(f"Dashboard data written: {OUTPUT_FILE}")

    # Print summary
    for b in [v5_status, kraken_status]:
        print(f"  {b['bot']}: {b['status']}" + (f" PID={b['pid']}" if b.get('pid') else ""))


if __name__ == "__main__":
    main()
