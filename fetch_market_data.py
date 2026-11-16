#!/usr/bin/env python3
"""
fetch_market_data.py - Layer 1 data fetcher v3.0
Output: /home/claude/market_data.json
"""
import json, re, time, xml.etree.ElementTree as ET
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
}

DATE_REPORT   = "DATA_REPORT_PLACEHOLDER"
DATE_CHIUSURA = "DATA_CHIUSURA_PLACEHOLDER"
DATE_STR      = "DATE_STR_PLACEHOLDER"
OUTPUT_PATH   = "/home/claude/market_data.json"

data = {
    "meta": {
        "DATE_REPORT": DATE_REPORT,
        "DATE_CHIUSURA": DATE_CHIUSURA,
        "DATE_STR": DATE_STR,
        "generated_at": datetime.now().isoformat(),
        "pipeline_version": "3.0",
    },
    "forex": {}, "indices": {}, "bonds": {}, "commodities": {},
    "volatility": {}, "macro": {}, "us_equity": {}, "mag7": {},
    "crypto": {}, "headlines": [], "errors": [], "quality": {},
}

def fetch_url(url, timeout=15):
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return None

def fetch_ecb_forex():
    url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
    content = fetch_url(url)
    if not content:
        data["errors"].append("ECB XML: fetch fallito")
        data["quality"]["forex"] = "N/D"
        return
    try:
        root = ET.fromstring(content.encode("utf-8"))
        ns = {"gesmes": "http://www.gesmes.org/xml/2002-08-01",
              "ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
        cube_time = root.find(".//ecb:Cube/ecb:Cube", ns)
        ecb_date = cube_time.get("time") if cube_time is not None else "N/D"
        fx = {c.get("currency"): float(c.get("rate")) for c in cube_time}
        data["forex"]["ECB_DATE"] = ecb_date
        data["forex"]["EUR_USD"]  = fx.get("USD")
        data["forex"]["EUR_JPY"]  = fx.get("JPY")
        data["forex"]["EUR_GBP"]  = fx.get("GBP")
        data["forex"]["EUR_CHF"]  = fx.get("CHF")
        if fx.get("JPY") and fx.get("USD"):
            data["forex"]["USD_JPY"] = round(fx["JPY"] / fx["USD"], 4)
        data["forex"]["_source"] = "ECB eurofxref XML"
        data["forex"]["_tier"]   = "T1"
        data["quality"]["forex"] = "Alta"
        print(f"OK ECB XML - data: {ecb_date} | EUR/USD={data['forex']['EUR_USD']}")
    except Exception as e:
        data["errors"].append(f"ECB XML parse error: {e}")
        data["quality"]["forex"] = "N/D"

def fetch_ecb_fx_delta():
    """Variazione % giornaliera dei cross EUR: ultime due date dello storico
    ECB a 90 giorni (T1). Calcolata solo se l'ultima data coincide con quella
    del file daily, cosi' delta e livello si riferiscono alla stessa fixing."""
    url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
    content = fetch_url(url, timeout=20)
    if not content:
        data["errors"].append("ECB hist-90d: fetch fallito, variazioni FX N/D")
        return
    try:
        root = ET.fromstring(content.encode("utf-8"))
        ns = {"ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
        days = sorted(root.findall(".//ecb:Cube/ecb:Cube[@time]", ns),
                      key=lambda c: c.get("time"), reverse=True)[:2]
        if len(days) < 2:
            raise ValueError("meno di due fixing nello storico")
        last, prev = ({c.get("currency"): float(c.get("rate")) for c in d} for d in days)
        last_date, prev_date = days[0].get("time"), days[1].get("time")
        if last_date != data["forex"].get("ECB_DATE"):
            data["errors"].append(f"ECB hist-90d ({last_date}) non allineato al daily "
                                  f"({data['forex'].get('ECB_DATE')}): variazioni FX N/D")
            return
        def pct(a, b): return round((a / b - 1) * 100, 2)
        for cur in ("USD", "JPY", "GBP", "CHF"):
            if cur in last and cur in prev:
                data["forex"][f"EUR_{cur}_DELTA"] = pct(last[cur], prev[cur])
        if all(k in d for d in (last, prev) for k in ("USD", "JPY")):
            data["forex"]["USD_JPY_DELTA"] = pct(last["JPY"] / last["USD"], prev["JPY"] / prev["USD"])
        data["forex"]["ECB_PREV_DATE"] = prev_date
        print(f"OK ECB hist-90d - variazioni {prev_date} -> {last_date}")
    except Exception as e:
        data["errors"].append(f"ECB hist-90d parse error: {e}")

def fetch_ansa():
    url = "https://www.ansa.it/sito/notizie/economia/economia.shtml"
    content = fetch_url(url)
    if not content:
        data["errors"].append("ANSA: fetch fallito")
        return
    try:
        titles = re.findall(r'<h3[^>]*>\s*<a[^>]*>([^<]+)</a>', content)
        data["headlines"] = [t.strip() for t in titles[:8] if t.strip()]
        print(f"OK ANSA - {len(data['headlines'])} headlines")
    except Exception as e:
        data["errors"].append(f"ANSA parse error: {e}")

def set_placeholders():
    for cat, keys in {
        "bonds": ["BUND_10Y","BTP_10Y","UST_2Y","UST_5Y","UST_10Y","UST_30Y","OAT_10Y","CDS_ITALIA_5Y","SPREAD_BTP_BUND"],
        "indices": ["FTSE_MIB","FTSE_MIB_DELTA","DAX","DAX_DELTA","CAC40","CAC40_DELTA","EUROSTOXX50","EUROSTOXX50_DELTA","SP500","SP500_DELTA","NASDAQ","NASDAQ_DELTA","DJI","DJI_DELTA"],
        "commodities": ["BRENT","BRENT_DELTA","WTI","WTI_DELTA","GOLD","GOLD_DELTA","SILVER","SILVER_DELTA","NAT_GAS","NAT_GAS_DELTA"],
        "volatility": ["VIX"],
        "macro": ["CPI_USA","CPI_CORE","PPI_USA","HICP_EZ","CPI_ITA","PIL_USA_Q1","PIL_EZ_Q1","FED_RATE","BCE_RATE"],
        "crypto": ["BTC_USD","BTC_DELTA","ETH_USD","ETH_DELTA"],
    }.items():
        if cat not in data: data[cat] = {}
        for key in keys:
            if key not in data[cat]: data[cat][key] = "N/D"

if __name__ == "__main__":
    print(f"\n{'='*50}\nFETCH MARKET DATA - {DATE_REPORT}\n{'='*50}\n")
    fetch_ecb_forex()
    time.sleep(1)
    if data["forex"].get("ECB_DATE"):
        fetch_ecb_fx_delta()
        time.sleep(1)
    fetch_ansa()
    set_placeholders()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nOK market_data.json salvato: {OUTPUT_PATH}")
    print(f"Errori: {len(data['errors'])}")
    for e in data["errors"]: print(f"  WARNING: {e}")
