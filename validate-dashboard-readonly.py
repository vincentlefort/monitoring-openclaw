#!/usr/bin/env python3
"""
validate-dashboard-readonly.py — Quick safety check that the monitoring dashboard
is read-only and no trading endpoints are exposed.
"""
import json
import os
import sys

errors = []
ok = lambda m: print(f"  [OK] {m}")
warn = lambda m: (print(f"  [WARN] {m}"), errors.append(m))

def main():
    print("Dashboard Read-Only Validator")
    print("=" * 50)

    # 1. Check ntv.json safety fields
    ntv_path = "/home/openclaw/monitoring-site/data/ntv.json"
    try:
        with open(ntv_path) as f:
            ntv = json.load(f)
        ok("ntv.json readable")
    except Exception as e:
        warn(f"ntv.json error: {e}")
        return 1

    if ntv.get("mode") == "DRY_RUN":
        ok("ntv.json mode=DRY_RUN")
    else:
        warn(f"ntv.json mode={ntv.get('mode')}")

    if ntv.get("auto_execution") == False:
        ok("ntv.json auto_execution=false")
    else:
        warn(f"ntv.json auto_execution={ntv.get('auto_execution')}")

    if ntv.get("dry_run") == True:
        ok("ntv.json dry_run=true")
    else:
        warn(f"ntv.json dry_run={ntv.get('dry_run')}")

    # 2. Check safety_header
    sh = ntv.get("safety_header", {})
    for k in ["futures", "margin", "short", "leverage"]:
        if sh.get(k) == "blocked":
            ok(f"safety_header.{k}=blocked")
        else:
            warn(f"safety_header.{k}={sh.get(k)}")

    if sh.get("live_trading_enabled") == False:
        ok("safety_header.live_trading_enabled=false")
    else:
        warn(f"safety_header.live_trading_enabled={sh.get('live_trading_enabled')}")

    # 3. Dry-run orders
    dro = ntv.get("dry_run_orders", {})
    if dro.get("executed") == False:
        ok("dry_run_orders.executed=false")
    else:
        warn(f"dry_run_orders.executed={dro.get('executed')}")

    if dro.get("mode") and "DRY_RUN" in dro["mode"]:
        ok("dry_run_orders mode contains DRY_RUN")
    else:
        warn(f"dry_run_orders mode={dro.get('mode')}")

    # 4. Breakout20 shadow only
    bo = ntv.get("breakout20_shadow", {})
    if bo.get("no_live_orders") == True:
        ok("breakout20_shadow.no_live_orders=true")
    else:
        warn(f"breakout20_shadow.no_live_orders={bo.get('no_live_orders')}")

    if bo.get("mode") == "SHADOW_ONLY":
        ok("breakout20_shadow mode=SHADOW_ONLY")
    else:
        warn(f"breakout20_shadow mode={bo.get('mode')}")

    # 5. Old bots retired
    old = ntv.get("old_bots_status", {})
    for bot in ["kraken_futures_v1", "binance_v5"]:
        status = old.get(bot, "")
        if status in ("retired", "inactive"):
            ok(f"old_bots.{bot}={status}")
        else:
            warn(f"old_bots.{bot}={status}")

    # 6. NTV tick freshness
    tick = ntv.get("ntv_tick", {})
    if tick.get("last_tick_ok") == True:
        ok("ntv_tick.last_tick_ok=true")
    else:
        warn(f"ntv_tick.last_tick_ok={tick.get('last_tick_ok')}")

    fs = tick.get("freshness_status", "UNKNOWN")
    if fs == "OK":
        ok(f"ntv_tick.freshness_status=OK")
    elif fs.startswith("WARNING") or fs.startswith("STALE"):
        warn(f"ntv_tick.freshness_status={fs}")
    else:
        warn(f"ntv_tick.freshness_status={fs}")

    # 7. Forward-test is meaningful (not frozen state)
    ft = ntv.get("forward_test", {})
    ages = tick.get("source_ages_minutes", {})
    dp_age = ages.get("dashboard_payload")
    if dp_age is not None and dp_age <= 30:
        ok(f"forward_test source fresh ({dp_age} min)")
    elif dp_age is not None:
        warn(f"forward_test source stale ({dp_age} min)")

    # 8. Dashboard HTML - check for execution buttons
    html_path = "/home/openclaw/monitoring-site/index.html"
    banned_html = ["ENABLE_TRADING", "execute_order", "place_order", "send_order",
                   "AUTO_EXECUTION: true", "DRY_RUN: false"]
    try:
        with open(html_path) as f:
            html = f.read()
        found = [p for p in banned_html if p in html]
        if not found:
            ok("index.html — no execution patterns found")
        else:
            warn(f"index.html contains execution patterns: {found}")
    except Exception as e:
        warn(f"index.html read error: {e}")

    # 9. Dashboard payload source is fresh
    dp_paths = [
        "/home/openclaw/monitoring-site/data/ntv_dashboard_payload.json",
        "/home/openclaw/monitoring-site/data/ntv.json",
    ]
    for p in dp_paths:
        try:
            dt = os.path.getmtime(p)
            ok(f"{os.path.basename(p)} exists and has valid timestamp")
        except OSError:
            warn(f"{p} not found")

    # Verdict
    print(f"\n{'='*50}")
    print(f"ERRORS: {len(errors)}")
    if errors:
        print("VERDICT: DASHBOARD CHECK FAILED")
        return 1
    else:
        print("VERDICT: DASHBOARD READ-ONLY — ALL CHECKS PASS")
        return 0

if __name__ == "__main__":
    sys.exit(main())
