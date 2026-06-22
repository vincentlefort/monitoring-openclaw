#!/usr/bin/env python3
"""
update-ntv-data.py — Copies Kraken Auto Spot NTV outputs to monitoring-site/data/ntv.json
Run after `python3 src/main.py` to update dashboard data.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

NTV_OUTPUT_DIR = "/home/openclaw/kraken_auto_spot_ntv/output"
DASHBOARD_DATA_DIR = "/home/openclaw/monitoring-site/data"
OUTPUT_FILE = os.path.join(DASHBOARD_DATA_DIR, "ntv.json")


def file_age_minutes(path):
    """Return age of file in minutes, or None if not found."""
    try:
        mtime = os.path.getmtime(path)
        age_seconds = (datetime.now(timezone.utc) - datetime.fromtimestamp(mtime, tz=timezone.utc)).total_seconds()
        return round(age_seconds / 60.0, 1)
    except OSError:
        return None


def tick_status():
    """Read .tick_status.json if present."""
    return safe_read_json(os.path.join(NTV_OUTPUT_DIR, ".tick_status.json"))


def safe_read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"WARNING: Cannot read {path}: {e}")
        return None


def main():
    os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)

    dashboard = safe_read_json(os.path.join(NTV_OUTPUT_DIR, "dashboard_payload.json"))
    signal = safe_read_json(os.path.join(NTV_OUTPUT_DIR, "signal.json"))
    orders_dry = safe_read_json(os.path.join(NTV_OUTPUT_DIR, "orders_dry_run.json"))
    alerts = safe_read_json(os.path.join(NTV_OUTPUT_DIR, "alerts.json"))

    fused = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "DRY_RUN",
        "auto_execution": False,
        "dry_run": True,

        "safety_header": {
            "model": "Naive Trend+Vol Model A (Kraken Auto Spot NTV)",
            "mode": dashboard.get("mode", "DRY_RUN") if dashboard else "DRY_RUN",
            "live_trading_enabled": dashboard.get("live_trading_enabled", False) if dashboard else False,
            "auto_execution": False,
            "futures": "blocked",
            "margin": "blocked",
            "short": "blocked",
            "leverage": "blocked",
            "kill_switch_status": "inactive",
            "data_status": "ok" if dashboard else "missing",
            "last_update": dashboard.get("timestamp", "") if dashboard else "",
        },

        "current_signal": {
            "btc": {
                "close": signal.get("btc_close") if signal else None,
                "sma200": signal.get("btc_sma200") if signal else None,
                "vol30": signal.get("btc_vol30") if signal else None,
                "trend_ok": signal.get("btc_trend_ok") if signal else None,
                "vol_ok": signal.get("btc_vol_ok") if signal else None,
                "allowed": signal.get("btc_allowed") if signal else None,
                "block_reason": "close < SMA200" if (signal and not signal.get("btc_trend_ok")) else (
                    "vol30 > 100%" if (signal and not signal.get("btc_vol_ok")) else ""
                ),
            },
            "eth": {
                "close": signal.get("eth_close") if signal else None,
                "sma200": signal.get("eth_sma200") if signal else None,
                "vol30": signal.get("eth_vol30") if signal else None,
                "trend_ok": signal.get("eth_trend_ok") if signal else None,
                "vol_ok": signal.get("eth_vol_ok") if signal else None,
                "allowed": signal.get("eth_allowed") if signal else None,
                "block_reason": "close < SMA200 and vol30 > 100%" if (signal and not signal.get("eth_trend_ok") and not signal.get("eth_vol_ok")) else (
                    "close < SMA200" if (signal and not signal.get("eth_trend_ok")) else (
                        "vol30 > 100%" if (signal and not signal.get("eth_vol_ok")) else ""
                    )
                ),
            },
            "allocation_tier": signal.get("allocation_tier", "unknown") if signal else "unknown",
        },

        "allocation": {
            "current": dashboard.get("current_allocation", {}) if dashboard else {},
            "target": dashboard.get("target_allocation", {}) if dashboard else {},
            "deviation": dashboard.get("allocation_deviation", {}) if dashboard else {},
            "recommended_action": ("REBALANCE" if any(
                abs(v) >= 5.0 for v in (dashboard.get("allocation_deviation", {}) if dashboard else {}).values()
            ) else "HOLD"),
        },

        "dry_run_orders": {
            "mode": "DRY_RUN — simulated only",
            "orders": orders_dry.get("orders", []) if orders_dry else [],
            "executed": False,
            "estimated_costs": dashboard.get("estimated_costs", []) if dashboard else [],
        },

        "breakout20_shadow": {
            "mode": "SHADOW_ONLY",
            "no_live_orders": True,
            "status": dashboard.get("breakout20_shadow_signal", {}) if dashboard else {},
        },

        "alerts": alerts.get("alerts", []) if alerts else [],

        "old_bots_status": {
            "kraken_futures_v1": "retired",
            "binance_v5": "retired",
            "kraken_auto_spot_ntv": "active — DRY_RUN",
        },

        "safety_status": dashboard.get("safety_status", {}) if dashboard else {},
    }

    # ── NTV Tick Freshness ──
    ts = tick_status() or {}
    tick_ok = ts.get("ntv_tick_ok", False)
    tick_time = ts.get("ntv_tick_ts", "")

    source_paths = {
        "dashboard_payload": os.path.join(NTV_OUTPUT_DIR, "dashboard_payload.json"),
        "signal": os.path.join(NTV_OUTPUT_DIR, "signal.json"),
        "orders_dry_run": os.path.join(NTV_OUTPUT_DIR, "orders_dry_run.json"),
        "alerts": os.path.join(NTV_OUTPUT_DIR, "alerts.json"),
    }
    source_ages = {k: file_age_minutes(p) for k, p in source_paths.items()}
    source_timestamps = {}
    for k, p in source_paths.items():
        try:
            source_timestamps[k] = datetime.fromtimestamp(os.path.getmtime(p), tz=timezone.utc).isoformat()
        except OSError:
            source_timestamps[k] = None

    dp_age = source_ages.get("dashboard_payload")
    if dp_age is None:
        freshness_status = "UNKNOWN"
    elif dp_age > 1440:  # > 24h
        freshness_status = "UNSAFE — NTV source > 24h stale"
    elif dp_age > 120:   # > 2h
        freshness_status = "WARNING — NTV source > 2h stale"
    elif dp_age > 30:    # > 30min
        freshness_status = "STALE — NTV source > 30min"
    else:
        freshness_status = "OK"

    fused["ntv_tick"] = {
        "last_tick_ok": tick_ok,
        "last_tick_time": tick_time,
        "source_timestamps": source_timestamps,
        "source_ages_minutes": source_ages,
        "freshness_status": freshness_status,
    }

    # Forward-test summary
    ft_summary_path = "/home/openclaw/kraken_auto_spot_ntv/forward_test/forward_test_summary.json"
    ft_summary = safe_read_json(ft_summary_path)
    if ft_summary:
        ft_verdict = ft_summary.get("last_verdict", "UNKNOWN")
        # Downgrade verdict if source is stale
        if freshness_status.startswith("UNSAFE"):
            ft_verdict = "FORWARD_TEST_UNSAFE"
        elif freshness_status.startswith("WARNING"):
            ft_verdict = "FORWARD_TEST_WARNING"
        elif freshness_status.startswith("STALE") and ft_verdict == "FORWARD_TEST_OK":
            ft_verdict = "FORWARD_TEST_WARNING"

        fused["forward_test"] = {
            "status": ft_verdict,
            "days_observed": ft_summary.get("days_observed", 0),
            "last_snapshot_time": ft_summary.get("last_snapshot_time", ""),
            "last_verdict": ft_verdict,
            "warnings_count": ft_summary.get("total_warnings", 0),
            "unsafe_count": ft_summary.get("unsafe_days", 0),
            "total_snapshots": ft_summary.get("total_snapshots", 0),
            "date_range": ft_summary.get("date_range", {}),
        }

    # Safeguard: never show live_trading_enabled=true unless ALL conditions met
    if fused.get("live_trading_enabled"):
        fused["live_trading_enabled"] = False

    with open(OUTPUT_FILE, "w") as f:
        json.dump(fused, f, indent=2)

    print(f"NTV data exported to {OUTPUT_FILE}")

    # Also copy raw dashboard_payload.json for direct access
    raw_path = os.path.join(DASHBOARD_DATA_DIR, "ntv_dashboard_payload.json")
    if dashboard:
        with open(raw_path, "w") as f:
            json.dump(dashboard, f, indent=2)
        print(f"Raw dashboard payload copied to {raw_path}")


if __name__ == "__main__":
    main()
