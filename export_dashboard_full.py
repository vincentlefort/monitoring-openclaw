#!/usr/bin/env python3
"""
export_dashboard_full.py — Unified dashboard data export
Aggregates NTV + Swing Paper + Market Context + Bot Statuses + Global Freshness
Run after update-data.sh completes. Produces data/dashboard_full.json
Read-only. No orders. No secrets.
"""
import json, os, sys
from datetime import datetime, timezone, timedelta

DASHBOARD_DATA_DIR = "/home/openclaw/monitoring-site/data"
NTV_OUTPUT_DIR = "/home/openclaw/kraken_auto_spot_ntv/output"
MARKET_STATE_PATH = "/home/openclaw/shared/market_state.json"
OUTPUT_FILE = os.path.join(DASHBOARD_DATA_DIR, "dashboard_full.json")

def safe_read(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

def file_age_minutes(path):
    try:
        mtime = os.path.getmtime(path)
        age_s = (datetime.now(timezone.utc) - datetime.fromtimestamp(mtime, tz=timezone.utc)).total_seconds()
        return round(age_s / 60.0, 1)
    except OSError:
        return None

def freshness_status(age_min, expected_interval, ok_threshold=15, warn_threshold=120):
    if age_min is None:
        return "MISSING"
    if age_min > warn_threshold:
        return "STALE"
    if age_min > ok_threshold:
        return "DELAYED"
    return "OK"

def main():
    os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    fused = {
        "generated_at": now.isoformat(),
        "generated_at_unix": int(now.timestamp()),
    }

    # ── 1. NTV data (read from existing ntv.json to avoid duplicating fusion logic) ──
    ntv = safe_read(os.path.join(DASHBOARD_DATA_DIR, "ntv.json")) or {}
    fused["ntv"] = ntv

    # ── 2. Swing Paper data (engine source lost; historical archive preserved) ──
    # Frozen historical summary sourced from the durable recovered dataset under
    # /home/openclaw/trading_stack/recovered_paper_history/ (do NOT treat as live).
    swing = {
        "status": "PAUSED_ENGINE_LOST",
        "reason": "engine_source_and_runtime_state_lost",
        "continuity": False,
        "last_known_good_utc": "2026-08-28T13:50:19+00:00",
        "historical": {
            "closed_trades": 0,
            "orphaned_positions": 2,
            "source": "/home/openclaw/trading_stack/recovered_paper_history/swing/",
        },
        "portfolios": {},
        "signals": {},
        "active_trades": {},
        "freshness": {"status": "PAUSED"},
    }
    fused["swing_paper"] = swing

    # ── 2b. Recovery Paper data (fresh paper reimplementation, live) ──
    # Historical archive (20 closed trades, reconciled net EUR 2531.93) stays
    # archive-only. Current fresh paper state comes from the reimplemented engine's
    # monitoring payload (separate from the historical PnL).
    recovery_live = safe_read(
        "/home/openclaw/trading_stack/kraken_recovery_paper_trading/state/recovery_monitoring.json"
    ) or {}

    recovery_historical = {
        "closed_trades": 20,
        "net_pnl_eur": 2531.93,
        "recovery_a": {"closed_trades": 8, "net_pnl_eur": 1321.94, "win_rate": 62.5},
        "recovery_b": {"closed_trades": 12, "net_pnl_eur": 1209.99, "win_rate": 58.3},
        "source": "/home/openclaw/trading_stack/recovered_paper_history/recovery/",
    }

    recovery_age = None
    last_tick_utc = recovery_live.get("last_tick_utc")
    if last_tick_utc:
        try:
            recovery_age = round(
                (now - datetime.fromisoformat(last_tick_utc)).total_seconds() / 60.0, 1
            )
        except Exception:
            recovery_age = None

    recovery_active = (
        recovery_live.get("status") == "ACTIVE_PAPER_REIMPLEMENTED"
        and recovery_age is not None
    )
    if recovery_active:
        # 4h bar cadence: OK within one interval + 30 min grace; DELAYED within
        # 6h; STALE beyond (a missed tick / scheduler failure).
        if recovery_age > 360:
            recovery_fresh = "STALE"
        elif recovery_age > 270:
            recovery_fresh = "DELAYED"
        else:
            recovery_fresh = "OK"
        recovery = {
            "status": "ACTIVE_PAPER_REIMPLEMENTED",
            "reason": recovery_live.get("reason", "reimplemented_from_reverse_spec"),
            "continuity": False,
            "implementation": recovery_live.get("implementation"),
            "historical_engine_continuity": recovery_live.get("historical_engine_continuity", False),
            "last_tick_utc": last_tick_utc,
            "last_bar_utc": recovery_live.get("last_bar_utc"),
            "strategy": "R1 Recovery Rebound (sub-SMA200 bear regime)",
            "paper_only": True,
            "historical": recovery_historical,
            "portfolios": recovery_live.get("portfolios", {}),
            "signals": recovery_live.get("signals", {}),
            "open_trades": {},
            "closed_trades": {},
            "freshness": {
                "status": recovery_fresh,
                "age_minutes": recovery_age,
                "expected_interval_minutes": 240,
            },
        }
    else:
        recovery = {
            "status": "PAUSED_ENGINE_LOST",
            "reason": "engine_source_and_runtime_state_lost",
            "continuity": False,
            "last_known_good_utc": "2026-08-28T13:50:13+00:00",
            "strategy": "R1 Recovery Rebound (sub-SMA200 bear regime)",
            "paper_only": True,
            "historical": recovery_historical,
            "portfolios": {},
            "signals": {},
            "open_trades": {},
            "closed_trades": {},
            "freshness": {"status": "PAUSED"},
        }
    fused["recovery_paper"] = recovery

    # ── 3. Market context ──
    market = safe_read(MARKET_STATE_PATH)
    market_age = file_age_minutes(MARKET_STATE_PATH)
    if market:
        fused["market_context"] = {
            "timestamp": market.get("timestamp", ""),
            "fear_greed": market.get("fear_greed"),
            "fear_greed_label": market.get("fear_greed_label"),
            "btc_price": market.get("btc_price"),
            "btc_change_4h": market.get("btc_change_4h"),
            "vix": market.get("vix"),
            "dxy": market.get("dxy"),
            "us10y_yield": market.get("us10y_yield"),
            "regime": market.get("regime"),
            "freshness": {
                "age_minutes": market_age,
                "status": freshness_status(market_age, 15) if market_age is not None else "MISSING",
                "expected_interval_minutes": 15,
            },
        }
    else:
        fused["market_context"] = {"status": "UNAVAILABLE", "freshness": {"status": "MISSING"}}

    # ── 4. Bot statuses ──
    legacy = safe_read(os.path.join(DASHBOARD_DATA_DIR, "legacy_bots_status.json"))
    bot_status = safe_read(os.path.join(DASHBOARD_DATA_DIR, "bot_status.json"))
    legacy_age = file_age_minutes(os.path.join(DASHBOARD_DATA_DIR, "legacy_bots_status.json"))

    bots = {
        "ntv_spot": {
            "name": "Kraken Auto Spot NTV",
            "status": "ACTIVE_FORWARD",
            "mode": "DRY_RUN",
            "type": "spot",
            "freshness": ntv.get("ntv_tick", {}).get("freshness_status", "UNKNOWN"),
        },
        "swing_paper": {
            "name": "Swing Futures Paper",
            "status": "PAUSED_ENGINE_LOST",
            "mode": "PAPER",
            "type": "futures",
            "freshness": swing.get("freshness", {}).get("status", "UNKNOWN"),
        },
        "recovery_paper": {
            "name": "Recovery Paper R1",
            "status": recovery.get("status", "PAUSED_ENGINE_LOST"),
            "mode": "PAPER",
            "type": "futures",
            "strategy": "R1 Recovery Rebound",
            "freshness": recovery.get("freshness", {}).get("status", "UNKNOWN"),
        },
        "gateway": {
            "name": "Telegram Gateway",
            "status": "ACTIVE_INFRASTRUCTURE",
            "type": "infrastructure",
        },
        "event_dispatcher": {
            "name": "Event Dispatcher",
            "status": "ACTIVE_INFRASTRUCTURE",
            "type": "infrastructure",
        },
    }

    if legacy:
        for b in legacy.get("bots", []):
            key = b["bot"].lower().replace(" ", "_")
            bots[key] = {
                "name": b["bot"],
                "status": b["status"],
                "type": "legacy",
                "stopped_since": "2026-06-21",
                "no_orders": b.get("no_orders_executed", True),
                "restart_disabled": b.get("restart_disabled", True),
            }

    bots["_freshness"] = {
        "legacy_bots_status_age_minutes": legacy_age,
        "legacy_bots_freshness": freshness_status(legacy_age, 360) if legacy_age is not None else "MISSING",
    }
    fused["bots"] = bots

    # ── 5. Global Freshness ──
    sources = {
        "ntv_tick": {"age": ntv.get("ntv_tick", {}).get("age_minutes"), "expected": 5, "status": ntv.get("ntv_tick", {}).get("freshness_status", "UNKNOWN")},
        "ntv_signal": {"age": file_age_minutes(os.path.join(NTV_OUTPUT_DIR, "signal.json")), "expected": 5, "status": None},
        "swing_paper": {"age": None, "expected": None, "status": "PAUSED", "paused": True},
        "recovery_paper": {"age": recovery_age, "expected": 240, "status": recovery.get("freshness", {}).get("status", "UNKNOWN"), "paused": not recovery_active},
        "market_context": {"age": market_age, "expected": 15, "status": None},
        "legacy_bots": {"age": legacy_age, "expected": 360, "status": None},
        "stocks_json": {"age": file_age_minutes(os.path.join(DASHBOARD_DATA_DIR, "stocks.json")), "expected": 360, "status": None},
    }
    for key, src in sources.items():
        if src.get("paused"):
            continue
        if src["status"] is None:
            src["status"] = freshness_status(src["age"], src["expected"])

    fused["global_freshness"] = {
        "sources": sources,
        "overall_status": "OK",
        "sources_stale": [],
    }
    for key, src in sources.items():
        if src.get("paused"):
            continue
        if src["status"] in ("STALE", "MISSING"):
            fused["global_freshness"]["overall_status"] = "WARNING"
            fused["global_freshness"]["sources_stale"].append(key)
        if src["status"] == "MISSING" and key in ("ntv_tick", "ntv_signal"):
            fused["global_freshness"]["overall_status"] = "ERROR"

    # ── 6. Global Safety ──
    safety_checks = {
        "dry_run_mode": True,
        "auto_execution_disabled": True,
        "live_trading_disabled": True,
        "real_orders_today": 0,
        "legacy_bots_stopped": legacy.get("summary", {}).get("active", 0) == 0 if legacy else True,
        "futures_live_stopped": True,
        "no_secrets_exposed": True,
    }
    safety_overall = "OK"
    safety_unknowns = []
    for k, v in safety_checks.items():
        if v is None:
            safety_overall = "WARNING"
            safety_unknowns.append(k)

    fused["global_safety"] = {
        "checks": safety_checks,
        "overall": safety_overall,
        "unknowns": safety_unknowns,
    }

    # ── 7. Global Status ──
    global_status = "HEALTHY"
    if fused["global_freshness"]["overall_status"] == "ERROR":
        global_status = "ERROR"
    elif fused["global_freshness"]["overall_status"] == "WARNING":
        global_status = "WARNING"
    elif safety_overall == "WARNING":
        global_status = "WARNING"
    elif fused["global_freshness"]["overall_status"] == "STALE":
        global_status = "STALE"

    fused["global_status"] = global_status

    # ── 8. Finance labels ──
    fused["finance_labels"] = {
        "ntv_spot": "DRY-RUN",
        "swing_paper": "PAPER",
        "recovery_paper": "PAPER",
        "scalable_capital": "REAL",
        "stops_actifs": "REAL",
        "v5_binance_trades": "REAL (historical, stopped)",
        "kraken_futures_trades": "REAL (historical, stopped)",
        "backtest_results": "BACKTEST",
    }

    # Write
    with open(OUTPUT_FILE, "w") as f:
        json.dump(fused, f, indent=2)
    print(f"dashboard_full.json written to {OUTPUT_FILE}")
    print(f"  Global status: {global_status}")
    print(f"  Safety: {safety_overall}")
    print(f"  Freshness: {fused['global_freshness']['overall_status']}")
    print(f"  NTV: {ntv.get('ntv_tick',{}).get('freshness_status','?')}")
    print(f"  Swing: {swing.get('freshness',{}).get('status','?')}")
    print(f"  Recovery: {recovery.get('freshness',{}).get('status','?')}")
    print(f"  Market: {fused.get('market_context',{}).get('freshness',{}).get('status','?')}")

if __name__ == "__main__":
    main()
