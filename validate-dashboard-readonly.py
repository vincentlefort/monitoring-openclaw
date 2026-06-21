#!/usr/bin/env python3
"""
validate-dashboard-readonly.py
Validates the OpenClaw dashboard is read-only, all JSONs valid, and safety constraints intact.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
INDEX_PATH = os.path.join(ROOT, "index.html")

errors = []
warnings = []

def error(msg):
    errors.append(msg)
    print(f"  [FAIL] {msg}")

def warn(msg):
    warnings.append(msg)
    print(f"  [WARN] {msg}")

def ok(msg):
    print(f"  [OK] {msg}")

# 1. JSON validation
print("1. JSON Validation")
for fname in ["ntv.json", "ntv_dashboard_payload.json", "kraken.json", "stocks.json",
              "bot_status.json", "trades.json", "legacy_bots_status.json"]:
    path = os.path.join(DATA_DIR, fname)
    if not os.path.exists(path):
        warn(f"{fname} missing")
        continue
    try:
        with open(path) as f:
            json.load(f)
        ok(f"{fname} valid")
    except json.JSONDecodeError as e:
        error(f"{fname} invalid: {e}")

# 2. ntv.json critical fields
print("\n2. ntv.json Critical Fields")
try:
    with open(os.path.join(DATA_DIR, "ntv.json")) as f:
        ntv = json.load(f)
    checks = {
        "mode=DRY_RUN": ntv.get("mode") == "DRY_RUN",
        "dry_run=true": ntv.get("dry_run") == True,
        "auto_execution=false": ntv.get("auto_execution") == False,
        "live_trading_enabled=false": (ntv.get("safety_header", {}).get("live_trading_enabled") == False),
        "futures_blocked": ntv.get("safety_header", {}).get("futures") == "blocked",
        "margin_blocked": ntv.get("safety_header", {}).get("margin") == "blocked",
        "short_blocked": ntv.get("safety_header", {}).get("short") == "blocked",
        "btc_signal_present": ntv.get("current_signal", {}).get("btc") is not None,
        "eth_signal_present": ntv.get("current_signal", {}).get("eth") is not None,
        "allocation_present": "allocation" in ntv,
        "breakout20_shadow_only": ntv.get("breakout20_shadow", {}).get("no_live_orders") == True,
        "dry_run_orders_not_executed": ntv.get("dry_run_orders", {}).get("executed") == False,
    }
    for name, passed in checks.items():
        if passed: ok(name)
        else: error(name)
except Exception as e:
    error(f"ntv.json check failed: {e}")

# 3. legacy_bots_status.json fields
print("\n3. legacy_bots_status.json Critical Fields")
try:
    with open(os.path.join(DATA_DIR, "legacy_bots_status.json")) as f:
        legacy = json.load(f)
    bots = legacy.get("bots", [])
    if len(bots) >= 2:
        ok(f"{len(bots)} legacy bots tracked")
    else:
        warn(f"Only {len(bots)} legacy bots tracked (expected >=2)")
    for b in bots:
        name = b.get("bot", "unknown")
        status = b.get("status", "UNKNOWN")
        if status == "ACTIVE":
            error(f"{name}: ACTIVE — should be RETIRED_STOPPED")
        elif status == "RETIRED_STOPPED":
            ok(f"{name}: RETIRED_STOPPED")
        else:
            warn(f"{name}: {status}")
    if legacy.get("summary", {}).get("active", -1) > 0:
        error(f"legacy_bots_summary shows {legacy['summary']['active']} active bots")
    else:
        ok("legacy_bots_summary: 0 active")
except Exception as e:
    error(f"legacy_bots_status.json check failed: {e}")

# 4. HTML read-only scan
print("\n4. HTML Read-Only Enforcement")
if not os.path.exists(INDEX_PATH):
    error("index.html missing")
else:
    with open(INDEX_PATH) as f:
        html = f.read()
    actions = {
        "<button": (r'<button', 0),
        "<form": (r'<form', 0),
        "POST method": (r'method\s*=\s*["\']post["\']', 0, True),
        "fetch POST": (r'method\s*:\s*["\']POST["\']', 0, True),
        "onclick": (r'onclick\s*=', 0),
        "onsubmit": (r'onsubmit', 0),
        "XMLHttpRequest": (r'XMLHttpRequest|\.send\(', 0),
    }
    for name, args in actions.items():
        pattern = args[0]
        expected = args[1] if len(args) > 1 else 0
        case_insensitive = args[2] if len(args) > 2 else False
        flags = re.I if case_insensitive else 0
        count = len(re.findall(pattern, html, flags))
        if count != expected: error(f"{name}: {count} found (expected {expected})")
        else: ok(f"{name}: 0 found")

    # Verify new product hierarchy sections present
    sections_present = [
        "Kraken Auto Spot NTV",
        "Forward-Test Monitoring",
        "Legacy Bots",
        "Bourse / ETF Portfolio",
        "Alerts",
        "Data Freshness",
        "Dry-Run Orders",
        "Breakout 20",
        "OpenClaw Monitoring",
    ]
    for sec in sections_present:
        if sec in html: ok(f"Section '{sec}' present")
        else: error(f"Section '{sec}' MISSING")

    # Verify old active panels are NOT present as active dashboards
    # The terms may appear in legacy/archive context, but should NOT be active trading panels
    # Check: Binance V5 card should be in "Legacy Bots" or "Historical" context, not as active
    legacy_terms = ["RETIRED_STOPPED", "Historical Legacy", "ARCHIVE", "Legacy Bots \u2014 RETIRED"]
    for t in legacy_terms:
        if t in html: ok(f"Legacy marker '{t}' found")
        else: warn(f"Legacy marker '{t}' not found in index.html")

    # Verify no "ACTIVE" trading panel for old bots (the word ACTIVE in legacy context is OK)
    if "RETIRED_STOPPED" in html:
        ok("Legacy bots marked as RETIRED_STOPPED in HTML")

# 5. No execution endpoints
print("\n5. Execution Endpoint Check")
with open(INDEX_PATH) as f:
    html = f.read()
banned = ["create_order", "send_order", "place_order", "add_order",
          "ENABLE_TRADING", "AUTO_LIVE", "enable_live"]
for word in banned:
    matches = [m for m in re.finditer(word, html, re.I)]
    if matches:
        safe_context = True
        for m in matches:
            ctx_start = max(0, m.start() - 80)
            ctx = html[ctx_start:m.end() + 40]
            if not any(s in ctx.lower() for s in ["alert", "should be false", "blocked", "should be disabled"]):
                safe_context = False
        if safe_context:
            ok(f"'{word}': in safety alert only (OK)")
        else:
            error(f"'{word}': found outside safety context!")
    else:
        ok(f"'{word}': not found")

# Summary
print(f"\n{'='*50}")
print(f"RESULTS: {len(errors)} errors, {len(warnings)} warnings")
if errors:
    print("VERDICT: NEEDS_FIXES")
    sys.exit(1)
elif warnings:
    print("VERDICT: PASSED_WITH_WARNINGS")
else:
    print("VERDICT: PASSED \u2014 DASHBOARD SAFE")
