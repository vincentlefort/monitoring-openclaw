#!/usr/bin/env python3
"""
Extrait les transactions des releves PDF VKB/DKB, les categorise,
et genere data/finance_detail.json pour le dashboard monitoring-site.
"""
import pdfplumber
import re
import json
import os
from datetime import datetime
from collections import defaultdict

PDF_DIR = "/home/openclaw/finance/releves"
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "finance_detail.json")

# ── Catégorisation par mots-clés ──
CATEGORIES = {
    "loyer": ["SWM Versorgungs", "SWM Versorgung", "swm", "stadtwerke", "miete",
              "Jörg Kottsieper", "Kottsieper", "Joerg Kottsieper"],
    "juridique": ["Conlex", "Rechtsanwalt", "Anwalt", "Gericht", "Notar"],
    "impots": ["Finanzamt", "Steuer", "Steuerberater", "ELSTER", "elster"],
    "sante": ["Apotheke", "apotheke", "Arzt", "arzt", "Zahnarzt", "zahnarzt",
              "Krankenhaus", "krankenhaus", "Therapie", "therapie",
              "Physio", "physio", "Orthopade", "orthopade", "Orthopäde",
              "Sanitatshaus", "sanitatshaus", "Sanitätshaus", "Medikament",
              "TK ", "Techniker Krankenkasse", "AOK", "Barmer", "DAK",
              "Urologie", "urologie", "Radiologie", "Hautarzt", "Augenarzt"],
    "divers_connu": ["Allane SE", "DZ BANK", "dz bank",
                     "FK München", "KREISSPARKASSE", "Kreissparkasse",
                     "Postbank", "MEINE VBRB",
                     "MUENCHNER BANK", "VR-BANK LANDSBERG",
                     "Daniel Lang", "Traugott", "ECPNP Deutschland"],
    "leasing_voiture": ["Auto-Leasing-Börse"],
    "energie_eau": ["SWM", "swm", "stadtwerke münchen", "energie", "strom"],
    "assurances": ["ARAG", "arag", "Allianz", "allianz", "HUK", "huk", "versicherung",
                   "AXA", "axa", "devk", "DEVK", "generali", "provinzial", "ERGO", "ergo",
                   "hansemerkur", "HanseMerkur", "continentale", "VR-Bank FFB eG", "DEPOTENTGELT"],
    "abonnements": ["Vodafone", "vodafone", "Netflix", "netflix", "Spotify", "spotify",
                    "Amazon Prime", "prime video", "Disney", "disney", "Apple", "apple.com/bill",
                    "iCloud", "Google", "google storage", "youtube premium", "DAZN", "dazn",
                    "Sky", "sky", "Waipu", "waipu", "Joyn", "joyn", "RTL", "rtl+", "Audible", "audible",
                    "Github", "github", "1und1", "1&1", "STRATO", "strato", "domain", "hosting",
                    "ChatGPT", "chatgpt", "openai", "Claude", "claude", "anthropic",
                    "Midjourney", "midjourney", "Cursor", "cursor"],
    "alimentation": ["Lidl", "lidl", "REWE", "rewe", "EDEKA", "edeka", "ALDI", "aldi",
                     "HIT", "HIT.", "Edeka", "Netto", "netto", "dm-", "DM ", "dm ",
                     "Tegut", "tegut", "PENNY", "penny", "Kaufland", "kaufland",
                     "BIO COMPANY", "bio company", "denn", "Denns", "Alnatura", "alnatura",
                     "VollCorner", "Vollcorner", "Basic", "basic bio", "AEZ", "aez",
                     "Marktkauf", "V-Markt", "v-markt", "GLOBUS", "globus",
                     "BAKING", "Back", "brot", "Brot", "Metzgerei", "metzgerei",
                     "Vinzenzmurr", "vinzenzmurr", "VINZENZMURR"],
    "maison": ["HAGEBAU", "hagebau", "OBI", "obi", "BAUHAUS", "bauhaus",
               "Toom", "toom", "HORNBACH", "hornbach", "Baumarkt",
               "IKEA", "ikea", "Butlers", "butlers", "Depot", "Maisons du monde",
               "XXXLutz", "xxxlutz", "Segmüller", "segmueller", "Roller",
               "POCO", "poco", "JYSK", "jysk", "Dänisches Bettenlager"],
    "enfants": ["Lycee Jean Renoir", "Lycee", "Jean Renoir", "Scolarites", "scolarite",
                "maryvonne", "Maryvonne", "Mary Monique", "Vogl", "vogl",
                "kind", "Kindergarten", "Kita", "kita", "Hort", "hort",
                "Schule", "schule", "Schul", "schul",
                "Eisstadion", "SPORTPARK", "Sportpark", "Eislauf", "eislauf",
                "Spielzeug", "spielzeug", "Kinder", "kinder", "Baby", "baby"],
    "loisirs": ["LUFTHAN", "lufthan", "Eurowings", "eurowings", "RYANAIR", "ryanair",
                "easyJet", "EASYJET", "AIR FRANCE", "air france", "KLM", "klm",
                "Booking.com", "BOOKING", "booking", "Airbnb", "airbnb", "HOTEL", "Hotel", "hotel",
                "Center Parcs", "center parcs", "TUI ", "TUI 4U", "Acherl", "Ferien",
                "DECATHLON", "decathlon", "Fitness", "fitness",
                "McFit", "mcfit", "FitX", "fitx", "FIT/ONE", "Elements", "ELEMENTS",
                "CROSSFIT", "crossfit", "Crossfit",
                "Skiset", "skiset", "SKI", "Ski", "Snowboard",
                "Zalando", "zalando", "ZARA", "zara", "H&M", "h&m", "HM ", "ABOUT YOU", "about you",
                "ASOS", "asos", "MANGO", "mango", "UNIQLO", "uniqlo", "Bershka", "bershka",
                "Pull&Bear", "Stradivarius", "Galeria", "galeria", "Kaufhof", "Karstadt",
                "Breuninger", "breuninger", "Peek", "Cloppenburg",
                "Douglas", "douglas", "Sephora", "sephora", "Müller", "mueller",
                "IKEA", "ikea", "Butlers", "butlers", "Depot", "Maisons du monde",
                "FNAC", "fnac", "SATURN", "saturn", "MediaMarkt", "mediamarkt",
                "Thalia", "thalia", "Hugendubel", "hugendubel", "Buch", "buch",
                "Eventim", "eventim", "Ticketmaster", "ticketmaster", "Kino", "kino",
                "CINEMA", "cinema", "Cinemaxx", "Theater", "theater", "Museum", "museum",
                "Konzert", "konzert", "Festival", "festival",
                "Bar", "BAR", "Club", "club", "Wein", "wein", "Bier", "bier",
                "AMZN Mktp", "amzn", "PayPal", "paypal", "PAYPAL", "Blink ",
                "OTTO", "otto.de", "Ebay", "ebay", "Kleinanzeigen",
                "C&A", "c&a", "H+M 360", "WEMPE", "wempe", "123gold", "GOLD",
                "Amazon", "amazon.de", "AMAZON PAY", "Babeth",
                # Restaurants
                "M8 Coffee", "ALLRESTO", "YORMAS", "yormas", "ALL RESTO",
                "MCDONALD", "mcdonald", "BURGER KING", "burger king",
                "SUBWAY", "subway", "NORDSEE", "nordsee",
                "VAPIANO", "vapiano", "L'Osteria", "L Osteria", "losteria",
                "Starbucks", "starbucks", "Coffee", "coffee", "COFFEE",
                "BAECKEREI", "Baeckerei", "Bäckerei",
                "BACKWERK", "backwerk", "BACK-FACTORY",
                "Baecker", "Bäcker", "Konditorei",
                "Restaurant", "restaurant", "GASTSTAETTE", "Bistro", "bistro",
                "Cafe", "cafe", "CAFE", "Café", "Catering", "catering",
                "Lieferando", "lieferando", "Wolt", "wolt", "Uber Eats", "ubereats",
                "Dominos", "dominos", "Pizza", "pizza",
                "SUSHI", "sushi", "BURGER", "burger", "Döner", "doener",
                "Eis", "Gelato", "gelato", "Asia", "asia",
                "RISTORANTE", "Ristorante", "ristorante", "PIZZERIA", "pizzeria",
                "KoKoNo", "kokoNo", "Wirthaus", "wirthaus",
                "Ochsenbraterei", "ochsenbraterei", "BK TS"],
    "restaurants": [],  # Fusionné dans loisirs, gardé pour compatibilité
    "transport": ["Tankstelle", "tankstelle", "ARAL", "aral", "Shell", "shell", "ESSO", "esso",
                  "Total", "TOTAL", "Jet", "JET", "OMV", "omv", "AGIP", "agip", "BP ",
                  "MVV", "mvv", "MVG", "mvg", "BVG", "bvg", "Ticket", "ticket",
                  "DB Fernverkehr", "DB ", "Deutsche Bahn", "deutsche bahn",
                  "Fahrrad", "fahrrad", "BIKE", "bike", "E-Scooter", "escooter",
                  "TIER", "tier mobility", "LIME", "lime", "BOLT", "bolt",
                  "Parkhaus", "parkhaus", "Parkplatz", "parkplatz", "Parking", "parking",
                  "Taxi", "taxi", "UBER", "uber", "FREE NOW", "free now", "FREENOW",
                  "ADAC", "adac", "KFZ", "kfz", "TUEV", "tuev", "TÜV",
                  "Sixt", "sixt", "Europcar", "europcar", "HERTZ", "hertz",
                  "Flughafen", "flughafen", "AIRPORT", "airport"],
}

# Exclusion patterns (virements internes, investissements)
EXCLUDE_PATTERNS = [
    r'Alexandra\s+Khudyakova',            # virement interne DKB joint
    r'Vincent.*Le\s*[Ff]ort',              # tout virement interne Vincent
    r'VR-Bank FFB.*Abwicklungskonten',      # remboursement carte credit (interne)
    r'Scalable Capital',                    # investissement (suivi separe)
    r'DKB AG\s+-',                          # frais DKB technique
    r'Abschluss\s+-?[\d\.]+,\d{2}',       # frais de tenue de compte
    r'Lastschrift aus Kartenzahlung',        # ecriture technique
    r'MÜNCHNER BANK',                        # distributeur/retrait (deja comptabilise dans achat)
    r'VR BANK MÜNCHEN LAND',                # retrait especes
    r'Auto-Leasing',                         # hors scope
]

REVENU_PATTERNS = [
    r'OVH GMBH',  # salaire
]

CATEGORY_EXCLUDE = [
    "loyer"  # Traité à part
]


def normalize_date(date_str, year=2025):
    """Normalise une date allemande (DD.MM.YY ou DD.MM.YYYY) en YYYY-MM-DD."""
    date_str = date_str.strip()
    # DD.MM.YY
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{2})$', date_str)
    if m:
        d, mo, y = m.groups()
        y = int(y)
        if y < 50: y += 2000
        else: y += 2000 if y < 100 else y
        return f"{y}-{mo}-{d}"
    # DD.MM.YYYY
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})$', date_str)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d}"
    return None


def parse_amount(amount_str):
    """Parse un montant allemand: -1.234,56 EUR -> -1234.56"""
    amount_str = amount_str.replace("EUR", "").strip()
    # Remove leading + sign
    amount_str = amount_str.lstrip('+')
    # German format: 1.234,56
    if re.match(r'^-?[\d\.]+,\d{2}$', amount_str):
        amount_str = amount_str.replace(".", "").replace(",", ".")
    elif re.match(r'^-?\d+,\d{2}$', amount_str):
        amount_str = amount_str.replace(",", ".")
    return float(amount_str)


def categorize(description):
    """Retourne la catégorie basée sur la description."""
    desc_lower = description.lower()
    # Revenus d'abord
    for pat in REVENU_PATTERNS:
        if re.search(pat, description, re.IGNORECASE):
            return "revenus"
    # Categories
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in desc_lower:
                return cat
    return "divers"


def is_excluded(description):
    """Vérifie si la transaction doit être exclue (virement interne, investissement)."""
    for pat in EXCLUDE_PATTERNS:
        if re.search(pat, description, re.IGNORECASE):
            return True
    return False


def extract_vkb_giro(pdf_path):
    """Extrait les transactions du compte Giro VKB."""
    transactions = []
    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        print(f"  Erreur ouverture {pdf_path}: {e}")
        return transactions

    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip header/footer lines
            if any(skip in line for skip in ['Endsaldo', 'Abschluss per', 'Kontokorrent', 'Filterparameter',
                                               'BIC ', 'IBAN ', 'Kontoinhaber', 'Abgefragt', 'Umsätze',
                                               'Seite ', 'Wir machen den Weg', 'Volksbanken Raiffeisenbanken',
                                               'Buchungsdatum', 'Valuta ', 'Abrechnung ', 'SecureGo']):
                i += 1
                continue

            # Chercher montant EUR
            m = re.search(r'([+-]?[\d\.]+,\d{2})\s*EUR', line)
            if m:
                raw_amount = m.group(1).replace('.', '').replace(',', '.')
                # Skip si c'est un solde (nombre trop grand, positif uniquement sur ligne vide)
                try:
                    amount = float(raw_amount)
                except ValueError:
                    i += 1
                    continue

                # Skip les soldes et lignes hors contexte
                if abs(amount) > 50000:
                    i += 1
                    continue

                # Chercher la date (DD.MM.YYYY) sur cette ligne ou la suivante
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
                if not date_match:
                    # Chercher sur ligne suivante
                    if i + 1 < len(lines):
                        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', lines[i + 1])

                if date_match:
                    date_str = normalize_date(date_match.group(1))
                    # Prendre le nom du bénéficiaire (partie avant le montant)
                    beneficiary = re.sub(r'\s*[+-]?[\d\.]+,\d{2}\s*EUR.*', '', line).strip()
                    # Nettoyer les dates résiduelles
                    beneficiary = re.sub(r'\d{2}\.\d{2}\.\d{4}', '', beneficiary).strip()

                    if date_str and amount != 0 and not is_excluded(line) and beneficiary:
                        cat = categorize(beneficiary)
                        transactions.append({
                            "date": date_str,
                            "description": beneficiary[:120],
                            "amount": round(amount, 2),
                            "categorie": cat,
                            "source": "VKB_Giro"
                        })
            i += 1
    pdf.close()
    return transactions


def extract_vkb_visa(pdf_path):
    """Extrait les transactions de la carte credit VKB (Mastercard).
    Le marchand est sur la/les lignes APRES "Basislastschrift".
    Structure: Basislastschrift -XX,XX EUR [\n Merchant EUR XX,XX Valuta ...] [\n Umsatz vom ...]
    """
    transactions = []
    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        print(f"  Erreur ouverture {pdf_path}: {e}")
        return transactions

    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip header/footer
            if any(skip in line for skip in ['Endsaldo', 'Kontokorrent', 'Filterparameter',
                                               'BIC ', 'IBAN ', 'Kontoinhaber', 'Abgefragt', 'Umsätze',
                                               'Seite ', 'Wir machen den Weg', 'Kreditkartenkonto',
                                               'Abrechnung vom']):
                i += 1
                continue

            # Format: "Basislastschrift -117,80 EUR" ou "Gutschrift +607,44 EUR"
            m = re.search(r'(Basislastschrift|Gutschrift)\s+([+-]?[\d\.]+,\d{2})\s*EUR', line)
            if m:
                amount = parse_amount(m.group(2))
                if m.group(1) == "Gutschrift":
                    amount = abs(amount)
                else:
                    amount = -abs(amount)

                # Chercher le marchand sur 1-3 lignes suivantes
                desc_parts = []
                date_str = None
                for j in range(1, 5):
                    if i + j >= len(lines):
                        break
                    next_line = lines[i + j].strip()
                    # Skip technical lines
                    if re.search(r'^(Valuta|Basislastschrift|Gutschrift|Seite |Wir machen)', next_line):
                        break
                    # Extract date if found
                    dm = re.search(r'(\d{2}\.\d{2}\.\d{4})', next_line)
                    if dm:
                        date_str = normalize_date(dm.group(1))
                    # Collect merchant description part (before EUR/Valuta)
                    merchant = re.sub(r'\s*EUR.*', '', next_line).strip()
                    merchant = re.sub(r'-?\s*[\d\.]+,\d{2}\s*', '', merchant).strip()
                    merchant = re.sub(r'Valuta.*', '', merchant).strip()
                    merchant = re.sub(r'Umsatz vom.*', '', merchant).strip()
                    if merchant and not re.match(r'^\d{2}\.\d{2}\.\d{4}$', merchant):
                        desc_parts.append(merchant)
                    # Stop at Valuta line
                    if 'Valuta' in next_line:
                        break

                desc = ' '.join(desc_parts).strip()

                # Fallback: try date from Umsatz vom line
                if not date_str:
                    for j in range(1, 5):
                        if i + j >= len(lines):
                            break
                        dm = re.search(r'Umsatz vom (\d{2}\.\d{2}\.\d{4})', lines[i + j])
                        if dm:
                            date_str = normalize_date(dm.group(1))
                            break

                if date_str and amount != 0 and desc and not is_excluded(desc):
                    cat = categorize(desc)
                    transactions.append({
                        "date": date_str,
                        "description": desc[:120],
                        "amount": round(amount, 2),
                        "categorie": cat,
                        "source": "VKB_Visa"
                    })
            i += 1
    pdf.close()
    return transactions


def extract_dkb_giro(pdf_path):
    """Extrait les transactions du compte DKB Giro (Unknown.pdf)."""
    transactions = []
    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        print(f"  Erreur ouverture {pdf_path}: {e}")
        return transactions

    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Format DKB: "05.08.26 Jörg Kottsieper -3.150,00"
            m = re.match(r'(\d{2}\.\d{2}\.\d{2})\s+(.+?)\s+([+-]?[\d\.]+,\d{2})', line)
            if m:
                date_str = normalize_date(m.group(1))
                beneficiary = m.group(2).strip()
                amount = parse_amount(m.group(3))

                # Éviter les lignes IBAN
                if re.match(r'IBAN', beneficiary):
                    i += 1
                    continue

                if date_str and amount != 0 and not is_excluded(line):
                    cat = categorize(beneficiary)
                    transactions.append({
                        "date": date_str,
                        "description": beneficiary[:120],
                        "amount": round(amount, 2),
                        "categorie": cat,
                        "source": "DKB_Giro"
                    })
            i += 1
    pdf.close()
    return transactions


def build_monthly_aggregates(transactions, start_month="2025-01", end_month="2026-08"):
    """Agrège les transactions par mois."""
    monthly = defaultdict(lambda: {"revenus": 0, "depenses": defaultdict(float), "total_depenses": 0, "epargne": 0})

    for t in transactions:
        month = t["date"][:7]
        if t["categorie"] == "revenus" or t["amount"] > 0:
            monthly[month]["revenus"] += abs(t["amount"])
        else:
            cat = t["categorie"]
            monthly[month]["depenses"][cat] += abs(t["amount"])
            monthly[month]["total_depenses"] += abs(t["amount"])

    result = []
    for m in sorted(monthly.keys()):
        if m < start_month or m > end_month:
            continue
        d = monthly[m]
        result.append({
            "mois": m,
            "revenus": round(d["revenus"], 2),
            "depenses": {k: round(v, 2) for k, v in sorted(d["depenses"].items(), key=lambda x: -x[1])},
            "total_depenses": round(d["total_depenses"], 2),
            "epargne": round(d["revenus"] - d["total_depenses"], 2)
        })
    return result


def build_category_breakdown(transactions):
    """Analyse détaillée par catégorie."""
    cats = defaultdict(lambda: {"total": 0, "count": 0, "top": [], "mois": defaultdict(float)})

    for t in transactions:
        if t["amount"] >= 0:
            continue
        cat = t["categorie"]
        amount = abs(t["amount"])
        cats[cat]["total"] += amount
        cats[cat]["count"] += 1
        cats[cat]["mois"][t["date"][:7]] += amount
        cats[cat]["top"].append({"date": t["date"], "description": t["description"], "amount": amount})

    result = {}
    for cat, data in cats.items():
        top10 = sorted(data["top"], key=lambda x: -x["amount"])[:10]
        result[cat] = {
            "total": round(data["total"], 2),
            "nb_transactions": data["count"],
            "moyen_mensuel": round(data["total"] / 21, 2),  # 21 mois
            "top10": top10,
            "par_mois": dict(sorted(data["mois"].items()))
        }
    return result


def build_top_global(transactions):
    """Top 10 dépenses globales."""
    depenses = [t for t in transactions if t["amount"] < 0]
    depenses.sort(key=lambda t: t["amount"])  # plus négatif = plus grosse dépense
    top10 = []
    for t in depenses[:10]:
        top10.append({
            "date": t["date"],
            "description": t["description"],
            "amount": abs(t["amount"]),
            "categorie": t["categorie"]
        })
    return top10


def build_loisirs_analysis(transactions):
    """Analyse détaillée des loisirs."""
    loisirs = [t for t in transactions if t["categorie"] == "loisirs" and t["amount"] < 0]

    # Sous-catégories
    sous_cats = {
        "voyages": ["LUFTHAN", "Eurowings", "RYANAIR", "easyJet", "AIR FRANCE", "KLM",
                     "Booking.com", "BOOKING", "Airbnb", "HOTEL", "Hotel"],
        "sport": ["DECATHLON", "Fitness", "McFit", "FitX", "FIT/ONE", "Elements",
                  "Skiset", "SKI", "Ski", "Snowboard"],
        "shopping": ["Zalando", "ZARA", "H&M", "ABOUT YOU", "ASOS", "MANGO",
                     "UNIQLO", "Bershka", "Pull&Bear", "Amazon", "otto.de", "OTTO",
                     "IKEA", "Breuninger", "Galeria"],
        "streaming_media": ["Netflix", "Spotify", "Prime Video", "Disney", "Apple",
                            "iCloud", "DAZN", "Sky", "Audible", "YouTube"],
        "sorties": ["Eventim", "Ticketmaster", "Kino", "CINEMA", "Cinemaxx",
                    "Theater", "Museum", "Konzert", "Festival"],
        "restos_bars": ["Restaurant", "GASTSTAETTE", "Bistro", "Cafe", "CAFE",
                        "Café", "BAECKEREI", "Bäckerei", "Eis", "SUSHI", "PIZZA",
                        "BURGER", "Döner", "Asia", "Wein", "Bier", "Bar", "Club"],
        "maison_deco": ["IKEA", "Butlers", "Depot", "Maisons du monde"],
        "culture": ["Thalia", "Hugendubel", "Buch", "FNAC", "MediaMarkt", "SATURN"],
    }

    breakdown = defaultdict(lambda: {"total": 0, "count": 0})
    for t in loisirs:
        desc = t["description"]
        found = False
        for sc, kws in sous_cats.items():
            for kw in kws:
                if kw.lower() in desc.lower() or kw in desc:
                    breakdown[sc]["total"] += abs(t["amount"])
                    breakdown[sc]["count"] += 1
                    found = True
                    break
            if found:
                break
        if not found:
            breakdown["autres"]["total"] += abs(t["amount"])
            breakdown["autres"]["count"] += 1

    # Mois les plus dépensiers
    mois_loisirs = defaultdict(float)
    for t in loisirs:
        mois_loisirs[t["date"][:7]] += abs(t["amount"])

    top_mois = sorted(mois_loisirs.items(), key=lambda x: -x[1])[:5]

    total_loisirs = sum(abs(t["amount"]) for t in loisirs)

    return {
        "total": round(total_loisirs, 2),
        "nb_transactions": len(loisirs),
        "moyen_mensuel": round(total_loisirs / 21, 2),
        "sous_categories": {k: {"total": round(v["total"], 2), "count": v["count"]}
                            for k, v in sorted(breakdown.items(), key=lambda x: -x[1]["total"])},
        "mois_top5": [{"mois": m, "total": round(v, 2)} for m, v in top_mois]
    }


def build_enfants_analysis(transactions):
    """Analyse détaillée des dépenses enfants."""
    enfants = [t for t in transactions if t["categorie"] == "enfants" and t["amount"] < 0]

    # Sous-catégories
    sous_cats = {
        "lycee_jean_renoir": ["Lycee Jean Renoir", "Lycee", "Jean Renoir", "Scolarites"],
        "maryvonne": ["maryvonne", "Maryvonne", "Mary Monique", "Vogl"],
        "activites": ["Eisstadion", "SPORTPARK", "Sportpark", "Eislauf"],
        "pension": [],
        "autres": [],
    }

    breakdown = defaultdict(lambda: {"total": 0, "count": 0})
    for t in enfants:
        desc = t["description"]
        found = False
        for sc, kws in sous_cats.items():
            for kw in kws:
                if kw.lower() in desc.lower() or kw in desc:
                    breakdown[sc]["total"] += abs(t["amount"])
                    breakdown[sc]["count"] += 1
                    found = True
                    break
            if found:
                break
        if not found:
            breakdown["autres"]["total"] += abs(t["amount"])
            breakdown["autres"]["count"] += 1

    total_enfants = sum(abs(t["amount"]) for t in enfants)

    return {
        "total": round(total_enfants, 2),
        "nb_transactions": len(enfants),
        "moyen_mensuel": round(total_enfants / 21, 2),
        "sous_categories": {k: {"total": round(v["total"], 2), "count": v["count"]}
                            for k, v in sorted(breakdown.items(), key=lambda x: -x[1]["total"])}
    }


def main():
    print("=== Extraction transactions PDF ===")

    all_tx = []

    # VKB Giro (2 fichiers)
    for fname in ["VKB_1.pdf", "VKB_2.pdf"]:
        fpath = os.path.join(PDF_DIR, fname)
        if os.path.exists(fpath):
            print(f"  Parsing {fname}...")
            tx = extract_vkb_giro(fpath)
            all_tx.extend(tx)
            print(f"    -> {len(tx)} transactions")

    # VKB Visa (2 fichiers)
    for fname in ["DKB_1.pdf", "DKB_2.pdf"]:
        fpath = os.path.join(PDF_DIR, fname)
        if os.path.exists(fpath):
            print(f"  Parsing {fname} (Visa)...")
            tx = extract_vkb_visa(fpath)
            all_tx.extend(tx)
            print(f"    -> {len(tx)} transactions")

    # DKB Giro
    fpath = os.path.join(PDF_DIR, "Unknown.pdf")
    if os.path.exists(fpath):
        print(f"  Parsing Unknown.pdf (DKB Giro)...")
        tx = extract_dkb_giro(fpath)
        all_tx.extend(tx)
        print(f"    -> {len(tx)} transactions")

    print(f"\nTotal transactions extraites: {len(all_tx)}")

    # Trier par date
    all_tx.sort(key=lambda t: t["date"])

    # Agregations
    print("  Building monthly aggregates...")
    monthly = build_monthly_aggregates(all_tx)

    print("  Building category breakdown...")
    categories = build_category_breakdown(all_tx)

    print("  Building top 10 global...")
    top_global = build_top_global(all_tx)

    print("  Building loisirs analysis...")
    loisirs = build_loisirs_analysis(all_tx)

    print("  Building enfants analysis...")
    enfants = build_enfants_analysis(all_tx)

    # Stats globales
    total_depenses = sum(abs(t["amount"]) for t in all_tx if t["amount"] < 0)
    total_revenus = sum(t["amount"] for t in all_tx if t["amount"] > 0)

    # Transactions par catégorie pour drill-down (top 50 par catégorie)
    tx_by_cat = defaultdict(list)
    for t in all_tx:
        if t["amount"] < 0:
            tx_by_cat[t["categorie"]].append({
                "d": t["date"], "n": t["description"][:80], "a": round(abs(t["amount"]), 2)
            })
    drilldown = {}
    for cat, tx_list in tx_by_cat.items():
        drilldown[cat] = sorted(tx_list, key=lambda x: -x["a"])[:50]

    output = {
        "generated": datetime.now().isoformat()[:16],
        "periode": "2025-01 à 2026-08",
        "nb_transactions": len(all_tx),
        "total_revenus": round(total_revenus, 2),
        "total_depenses": round(total_depenses, 2),
        "monthly": monthly,
        "categories": categories,
        "top_global": top_global,
        "loisirs": loisirs,
        "enfants": enfants,
        "drilldown": drilldown
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nFichier genere: {OUTPUT}")
    print(f"  Transactions: {len(all_tx)}")
    print(f"  Categories: {len(categories)}")
    print("Done.")


if __name__ == "__main__":
    main()
