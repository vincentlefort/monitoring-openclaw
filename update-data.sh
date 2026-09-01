#!/bin/bash
# Script pour mettre à jour les données du dashboard

set -e

cd "$(dirname "$0")"

# HOTFIX 2026-07-17: single-instance lock. The systemd timer
# (ntv-monitoring.timer, every 5 min) is the primary scheduler; a legacy
# 6-hourly crontab entry may coexist (crontab gets rewritten by agents —
# root cause of INC-2). The lock makes any concurrent/duplicate invocation
# a harmless no-op instead of a double-run.
exec 9>/tmp/ntv_update_data.lock
if ! flock -n 9; then
    echo "update-data.sh: another instance is running — skipping (lock held)"
    exit 0
fi

# Copier les données du bot
cp ~/binance_bot_v5/bot_status_v5.json ./data/bot_status.json 2>/dev/null || echo "Fichier bot_status_v5.json non trouvé"
cp ~/binance_bot_v5/trades_v5.csv ./data/trades.csv 2>/dev/null || echo "Fichier trades_v5.csv non trouvé"

# Calculer le PnL du jour et mettre à jour bot_status.json
if [ -f ./data/trades.csv ] && [ -f ./data/bot_status.json ]; then
    python3 -c "
import csv
import json
import sys
from datetime import datetime, timezone
import os

# Lire les trades
with open('./data/trades.csv', 'r') as f:
    reader = csv.DictReader(f)
    trades = list(reader)

# Calculer le PnL du jour (trades d'aujourd'hui)
today = datetime.now(timezone.utc).date()
daily_pnl = 0.0
today_trades_count = 0

for trade in trades:
    try:
        # Extraire la date du timestamp
        timestamp = trade['timestamp']
        trade_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).date()
        
        # Si le trade est d'aujourd'hui, ajouter son PnL
        if trade_date == today:
            pnl = float(trade['pnl_usdc']) if trade['pnl_usdc'] else 0.0
            daily_pnl += pnl
            today_trades_count += 1
    except (ValueError, KeyError):
        continue

# Lire et mettre à jour bot_status.json
with open('./data/bot_status.json', 'r') as f:
    bot_status = json.load(f)

# Mettre à jour le PnL du jour
bot_status['daily_pnl'] = round(daily_pnl, 4)
bot_status['daily_pnl_calculated'] = True
bot_status['daily_pnl_date'] = today.isoformat()
bot_status['today_trades_count'] = today_trades_count

# Sauvegarder
with open('./data/bot_status.json', 'w') as f:
    json.dump(bot_status, f, indent=2)

print(f'PnL du jour calculé: {daily_pnl:.4f} USDC ({today_trades_count} trades)')
" 2>/dev/null || echo "Calcul du PnL du jour échoué"
fi

# Convertir CSV en JSON pour faciliter l'utilisation
if [ -f ./data/trades.csv ]; then
    python3 -c "
import csv
import json
import sys

with open('./data/trades.csv', 'r') as f:
    reader = csv.DictReader(f)
    trades = list(reader)

# Garder seulement les 50 derniers trades
trades = trades[-50:]

with open('./data/trades.json', 'w') as f:
    json.dump(trades, f, indent=2)
" 2>/dev/null || echo "Conversion CSV->JSON échouée"
fi

# Analyser les données boursières
if [ -f /home/openclaw/.openclaw/workspace-bourse/scalable_export.csv ]; then
    python3 ./update-stocks-data-simple.py 2>/dev/null || echo "Analyse boursière échouée"
fi

# Intégrer les stops actifs (positions non-Scalable)
python3 ./update-stops-dashboard.py 2>/dev/null || echo "Stops dashboard échoué"

# Analyser les données Kraken
if [ -f /home/openclaw/kraken_bot_v1/bot.log ]; then
    python3 ./update-kraken-data.py 2>/dev/null || echo "Analyse Kraken échouée"
fi

# Tick NTV en DRY_RUN — lance un vrai cycle de signal frais avant export
NTV_TICK_OK=false
if ( cd /home/openclaw/kraken_auto_spot_ntv && python3 src/main.py ) 2>&1; then
    NTV_TICK_OK=true
else
    echo "NTV TICK FAILED — export will carry stale data and freshness warning" >&2
fi
# Enregistrer le statut du tick pour les consommateurs downstream
echo "{\"ntv_tick_ok\": $NTV_TICK_OK, \"ntv_tick_ts\": \"$(date -Iseconds)\"}" > /home/openclaw/kraken_auto_spot_ntv/output/.tick_status.json

# Exporter les données Kraken Auto Spot NTV
python3 ./update-ntv-data.py 2>/dev/null || echo "Export NTV échoué"

# Forward-test snapshot (after NTV data generation)
python3 /home/openclaw/kraken_auto_spot_ntv/src/forward_test_snapshot.py 2>/dev/null || echo "Forward-test snapshot échoué"

# Exporter le statut reel des legacy bots
python3 ./export_legacy_bots_status.py 2>/dev/null || echo "Export legacy bots status échoué"

# Swing + Recovery paper engines are LOST (source under /tmp/opencode was removed).
# Their status is now PAUSED_ENGINE_LOST (historical data preserved under
# /home/openclaw/trading_stack/recovered_paper_history/). Do NOT attempt to execute
# any /tmp/opencode engine.py. export_dashboard_full.py emits the frozen
# historical summary directly.

# Generer les donnees financieres corrigees (finance.json + finance_detail.json)
python3 ./update-finance-json.py 2>/dev/null || echo "Finance JSON generation echouee"

# Extraire et catégoriser les transactions des releves PDF
python3 ./update-finance-detail.py 2>/dev/null || echo "Finance detail extraction échouée"

# Mettre à jour les prix ETF (Yahoo Finance côté serveur)
python3 ./update-stocks-prices.py 2>/dev/null || echo "Mise à jour prix ETF échouée"

# Exporter dashboard_full.json (agregation Swing Paper + Market Context + Freshness globale)
python3 ./export_dashboard_full.py 2>/dev/null || echo "Export dashboard_full échoué"

# Mettre à jour le timestamp
echo '{"last_updated": "'$(date -Iseconds)'"}' > ./data/last_updated.json

echo "Données mises à jour : $(date)"
