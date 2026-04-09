#!/usr/bin/env python3
"""
Script pour analyser les données boursières et générer un fichier JSON
"""

import csv
import json
import os
from datetime import datetime
import requests

# Chemins des fichiers
SCALABLE_CSV = "/home/openclaw/.openclaw/workspace-bourse/scalable_export.csv"
OUTPUT_JSON = "/home/openclaw/monitoring-site/data/stocks.json"

# Mapping ISIN -> Ticker et noms
ISIN_TO_DATA = {
    "IE00BF4RFH31": {"ticker": "WSML.L", "name": "iShares MSCI World Small Cap"},
    "IE00BKM4GZ66": {"ticker": "EIMI.L", "name": "iShares Core MSCI Emerging Markets IMI"},
    "IE00B5BMR087": {"ticker": "CSPX.L", "name": "iShares Core S&P 500"},
    "IE00BK5BQT80": {"ticker": "VWRA.L", "name": "Vanguard FTSE All-World"},
    "IE000BI8OT95": {"ticker": "LCUW.DE", "name": "Amundi MSCI World ESG"},
    "IE000I8KRLL9": {"ticker": "XDWH.DE", "name": "iShares MSCI Global Semiconductors"},
    "IE00BMW42413": {"ticker": "IQQH.DE", "name": "iShares MSCI Europe IT Sector"},
    "IE00BMW42306": {"ticker": "IEMM.L", "name": "iShares MSCI Europe Financials"},
}

def get_current_price_yahoo(ticker):
    """Récupère le prix actuel depuis Yahoo Finance"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if data.get('chart') and data['chart'].get('result'):
            result = data['chart']['result'][0]
            price = result['indicators']['quote'][0]['close'][-1]
            return float(price) if price else None
    except Exception as e:
        print(f"  Erreur Yahoo pour {ticker}: {e}")
    return None

def analyze_portfolio():
    """Analyse le portefeuille depuis le CSV Scalable Capital"""
    portfolio = {}
    
    print("Analyse des transactions Scalable Capital...")
    
    try:
        with open(SCALABLE_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)
            
            # Traiter les transactions dans l'ordre chronologique
            for row in rows:
                # Filtrer seulement les transactions exécutées
                if row['status'] != 'Executed':
                    continue
                
                isin = row['isin']
                if not isin or isin not in ISIN_TO_DATA:
                    continue
                
                ticker = ISIN_TO_DATA[isin]['ticker']
                transaction_type = row['type']
                
                # Gérer les différents types de transactions
                if transaction_type in ['Buy', 'Sell']:
                    shares = float(row['shares'].replace(',', '.')) if row['shares'] else 0
                    price = float(row['price'].replace(',', '.')) if row['price'] else 0
                    
                    if shares <= 0:
                        continue
                    
                    # Initialiser la position si elle n'existe pas
                    if ticker not in portfolio:
                        portfolio[ticker] = {
                            'name': ISIN_TO_DATA[isin]['name'],
                            'isin': isin,
                            'shares': 0,
                            'total_invested': 0,
                            'transactions': []
                        }
                    
                    # Ajouter la transaction
                    transaction = {
                        'date': row['date'],
                        'type': transaction_type,
                        'shares': shares,
                        'price': price,
                        'amount': float(row['amount'].replace(',', '.')) if row['amount'] else 0
                    }
                    portfolio[ticker]['transactions'].append(transaction)
                    
                    # Mettre à jour la position
                    if transaction_type == 'Buy':
                        portfolio[ticker]['shares'] += shares
                        portfolio[ticker]['total_invested'] += abs(transaction['amount'])
                    elif transaction_type == 'Sell':
                        portfolio[ticker]['shares'] -= shares
                        # Pour les ventes, on réduit proportionnellement l'investissement
                        if portfolio[ticker]['shares'] > 0:
                            portfolio[ticker]['total_invested'] = portfolio[ticker]['total_invested'] * (portfolio[ticker]['shares'] / (portfolio[ticker]['shares'] + shares))
                        else:
                            portfolio[ticker]['total_invested'] = 0
        
        # Nettoyer les positions avec 0 parts
        portfolio = {k: v for k, v in portfolio.items() if v['shares'] > 0}
        
        # Calculer le prix moyen et récupérer les prix actuels
        print("Récupération des prix actuels...")
        for ticker, data in portfolio.items():
            if data['shares'] > 0:
                data['average_price'] = data['total_invested'] / data['shares']
                
                # Récupérer le prix actuel
                current_price = get_current_price_yahoo(ticker)
                if current_price:
                    data['current_price'] = current_price
                    data['current_value'] = data['shares'] * current_price
                    data['total_pnl'] = data['current_value'] - data['total_invested']
                    data['total_pnl_pct'] = (data['total_pnl'] / data['total_invested'] * 100) if data['total_invested'] > 0 else 0
                else:
                    # Valeurs par défaut si pas de prix
                    data['current_price'] = data['average_price']
                    data['current_value'] = data['shares'] * data['average_price']
                    data['total_pnl'] = 0
                    data['total_pnl_pct'] = 0
                
                # Simplifier les données pour le frontend
                data['shares'] = round(data['shares'], 4)
                data['average_price'] = round(data['average_price'], 2)
                data['current_price'] = round(data['current_price'], 2)
                data['current_value'] = round(data['current_value'], 2)
                data['total_pnl'] = round(data['total_pnl'], 2)
                data['total_pnl_pct'] = round(data['total_pnl_pct'], 2)
                
                # Supprimer les transactions détaillées pour alléger le JSON
                if 'transactions' in data:
                    del data['transactions']
        
        return portfolio
        
    except Exception as e:
        print(f"Erreur lors de l'analyse: {e}")
        return {}

def main():
    print("=== Analyse du portefeuille boursier ===")
    
    try:
        portfolio = analyze_portfolio()
        
        # Calculer les totaux
        total_invested = sum(p['total_invested'] for p in portfolio.values())
        total_value = sum(p['current_value'] for p in portfolio.values())
        total_pnl = total_value - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        # Préparer les données finales
        result = {
            'portfolio': portfolio,
            'summary': {
                'positions_count': len(portfolio),
                'total_invested': round(total_invested, 2),
                'total_value': round(total_value, 2),
                'total_pnl': round(total_pnl, 2),
                'total_pnl_pct': round(total_pnl_pct, 2),
                'last_updated': datetime.now().isoformat()
            }
        }
        
        # Sauvegarder
        os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
        
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\\n✅ Données sauvegardées dans {OUTPUT_JSON}")
        print(f"\\n📊 RÉSUMÉ DU PORTEFEUILLE:")
        print(f"   Nombre de positions: {len(portfolio)}")
        print(f"   Total investi: {total_invested:.2f} €")
        print(f"   Valeur actuelle: {total_value:.2f} €")
        print(f"   PnL total: {total_pnl:+.2f} € ({total_pnl_pct:+.2f}%)")
        
        if portfolio:
            print(f"\\n📋 DÉTAIL DES POSITIONS:")
            for ticker, data in portfolio.items():
                pnl_color = "🟢" if data['total_pnl'] >= 0 else "🔴"
                print(f"   {ticker}: {data['shares']} parts")
                print(f"     Prix moyen: {data['average_price']:.2f} €")
                print(f"     Prix actuel: {data['current_price']:.2f} €")
                print(f"     Valeur: {data['current_value']:.2f} €")
                print(f"     PnL: {pnl_color} {data['total_pnl']:+.2f} € ({data['total_pnl_pct']:+.2f}%)")
        
    except Exception as e:
        print(f"\\n❌ ERREUR: {e}")
        # Créer un fichier d'erreur
        error_data = {
            'error': str(e),
            'last_updated': datetime.now().isoformat(),
            'portfolio': {},
            'summary': {
                'positions_count': 0,
                'total_invested': 0,
                'total_value': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0
            }
        }
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()