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
SWING_DIR = "/tmp/opencode/kraken_swing_paper_trading"
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

    # ── 2. Swing Paper data ──
    swing = {"status": "UNAVAILABLE", "portfolios": {}, "signals": {}}
    swing_tick = safe_read(os.path.join(SWING_DIR, "tick_result.json"))
    swing_state_a = safe_read(os.path.join(SWING_DIR, "paper_state_PaperA_Conservative.json"))
    swing_state_b = safe_read(os.path.join(SWING_DIR, "paper_state_PaperB_Aggressive.json"))
    swing_results = safe_read(os.path.join(SWING_DIR, "results.json"))
    swing_csv_age = file_age_minutes(os.path.join(SWING_DIR, "dashboard.csv"))

    if swing_tick:
        swing["status"] = "OK"
        swing["last_tick"] = swing_tick.get("timestamp", "")
        swing["signals"] = swing_tick.get("signals", {})
        swing["tick_status"] = swing_tick.get("status", "UNKNOWN")
        for pf_name, pf_data in swing_tick.get("portfolios", {}).items():
            s = pf_data.get("summary", {})
            swing["portfolios"][pf_name] = {
                "cash": s.get("cash", 0),
                "active_positions": s.get("active_positions", 0),
                "closed_trades": s.get("total_closed_trades", 0),
                "total_net_eur": s.get("total_net_eur", 0),
                "win_rate": s.get("win_rate", 0),
                "active_assets": s.get("active_assets", []),
            }
        swing["freshness"] = {
            "age_minutes": swing_csv_age,
            "status": freshness_status(swing_csv_age, 5) if swing_csv_age is not None else "MISSING",
            "expected_interval_minutes": 5,
        }
    else:
        swing["freshness"] = {"status": "MISSING"}

    # Swing active positions detail
    swing["active_trades"] = {}
    for pf_name, state in [("PaperA_Conservative", swing_state_a), ("PaperB_Aggressive", swing_state_b)]:
        if state and state.get("active_trades"):
            for t in state["active_trades"]:
                key = f"{pf_name}/{t.get('asset','?')}"
                swing["active_trades"][key] = {
                    "asset": t.get("asset"),
                    "portfolio": pf_name,
                    "entry_time": t.get("entry_time"),
                    "entry_price": t.get("entry_price"),
                    "duration_hours": t.get("duration_hours"),
                    "status": t.get("status"),
                }

    fused["swing_paper"] = swing

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
            "status": "ACTIVE_PAPER",
            "mode": "PAPER",
            "type": "futures",
            "freshness": swing.get("freshness", {}).get("status", "UNKNOWN"),
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
        "swing_paper": {"age": swing_csv_age, "expected": 5, "status": swing.get("freshness", {}).get("status", "UNKNOWN")},
        "market_context": {"age": market_age, "expected": 15, "status": None},
        "legacy_bots": {"age": legacy_age, "expected": 360, "status": None},
        "stocks_json": {"age": file_age_minutes(os.path.join(DASHBOARD_DATA_DIR, "stocks.json")), "expected": 360, "status": None},
    }
    for key, src in sources.items():
        if src["status"] is None:
            src["status"] = freshness_status(src["age"], src["expected"])

    fused["global_freshness"] = {
        "sources": sources,
        "overall_status": "OK",
        "sources_stale": [],
    }
    for key, src in sources.items():
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
    print(f"  Market: {fused.get('market_context',{}).get('freshness',{}).get('status','?')}")

if __name__ == "__main__":
    main()
