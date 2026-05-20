#!/usr/bin/env python3
"""
update-stocks-prices.py — Récupère les prix ETF via Yahoo Finance côté serveur.
Écrit les prix dans data/stocks.json pour éviter les blocages CORS côté browser.
Cron : toutes les 30 min (intégré au cron monitoring existant)
"""
import json, requests
from datetime import datetime
from pathlib import Path

STOCKS_FILE  = Path('/home/openclaw/monitoring-site/data/stocks.json')
MARKET_STATE = Path('/home/openclaw/shared/market_state.json')
HEADERS      = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}

# Tickers alternatifs — ticker Yahoo Finance ≠ ticker d'affichage
TICKER_ALT = {
    # IEMM.L retiré : IEMM.AS pointait vers un ETF EM à 53€ (mauvais ETF)
    # ESIF.L est maintenant le ticker direct pour IE00BMW42306
}

# Devises Yahoo qui nécessitent une conversion vers EUR
# Les ETFs listés sur LSE (xxx.L) retournent souvent USD ou GBP sur Yahoo Finance
CURRENCY_TO_EUR = {}   # rempli dynamiquement depuis les taux live


def fetch_price(ticker: str) -> dict:
    """Retourne {price, prev_close, change_pct, currency} ou None."""
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d'
        r   = requests.get(url, headers=HEADERS, timeout=8)
        result = r.json().get('chart', {}).get('result')
        if not result:
            return None
        meta     = result[0]['meta']
        price    = meta.get('regularMarketPrice')
        prev     = meta.get('chartPreviousClose')
        currency = meta.get('currency', 'EUR')
        if not price:
            return None
        chg = (price - prev) / prev * 100 if prev else 0
        return {
            'price':      round(price, 4),
            'prev_close': round(prev, 4) if prev else None,
            'change_pct': round(chg, 2),
            'currency':   currency,
        }
    except Exception as e:
        print(f'  ⚠️  {ticker}: {e}')
        return None


def fetch_fx_rates() -> dict:
    """Retourne {currency: eur_rate} depuis Yahoo Finance. Fallback sur derniers taux connus."""
    rates = {'EUR': 1.0}
    pairs = {'USD': 'EURUSD=X', 'GBP': 'GBPEUR=X'}
    for currency, pair in pairs.items():
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{pair}?interval=1d&range=1d'
            r   = requests.get(url, headers=HEADERS, timeout=5)
            res = r.json().get('chart', {}).get('result')
            if res:
                rate = res[0]['meta'].get('regularMarketPrice')
                if rate:
                    # EURUSD=X → rate = USD par EUR → 1 USD = 1/rate EUR
                    # GBPEUR=X → rate = EUR par GBP → 1 GBP = rate EUR
                    rates[currency] = (1 / rate) if currency == 'USD' else rate
        except Exception:
            pass
    # Fallbacks si fetch échoue
    rates.setdefault('USD', 0.848)
    rates.setdefault('GBP', 1.150)
    return rates


def get_macro() -> dict:
    """Lit market_state.json — retourne {'regime', 'fg', 'btc_4h'} ou défauts neutres."""
    try:
        with open(MARKET_STATE) as f:
            m = json.load(f)
        return {
            'regime': m.get('regime', 'neutral'),
            'fg':     m.get('fear_greed', 50),
            'btc_4h': m.get('btc_change_4h', 0.0),
        }
    except Exception:
        return {'regime': 'neutral', 'fg': 50, 'btc_4h': 0.0}


def compute_signal(pnl_pct: float, change_pct: float, macro: dict) -> str:
    """
    Signal aligné avec la logique agent bourse :
    - Baisse jour > 1.5% ET macro favorable (fg >= 40 ou régime non extreme_fear) → BUY
    - PnL position > 15% ET marché haussier (fg >= 55) → SELL
    - Sinon → HOLD
    """
    if change_pct is None or pnl_pct is None:
        return 'STALE'

    regime   = macro.get('regime', 'neutral')
    fg       = macro.get('fg', 50)
    macro_ok = fg >= 40 and regime != 'extreme_fear'
    bullish  = fg >= 55

    if change_pct < -1.5 and macro_ok:
        return 'BUY'
    if pnl_pct > 15 and bullish:
        return 'SELL'
    return 'HOLD'


def main():
    with open(STOCKS_FILE) as f:
        data = json.load(f)

    portfolio   = data.get('portfolio', {})
    prices      = data.get('prices', {})   # section prix persistée
    total_val   = 0.0
    total_inv   = 0.0
    stale_count = 0
    macro       = get_macro()
    fx          = fetch_fx_rates()

    print(f"[{datetime.now().strftime('%H:%M')}] Mise à jour prix ETF... (F&G={macro['fg']} régime={macro['regime']} USD={fx.get('USD',0):.4f} GBP={fx.get('GBP',0):.4f})")

    for ticker, pos in portfolio.items():
        yahoo_ticker = TICKER_ALT.get(ticker, ticker)
        pd = fetch_price(yahoo_ticker)
        if pd:
            prices[ticker] = pd
            currency = pd.get('currency', 'EUR')
            eur_rate = fx.get(currency, 1.0)
            price_eur = round(pd['price'] * eur_rate, 4)
            prices[ticker]['price_eur'] = price_eur
            prices[ticker]['currency']  = currency
            conv_note = f" [{currency}×{eur_rate:.4f}={price_eur:.2f}€]" if currency != 'EUR' else ""
            print(f"  ✅ {ticker:<12} {pd['price']:.3f} {currency} {pd['change_pct']:+.2f}%{conv_note}")
        else:
            stale_count += 1
            last = prices.get(ticker, {}).get('price_eur') or prices.get(ticker, {}).get('price', '—')
            print(f"  ⚪ {ticker:<12} prix indisponible — dernier connu: {last}")

        # Calculs PnL — utiliser price_eur (converti) si disponible
        cur_price  = prices.get(ticker, {}).get('price_eur') or prices.get(ticker, {}).get('price')
        is_fresh   = pd is not None
        if cur_price:
            val      = cur_price * pos['shares']
            invested = pos['total_invested']
            total_val += val
            total_inv += invested
            pnl_pct  = (val - invested) / invested * 100 if invested else 0
            pnl_eur  = val - invested
            realized = pos.get('pnl_realized', 0)
            change   = prices.get(ticker, {}).get('change_pct')
            if is_fresh:
                signal = compute_signal(pnl_pct, change, macro)
            else:
                signal = 'STALE'
            prices[ticker]['pnl_pct']       = round(pnl_pct, 2)
            prices[ticker]['value']         = round(val, 2)
            prices[ticker]['pnl_eur']       = round(pnl_eur, 2)
            prices[ticker]['signal']        = signal
            prices[ticker]['fresh']         = is_fresh
            # Nouvelles colonnes par position
            prices[ticker]['pnl_realized']  = round(realized, 2)
            prices[ticker]['pnl_total']     = round(realized + pnl_eur, 2)
            prices[ticker]['pnl_total_pct'] = round((realized + pnl_eur) / invested * 100, 2) if invested else 0
        else:
            total_inv += pos['total_invested']

    # Avertissement global si trop de données indisponibles
    if stale_count >= len(portfolio) // 2:
        data['prix_warning'] = f"Données partielles ({stale_count}/{len(portfolio)} indisponibles) — rate-limit probable"
        print(f"  ⚠️  {stale_count}/{len(portfolio)} tickers non rafraîchis — rate-limit probable")
    else:
        data.pop('prix_warning', None)

    # Ajouter le poids portefeuille par position
    if total_val > 0:
        for ticker in prices:
            val = prices[ticker].get('value', 0)
            prices[ticker]['weight_pct'] = round(val / total_val * 100, 1)

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
