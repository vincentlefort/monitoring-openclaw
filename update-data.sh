#!/bin/bash
# Script pour mettre à jour les données du dashboard

set -e

cd "$(dirname "$0")"

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

# Analyser les données Kraken
if [ -f /home/openclaw/kraken_bot_v1/bot.log ]; then
    python3 ./update-kraken-data.py 2>/dev/null || echo "Analyse Kraken échouée"
fi

# Mettre à jour les prix ETF (Yahoo Finance côté serveur)
python3 ./update-stocks-prices.py 2>/dev/null || echo "Mise à jour prix ETF échouée"

# Mettre à jour le timestamp
echo '{"last_updated": "'$(date -Iseconds)'"}' > ./data/last_updated.json

echo "Données mises à jour : $(date)"