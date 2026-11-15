#!/usr/bin/env python3
"""
fetch_market_data.py - Layer 1 data fetcher v3.1
Fonti automatiche:
  - ECB eurofxref-daily.xml (T1): EUR/USD, EUR/JPY, EUR/GBP, EUR/CHF, USD/JPY calcolato
  - FRED fredgraph.csv (T1): UST 2/5/10/30Y, VIX, S&P 500, Nasdaq, Dow, Brent, WTI,
    Henry Hub, Fed funds (upper), BCE deposit facility
  - ANSA economia: headlines
I campi non coperti restano N/D e vanno integrati con merge_supplement.py
(dati raccolti via Bigdata.com o altre fonti, con fonte/tier/data dichiarati).

Uso: python3 fetch_market_data.py [--date-report DD/MM/YYYY] [--date-chiusura DD/MM/YYYY]
Output: $FDR_WORK_DIR/market_data.json
"""
import argparse
import csv
import io
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from urllib.request import Request, urlopen

from fdr_common import CATEGORIES, MARKET_DATA_PATH, ensure_dirs, save_market_data

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
}

# key -> (categoria, chiave, unita' delta: "pct" | "bp" | None)
FRED_SERIES = {
    "DGS2": ("bonds", "UST_2Y", "bp"),
    "DGS5": ("bonds", "UST_5Y", "bp"),
    "DGS10": ("bonds", "UST_10Y", "bp"),
    "DGS30": ("bonds", "UST_30Y", "bp"),
    "VIXCLS": ("volatility", "VIX", "pct"),
    "SP500": ("indices", "SP500", "pct"),
    "NASDAQCOM": ("indices", "NASDAQ", "pct"),
    "DJIA": ("indices", "DJI", "pct"),
    "DCOILBRENTEU": ("commodities", "BRENT", "pct"),
    "DCOILWTICO": ("commodities", "WTI", "pct"),
    "DHHNGSP": ("commodities", "NAT_GAS", "pct"),
    "DFEDTARU": ("macro", "FED_RATE", None),
    "ECBDFR": ("macro", "BCE_RATE", None),
}

PLACEHOLDER_KEYS = {
    "bonds": ["BUND_10Y", "BTP_10Y", "UST_2Y", "UST_5Y", "UST_10Y", "UST_30Y", "OAT_10Y",
              "CDS_ITALIA_5Y", "SPREAD_BTP_BUND"],
    "indices": ["FTSE_MIB", "FTSE_MIB_DELTA", "DAX", "DAX_DELTA", "CAC40", "CAC40_DELTA",
                "EUROSTOXX50", "EUROSTOXX50_DELTA", "SP500", "SP500_DELTA", "NASDAQ",
                "NASDAQ_DELTA", "DJI", "DJI_DELTA"],
    "commodities": ["BRENT", "BRENT_DELTA", "WTI", "WTI_DELTA", "GOLD", "GOLD_DELTA",
                    "SILVER", "SILVER_DELTA", "NAT_GAS", "NAT_GAS_DELTA"],
    "volatility": ["VIX"],
    "macro": ["CPI_USA", "CPI_CORE", "PPI_USA", "HICP_EZ", "CPI_ITA", "PIL_USA", "PIL_EZ",
              "FED_RATE", "BCE_RATE"],
    "crypto": ["BTC_USD", "BTC_USD_DELTA", "ETH_USD", "ETH_USD_DELTA"],
}


def prev_business_day(d):
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def new_data(date_report, date_chiusura, date_str):
    data = {
        "meta": {
            "DATE_REPORT": date_report,
            "DATE_CHIUSURA": date_chiusura,
            "DATE_STR": date_str,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "pipeline_version": "3.1",
        },
        "headlines": [], "errors": [], "quality": {}, "context": {}, "_meta": {},
    }
    for c in CATEGORIES:
        data[c] = {}
        data["_meta"][c] = {}
    return data


def setv(data, cat, key, value, source, tier, as_of):
    data[cat][key] = value
    data["_meta"][cat][key] = {"source": source, "tier": tier, "as_of": as_of}


def fetch_url(url, timeout=20):
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def parse_ecb_cubes(content):
    """Ritorna [(date_iso, {ccy: rate})] in ordine dal piu' recente."""
    root = ET.fromstring(content.encode("utf-8"))
    ns = {"ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
    return [(c.get("time"), {x.get("currency"): float(x.get("rate")) for x in c})
            for c in root.findall(".//ecb:Cube/ecb:Cube", ns)]


def fetch_ecb_forex(data):
    # hist-90d contiene anche la seduta precedente -> delta T1; fallback sul daily.
    content = fetch_url("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml") \
        or fetch_url("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml")
    if not content:
        data["errors"].append("ECB XML: fetch fallito")
        data["quality"]["forex"] = "N/D"
        return
    try:
        cubes = parse_ecb_cubes(content)
        as_of, fx = cubes[0]
        prev = cubes[1][1] if len(cubes) > 1 else {}
        src = "ECB eurofxref XML"

        def put(key, val, pval, source):
            setv(data, "forex", key, val, source, "T1", as_of)
            if pval:
                setv(data, "forex", f"{key}_DELTA", round((val / pval - 1) * 100, 2), f"{source} (calc)", "T1", as_of)

        for ccy in ("USD", "JPY", "GBP", "CHF"):
            if ccy in fx:
                put(f"EUR_{ccy}", fx[ccy], prev.get(ccy), src)
        if "JPY" in fx and "USD" in fx:
            pj = round(prev["JPY"] / prev["USD"], 4) if "JPY" in prev and "USD" in prev else None
            put("USD_JPY", round(fx["JPY"] / fx["USD"], 4), pj, "ECB (calcolato)")
        data["forex"]["ECB_DATE"] = as_of
        data["quality"]["forex"] = "Alta"
        print(f"OK ECB XML - data: {as_of} | EUR/USD={fx.get('USD')}")
    except Exception as e:
        data["errors"].append(f"ECB XML parse error: {e}")
        data["quality"]["forex"] = "N/D"


def parse_fred_csv(text):
    """Ritorna lista [(date_iso, float)] delle osservazioni valide."""
    rows = []
    reader = csv.reader(io.StringIO(text))
    next(reader, None)
    for row in reader:
        if len(row) < 2:
            continue
        try:
            rows.append((row[0], float(row[1])))
        except ValueError:
            continue  # valori vuoti o '.' per festivita'
    return rows


def fetch_fred(data, cosd):
    ok = 0
    for series, (cat, key, dunit) in FRED_SERIES.items():
        text = fetch_url(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={cosd}")
        obs = parse_fred_csv(text) if text else []
        if not obs:
            data["errors"].append(f"FRED {series}: nessun dato")
            continue
        as_of, last = obs[-1]
        setv(data, cat, key, last, f"FRED {series}", "T1", as_of)
        if dunit and len(obs) >= 2:
            prev = obs[-2][1]
            if dunit == "bp":
                delta = round((last - prev) * 100, 1)
            else:
                delta = round((last / prev - 1) * 100, 2) if prev else None
            if delta is not None:
                setv(data, cat, f"{key}_DELTA", delta, f"FRED {series} (calc)", "T1", as_of)
        ok += 1
        time.sleep(0.2)
    print(f"OK FRED - {ok}/{len(FRED_SERIES)} serie")


def fetch_ansa(data):
    content = fetch_url("https://www.ansa.it/sito/notizie/economia/economia.shtml")
    if not content:
        data["errors"].append("ANSA: fetch fallito")
        return
    titles = re.findall(r"<h3[^>]*>\s*<a[^>]*>([^<]+)</a>", content)
    data["headlines"] = [t.strip() for t in titles[:8] if t.strip()]
    print(f"OK ANSA - {len(data['headlines'])} headlines")


def set_placeholders(data):
    for cat, keys in PLACEHOLDER_KEYS.items():
        for key in keys:
            data[cat].setdefault(key, "N/D")


def main(argv=None):
    today = date.today()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date-report", default=today.strftime("%d/%m/%Y"))
    ap.add_argument("--date-chiusura", default=prev_business_day(today).strftime("%d/%m/%Y"))
    ap.add_argument("--no-network", action="store_true", help="salta il fetch (solo struttura N/D)")
    args = ap.parse_args(argv)

    date_str = datetime.strptime(args.date_report, "%d/%m/%Y").strftime("%Y-%m-%d")
    data = new_data(args.date_report, args.date_chiusura, date_str)

    print(f"\n{'=' * 50}\nFETCH MARKET DATA - {args.date_report}\n{'=' * 50}\n")
    if not args.no_network:
        fetch_ecb_forex(data)
        cosd = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=21)).strftime("%Y-%m-%d")
        fetch_fred(data, cosd)
        fetch_ansa(data)
    set_placeholders(data)

    ensure_dirs()
    save_market_data(data)
    nd = sum(1 for c in CATEGORIES for v in data[c].values() if v == "N/D")
    tot = sum(len(data[c]) for c in CATEGORIES)
    print(f"\nOK market_data.json salvato: {MARKET_DATA_PATH}")
    print(f"Campi N/D: {nd}/{tot} -> integrare con merge_supplement.py")
    print(f"Errori: {len(data['errors'])}")
    for e in data["errors"]:
        print(f"  WARNING: {e}")


if __name__ == "__main__":
    main()
