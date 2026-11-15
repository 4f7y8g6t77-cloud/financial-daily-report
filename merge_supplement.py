#!/usr/bin/env python3
"""
merge_supplement.py - Layer 1b: integra market_data.json con dati supplementari v3.1

Il supplemento (default $FDR_WORK_DIR/supplement.json) contiene i dati che i fetcher
automatici non coprono, raccolti via Bigdata.com o altre fonti, sempre con fonte dichiarata:

{
  "data": {
    "bonds": {"BUND_10Y": {"value": 3.377, "source": "Reuters via Bigdata.com",
                           "tier": "T1-NEWS", "as_of": "2026-11-13"}}
  },
  "context": {"geo_driver": "...", "scenarios": [...], "central_banks": [...],
              "agenda": [...], "wm_recommendations": [...]}
}

Regole di merge (Protocollo Fonti):
  1. Campo N/D -> si prende il valore del supplemento.
  2. Entrambi presenti, as_of diverso -> vince la sessione piu' recente.
  3. Stessa sessione -> se divergenza > soglia A: flag amber con entrambi i valori, NO media,
     resta la fonte di tier piu' alto; altrimenti resta il tier piu' alto e si annota la conferma.
  4. Se un livello cambia fonte e il supplemento non fornisce il delta, il delta va a N/D
     (mai un delta di un'altra sessione).
  5. Spread BTP-Bund calcolato se BTP e Bund della stessa sessione sono disponibili.
  6. Flag amber classe B sulle variazioni giornaliere anomale.
  7. Scenari validati: somma = 100% o errore bloccante.
"""
import argparse
import json
import sys

from fdr_common import (CATEGORIES, SUPPLEMENT_PATH, THRESHOLD_A, THRESHOLD_B, TIER_RANK,
                        ContextError, is_nd, load_market_data, save_market_data, to_float,
                        validate_scenarios)

BP_KEYS = {"SPREAD_BTP_BUND", "CDS_ITALIA_5Y"}


def threshold_for(cat, key):
    if cat == "bonds" and key in BP_KEYS:
        return THRESHOLD_A["bonds_bp"]
    return THRESHOLD_A.get(cat)


def diverges(cat, key, a, b):
    fa, fb = to_float(a), to_float(b)
    th = threshold_for(cat, key)
    if fa is None or fb is None or th is None:
        return False
    mode, lim = th
    if mode == "abs":
        return abs(fa - fb) > lim + 1e-9
    base = abs(fa) if fa else abs(fb)
    return base > 0 and abs(fa - fb) / base * 100 > lim + 1e-9


def rank(t):
    return TIER_RANK.get(t, 9)


def merge(mkt, supp):
    errors = mkt.setdefault("errors", [])
    meta = mkt.setdefault("_meta", {})
    log = []
    supplied = {(c, k) for c, d in (supp.get("data") or {}).items() for k in d}
    replaced_levels = []

    for cat, fields in (supp.get("data") or {}).items():
        if cat not in CATEGORIES:
            errors.append(f"Supplemento: categoria sconosciuta '{cat}' ignorata")
            continue
        mkt.setdefault(cat, {})
        meta.setdefault(cat, {})
        for key, rec in fields.items():
            if not isinstance(rec, dict) or "value" not in rec:
                errors.append(f"Supplemento {cat}.{key}: formato non valido (serve value/source/tier/as_of)")
                continue
            new_m = {"source": rec.get("source", "N/D"), "tier": rec.get("tier", "T3"),
                     "as_of": rec.get("as_of", "")}
            if rec.get("note"):
                new_m["note"] = rec["note"]
            cur_v = mkt[cat].get(key)
            cur_m = meta[cat].get(key, {})

            if is_nd(cur_v):
                take = True
            elif new_m["as_of"] and cur_m.get("as_of") and new_m["as_of"] != cur_m["as_of"]:
                take = new_m["as_of"] > cur_m["as_of"]
                if take:
                    log.append(f"{cat}.{key}: sessione piu' recente {new_m['as_of']} "
                               f"({new_m['source']}) sostituisce {cur_m.get('as_of')} ({cur_m.get('source')})")
            else:
                if diverges(cat, key, cur_v, rec["value"]):
                    errors.append(
                        f"AMBER {cat}.{key}: divergenza oltre soglia A stessa sessione "
                        f"{cur_v} [{cur_m.get('source')} {cur_m.get('tier')}] vs "
                        f"{rec['value']} [{new_m['source']} {new_m['tier']}] - nessuna media")
                take = rank(new_m["tier"]) < rank(cur_m.get("tier"))
                if not take and not diverges(cat, key, cur_v, rec["value"]):
                    cur_m.setdefault("confirmed_by", []).append(new_m["source"])

            if take:
                if not is_nd(cur_v) and not key.endswith("_DELTA"):
                    replaced_levels.append((cat, key))
                mkt[cat][key] = rec["value"]
                meta[cat][key] = new_m

    # Regola 4: delta orfani
    for cat, key in replaced_levels:
        dkey = f"{key}_DELTA"
        if dkey in mkt[cat] and (cat, dkey) not in supplied:
            mkt[cat][dkey] = "N/D"
            meta[cat].pop(dkey, None)
            log.append(f"{cat}.{dkey}: azzerato a N/D (livello da altra sessione/fonte)")

    compute_spread(mkt, log)
    flag_anomalies(mkt)

    if supp.get("context"):
        ctx = mkt.setdefault("context", {})
        ctx.update(supp["context"])
    validate_scenarios(mkt.get("context", {}).get("scenarios"))
    return log


def compute_spread(mkt, log):
    bonds, meta = mkt["bonds"], mkt["_meta"].setdefault("bonds", {})
    if not is_nd(bonds.get("SPREAD_BTP_BUND")):
        return
    btp, bund = to_float(bonds.get("BTP_10Y")), to_float(bonds.get("BUND_10Y"))
    if btp is None or bund is None:
        return
    a1 = meta.get("BTP_10Y", {}).get("as_of")
    a2 = meta.get("BUND_10Y", {}).get("as_of")
    if a1 != a2:
        mkt["errors"].append(f"Spread BTP-Bund non calcolato: sessioni diverse (BTP {a1}, Bund {a2})")
        return
    worst = max((meta["BTP_10Y"].get("tier"), meta["BUND_10Y"].get("tier")), key=rank)
    bonds["SPREAD_BTP_BUND"] = round((btp - bund) * 100, 1)
    meta["SPREAD_BTP_BUND"] = {"source": "calcolato BTP-Bund", "tier": worst, "as_of": a1}
    log.append(f"bonds.SPREAD_BTP_BUND calcolato: {bonds['SPREAD_BTP_BUND']} bp")


def flag_anomalies(mkt):
    checks = [("indices", THRESHOLD_B["indices"]), ("commodities", THRESHOLD_B["commodities"]),
              ("forex", THRESHOLD_B["forex"])]
    for cat, lim in checks:
        for key, val in mkt.get(cat, {}).items():
            if key.endswith("_DELTA"):
                f = to_float(val)
                if f is not None and abs(f) > lim:
                    mkt["errors"].append(f"AMBER classe B: {cat}.{key} = {f:+.2f}% (soglia {lim}%)")
    for key, val in mkt.get("bonds", {}).items():
        if key.endswith("_DELTA"):
            f = to_float(val)
            if f is not None and abs(f) > THRESHOLD_B["bonds_bp"]:
                mkt["errors"].append(f"AMBER classe B: bonds.{key} = {f:+.0f} bp (soglia 15bp)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Integra market_data.json con un supplemento")
    ap.add_argument("supplement", nargs="?", default=SUPPLEMENT_PATH)
    args = ap.parse_args(argv)
    try:
        with open(args.supplement, "r", encoding="utf-8") as f:
            supp = json.load(f)
    except FileNotFoundError:
        print(f"Nessun supplemento in {args.supplement}: market_data.json invariato")
        return 0
    mkt = load_market_data()
    try:
        log = merge(mkt, supp)
    except ContextError as e:
        print(f"ERRORE contesto: {e}", file=sys.stderr)
        return 2
    save_market_data(mkt)
    for line in log:
        print(f"  {line}")
    nd = sum(1 for c in CATEGORIES for v in mkt.get(c, {}).values() if is_nd(v))
    tot = sum(len(mkt.get(c, {})) for c in CATEGORIES)
    print(f"OK merge supplemento: campi N/D residui {nd}/{tot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
