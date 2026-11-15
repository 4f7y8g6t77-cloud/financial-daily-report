#!/usr/bin/env python3
"""
fdr_common.py - Utility condivise della pipeline Financial Daily Report v3.1

- Percorsi configurabili via env (FDR_WORK_DIR, FDR_OUTPUT_DIR), cartelle create se mancanti.
- Lettura market_data.json, accesso a valori e metadati di fonte (source/tier/as_of).
- Escape testo per i Paragraph reportlab (&, <, >).
- Validazione scenari (somma = 100%) e contesto narrativo (agenda, banche centrali, geopolitica).
"""
import json
import os
import shutil
from xml.sax.saxutils import escape as _xml_escape

ND = "N/D"

WORK_DIR = os.environ.get("FDR_WORK_DIR", "/home/claude")
OUTPUT_DIR = os.environ.get("FDR_OUTPUT_DIR", "/mnt/user-data/outputs")
MARKET_DATA_PATH = os.path.join(WORK_DIR, "market_data.json")
SUPPLEMENT_PATH = os.path.join(WORK_DIR, "supplement.json")

CATEGORIES = ("forex", "indices", "bonds", "commodities", "volatility", "macro", "crypto")

# Soglie classe A (concordanza fonti, stessa sessione). "rel" = % relativa, "abs" = assoluta.
THRESHOLD_A = {
    "forex": ("rel", 0.5),
    "indices": ("rel", 1.0),
    "commodities": ("rel", 5.0),
    "volatility": ("rel", 1.0),
    "crypto": ("rel", 1.0),
    "bonds": ("abs", 0.03),      # yield in punti percentuali: 3bp
    "bonds_bp": ("abs", 5.0),    # spread/CDS in bp: 5bp
    "macro": ("abs", 0.05),
}

# Soglie classe B (anomalia variazione giornaliera) per flag amber.
THRESHOLD_B = {"indices": 3.0, "commodities": 5.0, "forex": 2.0, "bonds_bp": 15.0}

TIER_RANK = {"T1": 0, "T1-D": 1, "T1-NEWS": 2, "T2": 3, "T3": 4}


def ensure_dirs():
    for d in (WORK_DIR, OUTPUT_DIR):
        os.makedirs(d, exist_ok=True)


def work_path(name):
    return os.path.join(WORK_DIR, name)


def publish(src_path):
    """Copia un file generato nella cartella di output e ne restituisce il percorso."""
    ensure_dirs()
    dst = os.path.join(OUTPUT_DIR, os.path.basename(src_path))
    if os.path.abspath(dst) != os.path.abspath(src_path):
        shutil.copy2(src_path, dst)
    return dst


def load_market_data(path=None):
    with open(path or MARKET_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_market_data(data, path=None):
    ensure_dirs()
    with open(path or MARKET_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_nd(val):
    return val is None or (isinstance(val, str) and val.strip().upper() in ("N/D", "", "N/A"))


def to_float(val):
    """Converte valori tipo '5.10%', '$95.84', '+0.4', '103bp' in float; None se non numerico."""
    if is_nd(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    for tok in ("%", "$", "bp", "+", " "):
        s = s.replace(tok, "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def esc(text):
    """Escape per reportlab Paragraph: evita 'S&P' -> 'S&P;' e tag spuri."""
    return _xml_escape(str(text))


def fmt(d, key, pattern=None):
    """Valore formattato o 'N/D'. pattern es. '{:.2f}%'."""
    val = d.get(key)
    if is_nd(val):
        return ND
    if pattern:
        f = to_float(val)
        if f is not None:
            return pattern.format(f)
    return str(val)


def fmt_delta(d, key, unit="%"):
    f = to_float(d.get(key))
    if f is None:
        return ND
    if unit == "bp":
        return f"{f:+.0f} bp"
    return f"{f:+.2f}%"


def src(mkt, cat, key):
    """(fonte, tier, as_of) dai metadati; ('N/D','—','') se assenti."""
    m = mkt.get("_meta", {}).get(cat, {}).get(key, {})
    return m.get("source", ND), m.get("tier", "—"), m.get("as_of", "")


def src_label(mkt, cat, key):
    s, _, as_of = src(mkt, cat, key)
    return f"{s} ({as_of})" if as_of and s != ND else s


def tier(mkt, cat, key):
    return src(mkt, cat, key)[1]


# ---------------------------------------------------------------- contesto narrativo
class ContextError(ValueError):
    pass


def validate_scenarios(scenarios):
    """Gli scenari A/B/C devono sommare a 100%. Black Swan escluso (prob=None)."""
    if not scenarios:
        return
    total = 0.0
    for sc in scenarios:
        p = sc.get("prob")
        if p is None:
            continue
        if not isinstance(p, (int, float)) or p < 0:
            raise ContextError(f"Probabilita' non valida per scenario {sc.get('name')}: {p!r}")
        total += p
    if abs(total - 100.0) > 1e-6:
        raise ContextError(f"Scenari: somma probabilita' = {total:g}% (attesa 100%)")


def get_context(mkt):
    ctx = mkt.get("context", {}) or {}
    validate_scenarios(ctx.get("scenarios"))
    return ctx


def headlines_of(mkt):
    return mkt.get("headlines") or []
