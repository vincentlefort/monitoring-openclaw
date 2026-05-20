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

# Mapping ISIN -> Ticker Yahoo Finance et nom
ISIN_TO_DATA = {
    "IE00BF4RFH31": {"ticker": "WSML.L",  "name": "iShares MSCI World Small Cap"},
    "IE00BKM4GZ66": {"ticker": "EIMI.L",  "name": "iShares Core MSCI Emerging Markets IMI"},
    "IE00B5BMR087": {"ticker": "CSPX.L",  "name": "iShares Core S&P 500"},
    "IE00BK5BQT80": {"ticker": "VWRA.L",  "name": "Vanguard FTSE All-World"},
    "IE000BI8OT95": {"ticker": "WRDU.AS", "name": "Amundi Core MSCI World"},
    "IE000I8KRLL9": {"ticker": "SEMI.L",  "name": "iShares MSCI Global Semiconductors"},
    "IE00BM67HK77": {"ticker": "XDWH.DE", "name": "Xtrackers MSCI World Health Care"},
    "IE00BMW42413": {"ticker": "IQQH.DE", "name": "iShares MSCI Europe IT Sector"},
    "IE00BMW42306": {"ticker": "ESIF.L",  "name": "iShares MSCI Europe Financials"},
    # Actions US (Scalable Capital)
    "US0404132054": {"ticker": "ANET",    "name": "Arista Networks"},
    "US74762E1029": {"ticker": "PWR",     "name": "Quanta Services"},
    "US7475251036": {"ticker": "QCOM",    "name": "Qualcomm"},
    "US1717793095": {"ticker": "CIEN",    "name": "Ciena Co"},
}

def analyze_portfolio_simple():
    """Analyse simplifiée du portefeuille"""
    portfolio = {}
    
    # Lire le fichier CSV
    try:
        with open(SCALABLE_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            # CSV Scalable = ordre anti-chronologique → inverser pour traiter Buy avant Sell
            rows = list(reader)
            rows.reverse()

            for row in rows:
                # Transactions exécutées Buy ou Sell uniquement
                if row['status'] != 'Executed' or row['type'] not in ('Buy', 'Sell'):
                    continue

                isin = row['isin']
                if not isin:
                    continue

                # Resoudre ticker et nom : mapping prioritaire, sinon utiliser description CSV
                mapping = ISIN_TO_DATA.get(isin, {})
                ticker = mapping.get('ticker', isin[:20])
                name = mapping.get('name', row.get('description', isin))
                asset_type = 'ETF' if isin.startswith('IE') else 'action'

                shares = float(row['shares'].replace('.', '').replace(',', '.')) if row['shares'] else 0
                price  = float(row['price'].replace('.', '').replace(',', '.'))  if row['price']  else 0

                if shares <= 0:
                    continue

                # Initialiser la position si absente
                if ticker not in portfolio:
                    portfolio[ticker] = {
                        'name': name,
                        'isin': isin,
                        'type': asset_type,
                        'shares': 0,
                        'average_price': 0,
                        'total_invested': 0
                    }

                pos = portfolio[ticker]
                if row['type'] == 'Buy':
                    pos['shares'] += shares
                    pos['total_invested'] += shares * price
                else:  # Sell
                    # Réduction proportionnelle du coût moyen
                    if pos['shares'] > 0:
                        cost_per_share = pos['total_invested'] / pos['shares']
                        pos['total_invested'] -= shares * cost_per_share
                    pos['shares'] -= shares

                if pos['shares'] > 0:
                    pos['average_price'] = pos['total_invested'] / pos['shares']
                else:
                    pos['average_price'] = 0
    
    except Exception as e:
        print(f"Erreur lecture CSV: {e}")
        return {}

    # Retirer les positions soldées (shares <= 0)
    portfolio = {k: v for k, v in portfolio.items() if v['shares'] > 0.001}

    # Pour le moment, on retourne les positions sans prix actuels
    # (les prix seront récupérés par JavaScript côté client)
    return portfolio

def get_transactions():
    """Extrait l'historique des transactions (Buy/Sell) depuis le CSV Scalable."""
    transactions = []
    try:
        with open(SCALABLE_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                if row.get('status') != 'Executed':
                    continue
                ttype = row.get('type', '')
                if ttype not in ('Buy', 'Sell'):
                    continue
                desc = row.get('description', '')
                isin = row.get('isin', '')
                ticker = ISIN_TO_DATA.get(isin, {}).get('ticker', '')
                shares = row.get('shares', '0').replace('.', '').replace(',', '.')
                price = row.get('price', '0').replace('.', '').replace(',', '.')
                amount = row.get('amount', '0').replace('.', '').replace(',', '.')
                fee = row.get('fee', '0').replace('.', '').replace(',', '.')
                transactions.append({
                    'date': row['date'],
                    'time': row.get('time', ''),
                    'type': ttype,
                    'description': desc,
                    'isin': isin,
                    'ticker': ticker,
                    'shares': float(shares),
                    'price': float(price),
                    'amount': float(amount),
                    'fee': float(fee),
                })
    except Exception as e:
        print(f"⚠️ Transactions: {e}")
    return transactions

def main():
    print("Analyse simplifiée du portefeuille boursier...")
    
    try:
        portfolio = analyze_portfolio_simple()
        
        # Extraire l'historique des transactions
        transactions = get_transactions()

        # Préserver les prix existants pour éviter perte si Yahoo rate-limite
        prev_prices = {}
        prev_transactions = []
        try:
            if os.path.exists(OUTPUT_JSON):
                with open(OUTPUT_JSON, 'r') as f:
                    prev = json.load(f)
                    prev_prices = prev.get('prices', {})
                    prev_transactions = prev.get('transactions', [])
        except Exception:
            pass

        # Garder les transactions precedentes si la nouvelle extraction echoue
        if not transactions and prev_transactions:
            transactions = prev_transactions

        # Préparer les données pour le dashboard
        result = {
            'portfolio': portfolio,
            'prices': prev_prices,
            'transactions': transactions,
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