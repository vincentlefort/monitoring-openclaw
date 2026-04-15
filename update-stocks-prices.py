#!/usr/bin/env python3
"""
update-stocks-prices.py — Récupère les prix ETF via Yahoo Finance côté serveur.
Écrit les prix dans data/stocks.json pour éviter les blocages CORS côté browser.
Cron : toutes les 30 min (intégré au cron monitoring existant)
"""
import json, requests
from datetime import datetime
from pathlib import Path

STOCKS_FILE = Path('/home/openclaw/monitoring-site/data/stocks.json')
HEADERS     = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}

# Tickers alternatifs pour les symboles introuvables sur Yahoo
TICKER_ALT = {
    'IEMM.L': 'IEMM.AS',  # iShares MSCI EM — .L introuvable sur Yahoo, .AS disponible
}


def fetch_price(ticker: str) -> dict:
    """Retourne {price, prev_close, change_pct} ou None."""
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d'
        r   = requests.get(url, headers=HEADERS, timeout=8)
        result = r.json().get('chart', {}).get('result')
        if not result:
            return None
        meta  = result[0]['meta']
        price = meta.get('regularMarketPrice')
        prev  = meta.get('chartPreviousClose')
        if not price:
            return None
        chg = (price - prev) / prev * 100 if prev else 0
        return {'price': round(price, 4), 'prev_close': round(prev, 4) if prev else None, 'change_pct': round(chg, 2)}
    except Exception as e:
        print(f'  ⚠️  {ticker}: {e}')
        return None


def compute_signal(pnl_pct: float, change_pct: float) -> str:
    """Signal basé sur variation jour + PnL position."""
    if change_pct is not None and change_pct < -3:
        return 'BUY'
    if change_pct is not None and change_pct < -1.5:
        return 'BUY'
    if pnl_pct is not None and pnl_pct < -4:
        return 'BUY'
    if change_pct is not None and change_pct > 3:
        return 'SELL'
    if pnl_pct is not None and pnl_pct > 15:
        return 'SELL'
    return 'HOLD'


def main():
    with open(STOCKS_FILE) as f:
        data = json.load(f)

    portfolio = data.get('portfolio', {})
    prices    = data.get('prices', {})   # section prix persistée
    total_val = 0.0
    total_inv = 0.0

    print(f"[{datetime.now().strftime('%H:%M')}] Mise à jour prix ETF...")

    for ticker, pos in portfolio.items():
        yahoo_ticker = TICKER_ALT.get(ticker, ticker)
        pd = fetch_price(yahoo_ticker)
        if pd:
            prices[ticker] = pd
            print(f"  ✅ {ticker:<12} {pd['price']:.2f}  {pd['change_pct']:+.2f}%")
        else:
            # Conserver dernier prix connu
            print(f"  ⚪ {ticker:<12} prix indisponible — dernier connu: {prices.get(ticker, {}).get('price', '—')}")

        # Calculs PnL
        cur_price = prices.get(ticker, {}).get('price')
        if cur_price:
            val      = cur_price * pos['shares']
            invested = pos['total_invested']
            total_val += val
            total_inv += invested
            pnl_pct   = (val - invested) / invested * 100
            change    = prices.get(ticker, {}).get('change_pct')
            signal    = compute_signal(pnl_pct, change)
            prices[ticker]['pnl_pct']       = round(pnl_pct, 2)
            prices[ticker]['value']         = round(val, 2)
            prices[ticker]['pnl_eur']       = round(val - invested, 2)
            prices[ticker]['signal']        = signal
        else:
            total_inv += pos['total_invested']

    data['prices']  = prices
    data['summary']['total_value']   = round(total_val, 2)
    data['summary']['total_invested'] = round(total_inv, 2)
    data['summary']['total_pnl_eur'] = round(total_val - total_inv, 2)
    data['summary']['total_pnl_pct'] = round((total_val - total_inv) / total_inv * 100, 2) if total_inv else 0
    data['summary']['last_updated']  = datetime.now().isoformat()

    with open(STOCKS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"  Total valeur : €{total_val:.0f} | Investi : €{total_inv:.0f} | PnL : €{total_val-total_inv:+.0f} ({data['summary']['total_pnl_pct']:+.1f}%)")
    print(f"  ✅ stocks.json mis à jour")


if __name__ == '__main__':
    main()
