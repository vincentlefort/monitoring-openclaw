#!/usr/bin/env python3
"""
Script pour analyser les données Kraken Futures
"""

import json
import os
import re
from datetime import datetime, timedelta
import csv

# Chemins des fichiers
BOT_LOG = "/home/openclaw/kraken_bot_v1/bot.log"
TRADES_CSV = "/home/openclaw/kraken_bot_v1/trades_kraken.csv"
OUTPUT_JSON = "/home/openclaw/monitoring-site/data/kraken.json"

def parse_bot_log():
    """Parse le fichier de log du bot Kraken"""
    data = {
        'balance': 0.0,
        'positions': [],
        'last_scan': None,
        'rsi_data': {},
        'status': 'offline'
    }
    
    try:
        with open(BOT_LOG, 'r') as f:
            lines = f.readlines()
            
        if not lines:
            return data
        
        # Chercher la dernière ligne de scan
        for line in reversed(lines):
            line = line.strip()
            
            # Vérifier si c'est une ligne de scan
            if line.startswith('[scan]'):
                data['status'] = 'online'
                data['last_scan'] = datetime.now().isoformat()
                
                # Extraire le balance
                balance_match = re.search(r'balance=([\d\.]+)', line)
                if balance_match:
                    data['balance'] = float(balance_match.group(1))
                
                # Extraire les positions
                positions_match = re.search(r'positions=\[([^\]]*)\]', line)
                if positions_match and positions_match.group(1).strip():
                    # Format: positions=['BTCUSDC:LONG:100.5']
                    pos_str = positions_match.group(1)
                    positions = []
                    for pos in pos_str.split(','):
                        pos = pos.strip().strip("'")
                        if pos:
                            parts = pos.split(':')
                            if len(parts) >= 2:
                                positions.append({
                                    'symbol': parts[0],
                                    'side': parts[1] if len(parts) > 1 else 'UNKNOWN',
                                    'size': float(parts[2]) if len(parts) > 2 else 0
                                })
                    data['positions'] = positions
                break
        
        # Extraire les dernières données RSI
        rsi_data = {}
        for line in reversed(lines[-50:]):  # Regarder les 50 dernières lignes
            line = line.strip()
            # Chercher les lignes RSI
            rsi_match = re.search(r'(\w+): RSI=([\d\.]+)', line)
            if rsi_match:
                symbol = rsi_match.group(1)
                rsi_value = float(rsi_match.group(2))
                if symbol not in rsi_data:
                    rsi_data[symbol] = {
                        'rsi': rsi_value,
                        'signal': 'none'
                    }
        
        data['rsi_data'] = rsi_data
        
    except Exception as e:
        print(f"Erreur parsing log: {e}")
        data['error'] = str(e)
    
    return data

def parse_trades_csv():
    """Parse le fichier CSV des trades Kraken"""
    trades = []
    daily_pnl = 0.0
    
    try:
        if os.path.exists(TRADES_CSV) and os.path.getsize(TRADES_CSV) > 0:
            with open(TRADES_CSV, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        trade = {
                            'timestamp': row.get('timestamp', ''),
                            'symbol': row.get('symbol', ''),
                            'side': row.get('side', ''),
                            'entry_price': float(row.get('entry_price', 0)),
                            'exit_price': float(row.get('exit_price', 0)),
                            'size': float(row.get('size', 0)),
                            'pnl_usd': float(row.get('pnl_usd', 0)),
                            'pnl_pct': float(row.get('pnl_pct', 0)),
                            'duration': row.get('duration', ''),
                            'exit_reason': row.get('exit_reason', '')
                        }
                        trades.append(trade)
                        
                        # Vérifier si le trade est d'aujourd'hui
                        if trade['timestamp']:
                            try:
                                trade_date = datetime.fromisoformat(trade['timestamp'].replace('Z', '+00:00'))
                                if trade_date.date() == datetime.now().date():
                                    daily_pnl += trade['pnl_usd']
                            except:
                                pass
                                
                    except (ValueError, KeyError) as e:
                        print(f"Erreur parsing trade: {e}")
                        continue
        
        # Trier par timestamp décroissant
        trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
    except Exception as e:
        print(f"Erreur parsing CSV: {e}")
    
    return trades, daily_pnl

def main():
    print("Analyse des données Kraken Futures...")
    
    try:
        # Parser les données
        bot_data = parse_bot_log()
        trades, daily_pnl = parse_trades_csv()
        
        # Préparer les données finales
        result = {
            'bot': bot_data,
            'trades': trades[:10],  # 10 derniers trades
            'summary': {
                'balance': bot_data['balance'],
                'positions_count': len(bot_data['positions']),
                'open_positions_value': sum(p.get('size', 0) for p in bot_data['positions']),
                'daily_pnl': round(daily_pnl, 4),
                'total_trades': len(trades),
                'last_updated': datetime.now().isoformat()
            }
        }
        
        # Sauvegarder
        os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
        
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Données Kraken sauvegardées dans {OUTPUT_JSON}")
        print(f"📊 Résumé Kraken :")
        print(f"   Balance: ${result['summary']['balance']:.2f}")
        print(f"   Positions ouvertes: {result['summary']['positions_count']}")
        print(f"   PnL du jour: ${result['summary']['daily_pnl']:.2f}")
        print(f"   Total trades: {result['summary']['total_trades']}")
        print(f"   Statut: {result['bot']['status']}")
        
        if result['bot']['rsi_data']:
            print(f"   RSI actuel:")
            for symbol, data in result['bot']['rsi_data'].items():
                print(f"     {symbol}: {data['rsi']:.1f}")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        # Créer un fichier d'erreur
        error_data = {
            'error': str(e),
            'last_updated': datetime.now().isoformat(),
            'bot': {'status': 'error', 'balance': 0, 'positions': []},
            'trades': [],
            'summary': {
                'balance': 0,
                'positions_count': 0,
                'open_positions_value': 0,
                'daily_pnl': 0,
                'total_trades': 0
            }
        }
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()