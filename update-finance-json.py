#!/usr/bin/env python3
"""Generate finance.json + finance_detail.json from VKB PDFs (corrected 2026 analysis)."""
import pdfplumber, re, json, os
from collections import defaultdict
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
PDF_DIR = '/home/openclaw/finance/releves'

def parse_vkb_giro_2026(path):
    """Parse VKB Giro checking account PDF (2026 format)."""
    tx = []
    pdf = pdfplumber.open(path)
    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue
        for line in text.split('\n'):
            line = line.strip()
            m = re.match(r'^(.+?)\s+([+-][\d\.]+,\d{2})\s*EUR$', line)
            if not m:
                continue
            desc = m.group(1).strip()
            amount = float(m.group(2).replace('.', '').replace(',', '.'))
            if 'Abschluss' in desc:
                continue
            # Find date in surrounding text
            date_str = None
            full_text = text
            idx = full_text.find(line)
            if idx >= 0:
                around = full_text[max(0, idx - 200):idx + len(line) + 200]
                dm = re.findall(r'(\d{2})\.(\d{2})\.(\d{4})', around)
                if dm:
                    d, mo, y = dm[-1]
                    date_str = f"{y}-{mo}-{d}"
            if date_str:
                tx.append({
                    'date': date_str, 'desc': desc, 'amount': amount,
                    'raw': f"{desc} {amount:+.2f}€"
                })
    pdf.close()
    return tx

def parse_vkb_visa_2026(path):
    """Parse VKB Visa credit card PDF (2026 format)."""
    tx = []
    pdf = pdfplumber.open(path)
    full_text = []
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            full_text.append(text)
    pdf.close()

    lines = '\n'.join(full_text).split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r'^(Basislastschrift|Gutschrift)\s+([+-][\d\.]+,\d{2})\s*EUR$', line)
        if m:
            amount = float(m.group(2).replace('.', '').replace(',', '.'))
            if i + 1 < len(lines):
                ml = lines[i + 1].strip()
                merchant = re.sub(r'\s*EUR\s+.*$', '', ml).strip()
                date_str = None
                dm = re.search(r'Valuta\s+(\d{2})\.(\d{2})\.(\d{4})', ml)
                if dm:
                    date_str = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"
                if not date_str and i + 2 < len(lines):
                    dm2 = re.search(r'Umsatz vom\s+(\d{2})\.(\d{2})\.(\d{4})', lines[i + 2])
                    if dm2:
                        date_str = f"{dm2.group(3)}-{dm2.group(2)}-{dm2.group(1)}"
                if date_str and merchant and 'Abrechnung' not in merchant:
                    tx.append({
                        'date': date_str, 'desc': f"CB {merchant}", 'amount': amount,
                        'raw': f"CB {merchant} {amount:+.2f}€"
                    })
            i += 2
            continue
        i += 1
    return tx

def categorize_giro(desc, amount):
    """Categorize a Giro transaction."""
    a = abs(amount)
    d = desc
    if 'Lycee' in d:
        return 'enfants'
    if 'C24 Bank' in d:
        return 'credit_conso'
    if 'Scalable Capital' in d:
        return 'epargne'
    if 'VR-Bank FFB - Abwicklung' in d:
        return 'carte_credit'
    if 'Vincent le fort' in d:
        return 'loyer' if 1900 <= a <= 2100 else 'epargne'
    if 'Barmenia' in d or 'Allianz' in d or 'VERSICHERUNGSKAMMER' in d:
        return 'assurances'
    if 'Vodafone' in d:
        return 'abonnements'
    if 'FitX' in d:
        return 'sport'
    if 'AMAZON' in d:
        return 'achats_online'
    if any(w in d for w in ['REWE', 'LIDL', 'EDEKA', 'ALDI', 'ANDERL', 'WUENSCHE', 'DM ']):
        return 'alimentation'
    if any(w in d for w in ['ARAL', 'Tankstelle', 'Drivers Inn', 'ALLGUTH']):
        return 'transport'
    if any(w in d for w in ['RISTORANTE', 'LOsteria', 'KOKONO', 'EL GRECO',
                              'Ochsenbraterei', 'Peter Pane', 'BK TS', 'BB Coffee',
                              'DZ BANK', 'Ngoc Ha', 'DA NOI', 'Traugott', 'SG-VR Payment']):
        return 'loisirs'
    if 'CARDPOINT' in d or 'MÜNCHNER BANK' in d:
        return 'divers'
    if 'IKEA' in d:
        return 'maison'
    if 'STADTWERKE' in d:
        return 'energie'
    if 'ELENA THOMAS' in d:
        return 'juridique'
    return None

def categorize_visa(merchant):
    """Categorize a Visa credit card transaction."""
    m = merchant
    if 'AMAZON' in m:
        return 'achats_online'
    if any(w in m for w in ['Lidl', 'REWE', 'EDEKA', 'ALDI', 'DM ']):
        return 'alimentation'
    if any(w in m for w in ['Drivers Inn', 'Shell', 'ARAL', 'ALLGUTH']):
        return 'transport'
    if any(w in m for w in ['Restaurant', 'Ristorante', 'Pizzeria', 'BIERGARTEN',
                              'Gaststaette', 'Wirthaus', 'STEINSEE', 'Strandbad',
                              'Schliersberg', 'Feringasee', 'SEESTUB', 'KOKONO',
                              'Haidhauser', 'SPC*', 'Schmid', 'Ngocha', 'Die2Bar',
                              'Cafe', 'GUT KALTENBRUNN', 'MCDONALD', 'Foodji',
                              'AUTOGRILL', 'DALLMAYR', 'MERCI', 'AK PARIS',
                              'SC-RODZAR', 'SUPER 15V', 'Steinsee', 'Ochsenbraterei',
                              'BAECKEREI']):
        return 'loisirs'
    if any(w in m for w in ['MUC AIRPORT', 'Lagard', 'RELAY']):
        return 'transport'
    if any(w in m for w in ['LUFTHAN', 'TUI', 'Booking', 'VINCCI', 'KARS',
                              'Paul Camper', '123gold']):
        return 'loisirs'
    if any(w in m for w in ['MUeLLER', 'Peek', 'Charles Tyrwhitt', 'Birkenstock',
                              'New Balance']):
        return 'achats_online'
    if 'DECATHLON' in m or 'Mol*Bike' in m:
        return 'sport'
    if 'SUPERPROF' in m:
        return 'enfants'
    if 'Hagebau' in m or 'Pools' in m:
        return 'maison'
    if any(w in m for w in ['Barauszahlung', 'KREISSPARKASSE', 'VR BANK', 'ICC10718']):
        return 'divers'
    if 'First Data' in m:
        return 'divers'
    if any(w in m for w in ['HANDYPARKEN', 'PARKSTER', 'PARKING']):
        return 'transport'
    return None

CAT_LABELS = {
    'loyer': 'Loyer DKB',
    'carte_credit': 'CB Visa (lifestyle)',
    'enfants': 'Lycee (net 1/3)',
    'credit_conso': 'Credit C24',
    'epargne': 'Epargne (Scalable + virements)',
    'alimentation': 'Alimentation',
    'loisirs': 'Loisirs & sorties',
    'achats_online': 'Achats online',
    'transport': 'Transport & essence',
    'assurances': 'Assurances',
    'abonnements': 'Abonnements',
    'sport': 'Sport',
    'maison': 'Maison',
    'energie': 'Energie',
    'juridique': 'Juridique',
    'divers': 'Divers'
}

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # Parse PDFs
    giro = parse_vkb_giro_2026(os.path.join(PDF_DIR, 'VKB_2026_giro.pdf'))
    visa = parse_vkb_visa_2026(os.path.join(PDF_DIR, 'VKB_2026_visa.pdf'))

    # Build monthly aggregation
    monthly = defaultdict(lambda: {
        'revenus': 0.0, 'depenses': defaultdict(float),
        'total_depenses': 0.0, 'epargne': 0.0, 'details': []
    })

    for t in giro:
        if not ('2026-01-01' <= t['date'] <= '2026-08-31'):
            continue
        m = t['date'][:7]
        a = t['amount']
        if a > 0:
            if any(w in t['desc'] for w in ['OVH', 'Mary', 'Alexandra']):
                monthly[m]['revenus'] += a
        else:
            cat = categorize_giro(t['desc'], a)
            if cat == 'epargne':
                monthly[m]['epargne'] += abs(a)
            elif cat:
                monthly[m]['depenses'][cat] += abs(a)
                monthly[m]['total_depenses'] += abs(a)
                monthly[m]['details'].append({
                    'd': t['date'], 'c': cat,
                    'a': round(abs(a), 2), 'n': t['raw'][:80]
                })

    for t in visa:
        if not ('2026-01-01' <= t['date'] <= '2026-08-31'):
            continue
        m = t['date'][:7]
        if t['amount'] < 0:
            cat = categorize_visa(t['desc'])
            if cat:
                monthly[m]['depenses'][cat] += abs(t['amount'])
                monthly[m]['total_depenses'] += abs(t['amount'])
                monthly[m]['details'].append({
                    'd': t['date'], 'c': cat,
                    'a': round(abs(t['amount']), 2), 'n': t['raw'][:80]
                })

    months_list = sorted(m for m in monthly if '2026' in m)
    n = len(months_list)
    if n == 0:
        print("WARNING: no 2026 data found!")
        return

    avg_revenus = sum(monthly[m]['revenus'] for m in months_list) / n
    avg_depenses_by_cat = defaultdict(float)
    for m in months_list:
        for cat, val in monthly[m]['depenses'].items():
            avg_depenses_by_cat[cat] += val / n
    avg_epargne = sum(monthly[m]['epargne'] for m in months_list) / n
    avg_total_depenses = sum(monthly[m]['total_depenses'] for m in months_list) / n

    # ── finance.json ──
    donut_cats = {}
    for cat, val in sorted(avg_depenses_by_cat.items(), key=lambda x: -x[1]):
        donut_cats[CAT_LABELS.get(cat, cat)] = round(val, 2)
    if avg_epargne > 0:
        donut_cats['Epargne (Scalable + virements)'] = round(avg_epargne, 2)

    finance_json = {
        "periode": "Janvier a Aout 2026 (corrige)",
        "mois_analyses": n,
        "revenus_mensuels_nets": round(avg_revenus, 2),
        "source_revenus": "OVH (CA mensuel) + remb. Mary/Alexandra (Lycee 1/3)",
        "depenses_fixes": {
            "loyer_DKB": 2000.00,
            "credit_C24": round(avg_depenses_by_cat.get('credit_conso', 0), 2),
            "lycee_net_1_3_vincent": round(avg_depenses_by_cat.get('enfants', 0), 2),
            "assurances": round(avg_depenses_by_cat.get('assurances', 0), 2),
            "abonnements": round(avg_depenses_by_cat.get('abonnements', 0), 2)
        },
        "depenses_variables": {
            "carte_credit_lifestyle": round(avg_depenses_by_cat.get('carte_credit', 0), 2),
            "alimentation": round(avg_depenses_by_cat.get('alimentation', 0), 2),
            "loisirs": round(avg_depenses_by_cat.get('loisirs', 0), 2),
            "achats_online": round(avg_depenses_by_cat.get('achats_online', 0), 2),
            "transport": round(avg_depenses_by_cat.get('transport', 0), 2),
            "sport": round(avg_depenses_by_cat.get('sport', 0), 2),
            "maison": round(avg_depenses_by_cat.get('maison', 0), 2),
            "divers": round(avg_depenses_by_cat.get('divers', 0), 2)
        },
        "total_depenses_mensuelles": round(avg_total_depenses, 2),
        "epargne_mensuelle": round(avg_epargne, 2),
        "capacite_epargne_pct": round(avg_epargne / avg_revenus * 100, 1) if avg_revenus > 0 else 0,
        "note_calcul": "Corrige 2026. Loyer 2000€. Lycee 1/3 Vincent. CB Visa = lifestyle. Epargne = Scalable + virements >2000€. Virements internes exclus.",
        "donut_categories": donut_cats,
        "comptes": {
            "VKB_Giro": {"solde_final": "+15.779,60 EUR (09.08.2026)"},
            "DKB_Giro": {"titulaires": "Vincent Le Fort et Alexandra Khudyakova"},
            "DKB_Visa": {"solde_final": "-3.273,07 EUR (09.08.2026)"}
        }
    }
    with open(os.path.join(DATA_DIR, 'finance.json'), 'w') as f:
        json.dump(finance_json, f, ensure_ascii=False, indent=2)

    # ── finance_detail.json ──
    detail_json = {
        "generated": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "periode": "Janvier a Aout 2026 (corrige)",
        "nb_transactions_giro": len([tx for tx in giro if '2026' in tx['date']]),
        "nb_transactions_visa": len([tx for tx in visa if '2026' in tx['date']]),
        "total_revenus": round(sum(monthly[m]['revenus'] for m in months_list), 2),
        "total_depenses": round(sum(monthly[m]['total_depenses'] for m in months_list), 2),
        "monthly": [],
        "categories": {},
        "top_global": [],
        "loisirs": {"total": 0, "sub_categories": {}, "monthly": {}},
        "enfants": {"total": 0, "sub_categories": {}, "monthly": {}},
        "drilldown": {}
    }

    for m in months_list:
        md = monthly[m]
        entry = {
            "mois": m,
            "revenus": round(md['revenus'], 2),
            "depenses": {CAT_LABELS.get(k, k): round(v, 2)
                        for k, v in sorted(md['depenses'].items(), key=lambda x: -x[1])},
            "total_depenses": round(md['total_depenses'], 2),
            "epargne": round(md['epargne'], 2)
        }
        detail_json["monthly"].append(entry)

    for cat_key, cat_label in CAT_LABELS.items():
        cat_drill = []
        cat_total = 0
        for m in months_list:
            for tx in monthly[m]['details']:
                if tx['c'] == cat_key:
                    cat_total += tx['a']
                    cat_drill.append(tx)
        if cat_total > 0:
            detail_json["categories"][cat_label] = round(cat_total, 2)
            cat_drill.sort(key=lambda x: -x['a'])
            detail_json["drilldown"][cat_label] = cat_drill[:50]

    all_details = []
    for m in months_list:
        all_details.extend(monthly[m]['details'])
    all_details.sort(key=lambda x: -x['a'])
    detail_json["top_global"] = all_details[:20]

    # Loisirs analysis
    loisirs_total = 0
    loirs_sub = defaultdict(float)
    loirs_mo = defaultdict(float)
    for m in months_list:
        for tx in monthly[m]['details']:
            if tx['c'] == 'loisirs':
                loisirs_total += tx['a']
                loirs_mo[tx['d'][:7]] += tx['a']
                n = tx['n'].lower()
                if any(w in n for w in ['restaurant', 'ristorante', 'pizzeria', 'baeckerei',
                                          'biergarten', 'gaststaette', 'wirthaus', 'steinsee',
                                          'strandbad', 'schliersberg', 'feringasee', 'seestub',
                                          'kokono', 'haidhauser', 'spc*', 'schmid', 'ngocha',
                                          'die2bar', 'cafe', 'gut kaltenbrunn', 'mcdonald',
                                          'foodji', 'autogrill', 'dallmayr', 'merci', 'ak paris',
                                          'ochsenbraterei']):
                    loirs_sub['Restaurants'] += tx['a']
                elif any(w in n for w in ['lufthan', 'tui', 'booking', 'vincci', 'kars',
                                            'paul camper', 'airport', 'relay', 'lagard']):
                    loirs_sub['Voyages'] += tx['a']
                elif any(w in n for w in ['mueller', 'peek', 'charles tyrwhitt', 'birkenstock',
                                            'new balance', 'decathlon', 'mol*bike']):
                    loirs_sub['Shopping'] += tx['a']
                elif '123gold' in n:
                    loirs_sub['Or / Divers'] += tx['a']
                else:
                    loirs_sub['Autres loisirs'] += tx['a']

    detail_json["loisirs"]["total"] = round(loisirs_total, 2)
    detail_json["loisirs"]["sub_categories"] = {
        k: round(v, 2) for k, v in sorted(loirs_sub.items(), key=lambda x: -x[1])
    }
    detail_json["loisirs"]["monthly"] = {
        k: round(v, 2) for k, v in sorted(loirs_mo.items())
    }

    # Enfants analysis
    enfants_total = 0
    enfants_sub = defaultdict(float)
    enfants_mo = defaultdict(float)
    for m in months_list:
        for tx in monthly[m]['details']:
            if tx['c'] == 'enfants':
                enfants_total += tx['a']
                enfants_mo[tx['d'][:7]] += tx['a']
                n = tx['n'].lower()
                if 'lycee' in n:
                    enfants_sub['Lycee Jean Renoir'] += tx['a']
                elif 'superprof' in n:
                    enfants_sub['Cours particuliers'] += tx['a']
                else:
                    enfants_sub['Autres enfants'] += tx['a']

    detail_json["enfants"]["total"] = round(enfants_total, 2)
    detail_json["enfants"]["sub_categories"] = {
        k: round(v, 2) for k, v in sorted(enfants_sub.items(), key=lambda x: -x[1])
    }
    detail_json["enfants"]["monthly"] = {
        k: round(v, 2) for k, v in sorted(enfants_mo.items())
    }

    with open(os.path.join(DATA_DIR, 'finance_detail.json'), 'w') as f:
        json.dump(detail_json, f, ensure_ascii=False, indent=2)

    print(f"OK: {n} mois, {round(avg_revenus)}€ revenus, {round(avg_epargne)}€ epargne, "
          f"{round(avg_total_depenses)}€ depenses, {len(all_details)} tx")

if __name__ == '__main__':
    main()
