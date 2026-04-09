#!/usr/bin/env python3
"""
Script simplifié pour analyser les données boursières
"""

import csv
import json
import os
from datetime import datetime

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

def analyze_portfolio_simple():
    """Analyse simplifiée du portefeuille"""
    portfolio = {}
    
    # Lire le fichier CSV
    try:
        with open(SCALABLE_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            
            for row in reader:
                # Filtrer seulement les transactions exécutées d'achat
                if row['status'] != 'Executed' or row['type'] != 'Buy':
                    continue
                
                isin = row['isin']
                if not isin or isin not in ISIN_TO_DATA:
                    continue
                
                ticker = ISIN_TO_DATA[isin]['ticker']
                shares = float(row['shares'].replace(',', '.')) if row['shares'] else 0
                price = float(row['price'].replace(',', '.')) if row['price'] else 0
                
                if shares <= 0:
                    continue
                
                # Initialiser ou mettre à jour la position
                if ticker not in portfolio:
                    portfolio[ticker] = {
                        'name': ISIN_TO_DATA[isin]['name'],
                        'isin': isin,
                        'shares': 0,
                        'average_price': 0,
                        'total_invested': 0
                    }
                
                # Mettre à jour la position
                portfolio[ticker]['shares'] += shares
                invested = shares * price
                portfolio[ticker]['total_invested'] += invested
                portfolio[ticker]['average_price'] = portfolio[ticker]['total_invested'] / portfolio[ticker]['shares']
    
    except Exception as e:
        print(f"Erreur lecture CSV: {e}")
        return {}
    
    # Pour le moment, on retourne les positions sans prix actuels
    # (les prix seront récupérés par JavaScript côté client)
    return portfolio

def main():
    print("Analyse simplifiée du portefeuille boursier...")
    
    try:
        portfolio = analyze_portfolio_simple()
        
        # Préparer les données pour le dashboard
        result = {
            'portfolio': portfolio,
            'summary': {
                'positions_count': len(portfolio),
                'total_shares': sum(p['shares'] for p in portfolio.values()),
                'total_invested': sum(p['total_invested'] for p in portfolio.values()),
                'last_updated': datetime.now().isoformat()
            },
            'note': 'Les prix actuels et signaux seront récupérés côté client via Yahoo Finance API'
        }
        
        # Sauvegarder
        os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
        
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Données sauvegardées dans {OUTPUT_JSON}")
        print(f"📊 Résumé :")
        print(f"   Positions : {len(portfolio)}")
        print(f"   Total investi : {result['summary']['total_invested']:.2f} EUR")
        
        # Afficher les positions
        for ticker, data in portfolio.items():
            print(f"   {ticker}: {data['shares']} parts @ {data['average_price']:.2f} EUR")
        
    except Exception as e:
        print(f"❌ Erreur : {e}")
        # Créer un fichier d'erreur
        error_data = {
            'error': str(e),
            'last_updated': datetime.now().isoformat(),
            'portfolio': {},
            'summary': {'positions_count': 0, 'total_invested': 0}
        }
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()