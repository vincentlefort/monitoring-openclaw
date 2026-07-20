#!/usr/bin/env python3
"""
update-stops-dashboard.py — Intègre les stops actifs (positions non-Scalable)
dans data/stocks.json. Lit stops_actifs.json depuis workspace-bourse,
récupère les prix Yahoo Finance, et enrichit stocks.json.
"""
import json, os, requests
from datetime import datetime
from pathlib import Path

STOPS_PATH = Path("/home/openclaw/.openclaw/workspace-bourse/stops_actifs.json")
STOCKS_PATH = Path("/home/openclaw/monitoring-site/data/stocks.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

# Mapping ticker → nom lisible (stock picking actions)
TICKER_NAMES = {
    "MRK.DE":  "Merck KGaA",
    "AIR.PA":  "Airbus SE",
    "BNP.PA":  "BNP Paribas",
    "NESN.SW": "Nestlé SA",
    "ALV.DE":  "Allianz SE",
    "MTX.DE":  "MTU Aero Engines",
}


def fetch_price(ticker: str) -> dict:
    """Fetch prix actuel + prev_close via Yahoo Finance, retourné en EUR."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json().get("chart", {}).get("result")
        if not data or not data[0]:
            return None
        meta = data[0]["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose")
        currency = meta.get("currency", "EUR")
        if not price:
            return None

        # Conversion EUR si nécessaire
        fx = 1.0
        if currency == "USD":
            fx = _get_fx("EURUSD=X")
        elif currency == "CHF":
            fx = _get_fx("CHFEUR=X")
        elif currency == "GBP" or currency == "GBp":
            fx = _get_fx("GBPEUR=X")
            if currency == "GBp":
                fx /= 100.0

        price_eur = round(price * fx, 4)
        change_pct = round((price - prev) / prev * 100, 2) if prev else 0
        return {
            "price": round(price, 4),
            "price_eur": price_eur,
            "prev_close": round(prev, 4) if prev else None,
            "change_pct": change_pct,
            "currency": currency,
        }
    except Exception as e:
        print(f"  ⚠️  {ticker}: {e}")
        return None


_FX_CACHE = {}


def _get_fx(pair: str) -> float:
    if pair in _FX_CACHE:
        return _FX_CACHE[pair]
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{pair}?interval=1d&range=1d"
        r = requests.get(url, headers=HEADERS, timeout=5)
        res = r.json().get("chart", {}).get("result")
        if res:
            rate = res[0]["meta"].get("regularMarketPrice")
            if rate:
                # EURUSD=X → 1 EUR = rate USD → 1 USD = 1/rate EUR
                # CHFEUR=X → rate EUR per CHF → 1 CHF = rate EUR
                # GBPEUR=X → rate EUR per GBP → 1 GBP = rate EUR
                if pair == "EURUSD=X":
                    rate = 1 / rate
                _FX_CACHE[pair] = rate
                return rate
    except Exception:
        pass
    _FX_CACHE[pair] = 1.0
    return 1.0


def main():
    if not STOPS_PATH.exists():
        print(f"❌ {STOPS_PATH} introuvable")
        return

    with open(STOPS_PATH) as f:
        stops_data = json.load(f)

    # Charger stocks.json existant (préserver le reste)
    if STOCKS_PATH.exists():
        with open(STOCKS_PATH) as f:
            stocks = json.load(f)
    else:
        stocks = {"portfolio": {}, "prices": {}, "transactions": [], "summary": {}}

    stops_positions = stops_data.get("positions", [])
    stop_positions_out = {}
    stop_prices_out = {}
    stop_transactions = []

    total_invested = 0.0
    total_value = 0.0
    total_risk = 0.0

    print(f"[{datetime.now().strftime('%H:%M')}] Intégration stops → dashboard")
    print(f"  {len(stops_positions)} positions stops actives")

    for pos in stops_positions:
        ticker = pos["ticker"]
        nb = pos["nb_actions"]
        entry = pos["prix_entree"]
        stop = pos["stop_dormant"]
        date_entree = pos.get("date_entree", "")
        invested = round(nb * entry, 2)
        risk = round(nb * (entry - stop), 2)
        name = TICKER_NAMES.get(ticker, ticker)

        # Prix actuel
        pd = fetch_price(ticker)
        if pd:
            cur_price = pd["price_eur"]
            valeur = round(nb * cur_price, 2)
            pnl_pct = round((cur_price - entry) / entry * 100, 2)
            pnl_eur = round(valeur - invested, 2)
            distance_stop_pct = round((cur_price - stop) / cur_price * 100, 2)
            fresh = True
        else:
            cur_price = None
            valeur = invested  # fallback
            pnl_pct = 0
            pnl_eur = 0
            distance_stop_pct = round((entry - stop) / entry * 100, 2)
            fresh = False

        stop_positions_out[ticker] = {
            "name": name,
            "ticker": ticker,
            "shares": nb,
            "prix_entree": entry,
            "stop": stop,
            "invested": invested,
            "date_entree": date_entree,
        }

        stop_prices_out[ticker] = {
            "price": pd["price"] if pd else None,
            "price_eur": pd["price_eur"] if pd else None,
            "change_pct": pd["change_pct"] if pd else None,
            "currency": pd["currency"] if pd else None,
            "value": valeur,
            "pnl_pct": pnl_pct,
            "pnl_eur": pnl_eur,
            "distance_stop_pct": distance_stop_pct,
            "fresh": fresh,
        }

        # Transaction (seulement pour les achats du jour)
        if date_entree == "2026-07-20":
            stop_transactions.append({
                "date": date_entree,
                "time": "",
                "type": "Buy",
                "description": name,
                "ticker": ticker,
                "isin": f"STOP:{ticker}",
                "shares": nb,
                "price": entry,
                "amount": -invested,
                "fee": 0.0,
            })

        total_invested += invested
        total_value += valeur
        total_risk += risk

        status = "✅" if fresh else "⚪"
        pnl_str = f"{pnl_pct:+.2f}%" if pnl_pct else "—"
        print(f"  {status} {ticker:<10} {nb:>3}×{entry}€ → {cur_price or '—':>8}€  PnL={pnl_str}  stop={stop} ({distance_stop_pct:+.1f}% au-dessus)")

    # Merge dans stocks.json
    stocks["stops_positions"] = stop_positions_out
    stocks["stops_prices"] = stop_prices_out

    # Ne pas écraser les transactions Scalable — ajouter celles du jour en tête
    existing_tx = stocks.get("transactions", [])
    # Filtrer les doublons (même ticker + même date)
    existing_keys = {(tx.get("ticker", ""), tx.get("date", "")) for tx in existing_tx}
    new_tx = [t for t in stop_transactions if (t["ticker"], t["date"]) not in existing_keys]
    # Insérer en tête (les plus récentes d'abord)
    stocks["transactions"] = new_tx + existing_tx

    # Mettre à jour le summary stops
    stocks["stops_summary"] = {
        "positions_count": len(stops_positions),
        "total_invested": round(total_invested, 2),
        "total_value": round(total_value, 2),
        "total_risk_eur": round(total_risk, 2),
        "total_pnl_eur": round(total_value - total_invested, 2),
        "total_pnl_pct": round((total_value - total_invested) / total_invested * 100, 2) if total_invested else 0,
        "last_updated": datetime.now().isoformat(),
    }

    # Écrire
    os.makedirs(STOCKS_PATH.parent, exist_ok=True)
    with open(STOCKS_PATH, "w") as f:
        json.dump(stocks, f, indent=2, ensure_ascii=False)

    print(f"\n💼 STOPS DASHBOARD :")
    print(f"  Positions  : {len(stops_positions)}")
    print(f"  Investi    : {total_invested:,.2f}€")
    print(f"  Valeur     : {total_value:,.2f}€")
    print(f"  Risque     : {total_risk:,.2f}€")
    print(f"  PnL latent : {total_value - total_invested:+,.2f}€")
    print(f"  ✅ {STOCKS_PATH}")


if __name__ == "__main__":
    main()
