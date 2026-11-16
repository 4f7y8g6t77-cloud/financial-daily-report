#!/usr/bin/env python3
"""
report_full_pipeline.py - PDF Report Finanziario v3.2
Input:  /home/claude/market_data.json   (schema: docs/market_data_schema.md)
Output: /home/claude/financial_daily_report_{DATE_STR}.pdf
        /mnt/user-data/outputs/financial_daily_report_{DATE_STR}.pdf

Tutte le chiavi aggiunte in v3.2 (summary, comments, *_DELTA, central_banks,
agenda, geo, scenarios, PIL_*_PERIOD) sono OPZIONALI: se mancano il PDF viene
generato comunque e la lacuna finisce nelle NOTE QUALITÀ DATI, senza
stampare contenuti statici scaduti.
"""
import json, os, re
from datetime import date
from xml.sax.saxutils import escape
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (HRFlowable, KeepTogether, Paragraph,
                                 SimpleDocTemplate, Spacer, Table, TableStyle)

# Palette skill v3.1 (invariata) + GREEN_TXT: il verde #1A8A4A ha contrasto
# 4,39:1 su bianco (< 4,5:1 WCAG AA); per il TESTO dei delta positivi si usa
# una variante piu' scura (6,49:1).
WHITE     = HexColor("#FFFFFF"); NAVY   = HexColor("#0B2545")
GOLD      = HexColor("#C9A84C"); AMBER  = HexColor("#E07B00")
AMBER_BG  = HexColor("#FFF8E1"); GREEN  = HexColor("#1A8A4A")
RED       = HexColor("#C0392B"); LGREY  = HexColor("#F5F7FA")
GREY      = HexColor("#2C3E50"); BLIGHT = HexColor("#E8F4FD")
BLUE      = HexColor("#1565C0"); GRID_C = HexColor("#CCCCCC")
GREEN_TXT = HexColor("#146C3A"); MUTED  = HexColor("#5D6D7E")

with open("/home/claude/market_data.json", "r", encoding="utf-8") as f:
    mkt = json.load(f)

meta  = mkt.get("meta", {}); forex = mkt.get("forex", {})
idx   = mkt.get("indices", {}); bonds = mkt.get("bonds", {})
comm  = mkt.get("commodities", {}); vol = mkt.get("volatility", {})
macro = mkt.get("macro", {}); errors = mkt.get("errors", [])
headlines = mkt.get("headlines", [])

DATE_REPORT   = meta.get("DATE_REPORT",   "N/D")
DATE_CHIUSURA = meta.get("DATE_CHIUSURA", "N/D")
DATE_STR      = meta.get("DATE_STR",      "2026-01-01")

PAGE_W = A4[0] - 3 * cm            # larghezza utile: tutte le tabelle a 18 cm

def ps(name, **kw): return ParagraphStyle(name, **kw)
SB  = ps("b",  fontName="Helvetica",         fontSize=8.5, textColor=GREY,  leading=12)
SW  = ps("w",  fontName="Helvetica-Bold",    fontSize=8.5, textColor=WHITE, leading=12)
SS  = ps("s",  fontName="Helvetica",         fontSize=7.5, textColor=GREY,  leading=10)
ST  = ps("t",  fontName="Helvetica-Bold",    fontSize=11,  textColor=NAVY,  leading=14)
SC  = ps("c",  fontName="Helvetica-Oblique", fontSize=7.5, textColor=GREY,  leading=10)
SBR = ps("br", parent=SB, alignment=TA_RIGHT)
SWR = ps("wr", parent=SW, alignment=TA_RIGHT)
SBLUF = ps("bluf", fontName="Helvetica", fontSize=9.5, textColor=GREY, leading=13.5)
SKL = ps("kl", fontName="Helvetica",      fontSize=7.5, textColor=MUTED, leading=9)
SKV = ps("kv", fontName="Helvetica-Bold", fontSize=12,  textColor=NAVY,  leading=15)
SKD = ps("kd", fontName="Helvetica-Bold", fontSize=8.5, textColor=GREY,  leading=11)

# ---------------------------------------------------------------------------
# Formato numeri: stile italiano (migliaia "." / decimali ",") per tutto il PDF.
# kind: idx (indici), px (prezzi commodity), fx, yield, pct, delta (variaz. %),
#       dbp (variaz. in bp), bp, pts (punti, es. VIX), dpts (variaz. in punti).
# Un input ambiguo (es. "$4.050": 4,05 o 4.050?) NON viene indovinato:
# resta invariato e finisce nelle NOTE QUALITÀ DATI.
# ---------------------------------------------------------------------------
QUALITY = []
_TOK = re.compile(r"\d[\d.,]*\d|\d")
_DOT_DECIMAL = {"fx", "yield", "pct", "delta", "dbp", "bp", "pts", "dpts"}
_SIGNED = {"delta", "dbp", "dpts"}
_DEFAULT_DEC = {"idx": 2, "px": 2, "fx": 4, "yield": 2, "pct": 1, "delta": 2,
                "dbp": 0, "bp": 0, "pts": 2, "dpts": 2}

def _it(n, dec):
    """Formatta un float in stile italiano: 6950.32 -> '6.950,32'."""
    out = f"{abs(n):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if round(n, dec) < 0 else "") + out

def _parse_tok(tok, kind):
    """Token numerico -> (valore, decimali), oppure None se ambiguo."""
    if "." in tok and "," in tok:
        dsep = "." if tok.rfind(".") > tok.rfind(",") else ","
        tsep = "," if dsep == "." else "."
        if tok.count(dsep) != 1: return None
        ip, fr = tok.split(dsep)
        return float(ip.replace(tsep, "") + "." + fr), len(fr)
    sep = "." if "." in tok else ("," if "," in tok else None)
    if sep is None: return float(tok), 0
    thousands = re.fullmatch(r"\d{1,3}(?:\%s\d{3})+" % sep, tok) is not None
    if tok.count(sep) > 1:                       # 1.234.567: migliaia certe
        return (float(tok.replace(sep, "")), 0) if thousands else None
    ip, fr = tok.split(sep)
    if thousands and kind not in _DOT_DECIMAL:
        if kind == "idx": return float(ip + fr), 0  # indici: 3 cifre = migliaia
        return None                              # px: "4.050" ambiguo
    return float(ip + "." + fr), len(fr)

def _missing(raw): return raw is None or raw == "N/D" or raw == ""

def fmt(raw, kind, unit=""):
    """Valore grezzo (str o numero) -> stringa formattata, 'N/D' se mancante."""
    if _missing(raw): return "N/D"
    if isinstance(raw, (int, float)):
        r = repr(raw)   # conserva la precisione della fonte (es. ECB 0.83559)
        if isinstance(raw, int): dec = _DEFAULT_DEC[kind] if kind in ("yield", "fx") else 0
        else: dec = len(r.split(".")[1]) if "." in r and "e" not in r else _DEFAULT_DEC[kind]
        out = _it(float(raw), dec)
        if kind in _SIGNED and raw > 0: out = "+" + out
        return out + unit
    s = str(raw).strip()
    toks = list(_TOK.finditer(s))
    if not toks: return s
    parsed = [_parse_tok(m.group(), kind) for m in toks]
    if any(p is None for p in parsed):
        QUALITY.append(f"Formato numerico ambiguo '{s}' ({kind}): lasciato invariato, verificare.")
        return s
    for m, (val, dec) in reversed(list(zip(toks, parsed))):
        s = s[:m.start()] + _it(val, dec) + s[m.end():]
    if kind in _SIGNED and s[0].isdigit() and parsed[0][0] != 0: s = "+" + s
    if unit and not s.endswith(unit.strip()): s += unit
    return s

def num_val(raw, kind):
    """Valore numerico (float, con segno) da un campo grezzo; None se mancante/ambiguo."""
    if isinstance(raw, (int, float)): return float(raw)
    if _missing(raw): return None
    s = str(raw).strip()
    m = _TOK.search(s)
    p = _parse_tok(m.group(), kind) if m else None
    if not p: return None
    return -p[0] if s[:m.start()].strip().endswith(("-", "−")) else p[0]

def v(d, k, kind=None, unit=""):
    val = d.get(k)
    if _missing(val): return "N/D"
    return fmt(val, kind, unit) if kind else str(val)

# ---------------------------------------------------------------------------
# Date: mesi italiani, filtro agenda/riunioni su DATE_STR
# ---------------------------------------------------------------------------
MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]

def _iso(s):
    try: return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError): return None

TODAY = _iso(DATE_STR)
if TODAY is None:
    QUALITY.append(f"DATE_STR non valida ('{DATE_STR}'): agenda e riunioni non filtrate per data.")

def date_it(d1, d2=None):
    """date(2026,12,8), date(2026,12,9) -> '8-9 dic 2026'."""
    if d2 and d2 != d1:
        if d2.month == d1.month: return f"{d1.day}-{d2.day} {MESI[d1.month-1]} {d1.year}"
        return f"{d1.day} {MESI[d1.month-1]} - {d2.day} {MESI[d2.month-1]} {d2.year}"
    return f"{d1.day} {MESI[d1.month-1]} {d1.year}"

def upcoming(d_end):
    return TODAY is None or d_end >= TODAY

# Calendario FOMC 2026 (Fed.gov T1, da skill v3.1). * = SEP + dot plot.
FOMC = [("2026-01-27", "2026-01-28", False), ("2026-03-17", "2026-03-18", True),
        ("2026-04-28", "2026-04-29", False), ("2026-06-16", "2026-06-17", True),
        ("2026-07-28", "2026-07-29", False), ("2026-09-15", "2026-09-16", True),
        ("2026-10-27", "2026-10-28", False), ("2026-12-08", "2026-12-09", True)]
FOMC = [(date.fromisoformat(a), date.fromisoformat(b), sep) for a, b, sep in FOMC]
FOMC_NEXT = [m for m in FOMC if upcoming(m[1])]

# ---------------------------------------------------------------------------
# Righe di mercato: valore + delta + soglie anomalia
# Soglie B (variazione giornaliera): indici 3%, commodity 5%, FX 2%, yield/spread 15bp
# Soglie di livello (skill v3.1): spread BTP-Bund > 100bp, VIX > 25
# ---------------------------------------------------------------------------
ANOMALIES = []   # (label, testo) -> riportate anche nella sintesi §00

def mrow(label, d, key, kind, unit="", dkind="delta", dunit="", d_thr=None,
         lvl_thr=None, src="", dkey=None):
    dkey = dkey or f"{key}_DELTA"
    if dkind == "delta" and not dunit: dunit = "%"   # delta numerici (es. FX da ECB) in %
    val_txt = v(d, key, kind, unit)
    dl_txt  = v(d, dkey, dkind, dunit)
    dl_num  = num_val(d.get(dkey), dkind)
    lv_num  = num_val(d.get(key), kind)
    d_anom  = d_thr is not None and dl_num is not None and abs(dl_num) > d_thr
    l_anom  = lvl_thr is not None and lv_num is not None and lv_num > lvl_thr
    if d_anom: ANOMALIES.append((label, f"{label} {dl_txt} (soglia {_it(d_thr, 0)}{dunit or '%'})"))
    if l_anom: ANOMALIES.append((label, f"{label} {val_txt} (soglia livello {_it(lvl_thr, 0)}{unit})"))
    return dict(label=label, val=val_txt, dl=dl_txt, dl_num=dl_num,
                d_anom=d_anom, l_anom=l_anom, src=src)

def delta_para(r):
    txt = escape(r["dl"]) + (" *" if r["d_anom"] else "")
    n = r["dl_num"]
    color = GREEN_TXT if n and n > 0 else (RED if n and n < 0 else GREY)
    st = ps("d", parent=SBR, fontName="Helvetica-Bold" if n else "Helvetica", textColor=color)
    return Paragraph(txt, st)

def grid(header, body, widths, num_cols=(), extra=()):
    """Tabella standard a larghezza piena. body: celle str o Paragraph."""
    scale = PAGE_W / sum(widths)
    rows = [[Paragraph(escape(str(c)), SWR if j in num_cols else SW) for j, c in enumerate(header)]]
    for row in body:
        rows.append([Paragraph(escape(c), SBR if j in num_cols else SB) if isinstance(c, str) else c
                     for j, c in enumerate(row)])
    sty = [("BACKGROUND", (0, 0), (-1, 0), NAVY),
           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
           ("GRID", (0, 0), (-1, -1), 0.3, GRID_C),
           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
           ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    return Table(rows, colWidths=[w * scale for w in widths],
                 style=TableStyle(sty + list(extra)), repeatRows=1)

def market_table(rows, first_col, val_col):
    """Strumento | Valore | Delta | Fonte. La colonna Delta sparisce se e' tutta N/D."""
    has_delta = any(r["dl"] != "N/D" for r in rows)
    extra, body = [], []
    for i, r in enumerate(rows, start=1):
        val = escape(r["val"]) + (" *" if r["l_anom"] else "")
        cells = [r["label"], Paragraph(val, SBR)]
        if r["l_anom"]: extra.append(("BACKGROUND", (1, i), (1, i), AMBER_BG))
        if has_delta:
            cells.append(delta_para(r))
            if r["d_anom"]: extra.append(("BACKGROUND", (2, i), (2, i), AMBER_BG))
        cells.append(r["src"])
        body.append(cells)
    if has_delta:
        hdr, widths, nc = [first_col, val_col, "Var.", "Fonte (Tier)"], [5.4, 3.4, 3.0, 6.2], (1, 2)
    else:
        hdr, widths, nc = [first_col, val_col, "Fonte (Tier)"], [5.4, 3.4, 9.2], (1,)
    out = [grid(hdr, body, widths, nc, extra)]
    if any(r["d_anom"] or r["l_anom"] for r in rows):
        out.append(Paragraph("* oltre soglia di anomalia (evidenziato in ambra)", SS))
    return out

# ---------------------------------------------------------------------------
# Box: commento di sezione (skill v3.1), sintesi, anomalie
# ---------------------------------------------------------------------------
COMMENTS = mkt.get("comments", {}) or {}
MISSING_COMMENTS = []

def boxed(flowables, bg, border, left_only=False):
    t = Table([[flowables]], colWidths=[PAGE_W])
    sty = [("BACKGROUND", (0, 0), (-1, -1), bg),
           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    sty.append(("LINEBEFORE", (0, 0), (0, -1), 3, border) if left_only
               else ("BOX", (0, 0), (-1, -1), 0.8, border))
    t.setStyle(TableStyle(sty))
    return t

def comment_box(num):
    text = COMMENTS.get(num)
    if not text:
        MISSING_COMMENTS.append(num); return []
    return [Spacer(1, 4), boxed(Paragraph("<b>[COMMENTO]</b> " + escape(str(text)), SC), BLIGHT, BLUE)]

def sec(title, num):
    hr = HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=4)
    hr._sec_start = True   # marcatore: inizio sezione, usato da keep_sections()
    return [hr, Paragraph(f"<b>{num} · {escape(title)}</b>", ST), Spacer(1, 4)]

def keep_sections(flows):
    """Ogni sezione (titolo + tabella + note) resta su una pagina."""
    out, cur = [], []
    for fl in flows:
        if getattr(fl, "_sec_start", False) and cur:
            out.append(KeepTogether(cur)); cur = []
        cur.append(fl)
    if cur: out.append(KeepTogether(cur))
    return out

def hdr_footer(canvas, doc):
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(NAVY); canvas.rect(0, h-1.5*cm, w, 1.5*cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE); canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(1.5*cm, h-1.0*cm, "FINANCIAL DAILY REPORT  di Ettore Turchet")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w-1.5*cm, h-1.0*cm, f"Chiusura: {DATE_CHIUSURA}  |  Report: {DATE_REPORT}")
    canvas.setStrokeColor(GOLD); canvas.setLineWidth(1.5)
    canvas.line(1.5*cm, h-1.55*cm, w-1.5*cm, h-1.55*cm)
    canvas.setFont("Helvetica", 7); canvas.setFillColor(GREY)
    canvas.drawString(1.5*cm, 0.7*cm, "Report finanziario a uso interno - dati da fonti pubbliche T1/T2")
    canvas.drawRightString(w-1.5*cm, 0.7*cm, f"Pag. {doc.page}")
    canvas.restoreState()

# ===========================================================================
# DATI DELLE SEZIONI (calcolati prima: la sintesi §00 li riassume)
# ===========================================================================
EQ = [mrow("FTSE MIB", idx, "FTSE_MIB", "idx", d_thr=3, src="MilanoFinanza (T2)"),
      mrow("DAX", idx, "DAX", "idx", d_thr=3, src="MilanoFinanza (T2)"),
      mrow("CAC 40", idx, "CAC40", "idx", d_thr=3, src="MilanoFinanza (T2)"),
      mrow("EuroStoxx50", idx, "EUROSTOXX50", "idx", d_thr=3, src="MilanoFinanza (T2)"),
      mrow("S&P 500", idx, "SP500", "idx", d_thr=3, src="CNBC (T2)"),
      mrow("Nasdaq", idx, "NASDAQ", "idx", d_thr=3, src="CNBC (T2)"),
      mrow("Dow Jones", idx, "DJI", "idx", d_thr=3, src="CNBC (T2)")]

BD = dict(dkind="dbp", dunit=" bp", d_thr=15)
BOND = [mrow("BTP 10Y", bonds, "BTP_10Y", "yield", "%", src="MilanoFinanza (T2)", **BD),
        mrow("Bund 10Y", bonds, "BUND_10Y", "yield", "%", src="web_search (T2)", **BD),
        mrow("Spread BTP-Bund", bonds, "SPREAD_BTP_BUND", "bp", " bp", lvl_thr=100,
             src="calcolato", **BD),
        mrow("OAT 10Y", bonds, "OAT_10Y", "yield", "%", src="WGB (T2)", **BD),
        mrow("UST 2Y", bonds, "UST_2Y", "yield", "%", src="CNBC (T2)", **BD),
        mrow("UST 5Y", bonds, "UST_5Y", "yield", "%", src="CNBC (T2)", **BD),
        mrow("UST 10Y", bonds, "UST_10Y", "yield", "%", src="CNBC (T2)", **BD),
        mrow("UST 30Y", bonds, "UST_30Y", "yield", "%", src="CNBC (T2)", **BD)]

FXD = dict(d_thr=2, src="ECB eurofxref (T1)")
FX = [mrow("EUR/USD", forex, "EUR_USD", "fx", **FXD),
      mrow("EUR/JPY", forex, "EUR_JPY", "fx", **FXD),
      mrow("EUR/GBP", forex, "EUR_GBP", "fx", **FXD),
      mrow("EUR/CHF", forex, "EUR_CHF", "fx", **FXD),
      mrow("USD/JPY", forex, "USD_JPY", "fx", d_thr=2, src="ECB, calcolato (T1)")]

CM = [mrow("Brent", comm, "BRENT", "px", d_thr=5, src="CNBC (T2)"),
      mrow("WTI", comm, "WTI", "px", d_thr=5, src="CNBC (T2)"),
      mrow("Natural Gas", comm, "NAT_GAS", "px", d_thr=5, src="CNBC (T2)"),
      mrow("Gold", comm, "GOLD", "px", d_thr=5, src="CNBC (T2)"),
      mrow("Silver", comm, "SILVER", "px", d_thr=5, src="CNBC (T2)")]

CRED = [mrow("VIX", vol, "VIX", "pts", dkind="dpts", lvl_thr=25, src="CBOE (T1)"),
        dict(label="iTraxx Europe", val="N/D", dl="N/D", dl_num=None, d_anom=False,
             l_anom=False, src="IHS Markit (abbonamento)"),
        mrow("CDS Italia 5Y", bonds, "CDS_ITALIA_5Y", "bp", " bp", **BD, src="WGB (T2)")]

def kpi(label, r):
    n = r["dl_num"]
    color = GREEN_TXT if n and n > 0 else (RED if n and n < 0 else MUTED)
    dl = "&nbsp;" if r["dl"] == "N/D" else escape(r["dl"])
    return [Paragraph(escape(label), SKL), Paragraph(escape(r["val"]), SKV),
            Paragraph(dl, ps("kdc", parent=SKD, textColor=color))]

# ===========================================================================
# STORY
# ===========================================================================
story = []

# --- §00 SINTESI ESECUTIVA -------------------------------------------------
story += sec("SINTESI ESECUTIVA", "00")
kp = [("FTSE MIB", EQ[0]), ("Spread BTP-Bund", BOND[2]), ("EUR/USD", FX[0]),
      ("Brent", CM[0]), ("VIX", CRED[0])]
kt = Table([[kpi(l, r) for l, r in kp]], colWidths=[PAGE_W / len(kp)] * len(kp))
kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LGREY),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEAFTER", (0, 0), (-2, -1), 0.5, WHITE),
                        ("LINEABOVE", (0, 0), (-1, 0), 2, NAVY),
                        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
story += [kt, Spacer(1, 6)]
summary = mkt.get("summary")
if summary:
    story.append(Paragraph("<b>BLUF</b> — " + escape(str(summary)), SBLUF))
else:
    story.append(Paragraph("<i>Sintesi non fornita (chiave 'summary' assente in market_data.json).</i>", SS))
    QUALITY.append("Sintesi esecutiva mancante: chiave 'summary' non presente.")
story.append(Spacer(1, 6))
if ANOMALIES:
    txt = "<b>SEGNALI OLTRE SOGLIA</b> — " + "; ".join(escape(t) for _, t in ANOMALIES)
else:
    txt = "<b>SEGNALI OLTRE SOGLIA</b> — nessuno tra i dati disponibili."
story += [boxed(Paragraph(txt, SB), AMBER_BG if ANOMALIES else LGREY,
                AMBER if ANOMALIES else GRID_C, left_only=True), Spacer(1, 10)]

# --- §01-04 mercati --------------------------------------------------------
story += sec("PIAZZA AFFARI", "01")
story += market_table(EQ, "Indice", "Chiusura") + comment_box("01") + [Spacer(1, 10)]

story += sec("OBBLIGAZIONARIO & SPREAD", "02")
story += market_table(BOND, "Strumento", "Rendimento") + comment_box("02") + [Spacer(1, 10)]

story += sec("FOREX", "03")
story += market_table(FX, "Cross", "Tasso")
prev = forex.get("ECB_PREV_DATE")
story.append(Paragraph(f"Riferimento ECB: {escape(str(forex.get('ECB_DATE', 'N/D')))}"
                       + (f" (variazione vs {escape(str(prev))})" if prev else ""), SS))
story += comment_box("03") + [Spacer(1, 10)]

story += sec("ENERGIA — DRIVER DOMINANTE", "04")
story += market_table(CM, "Commodity", "Prezzo") + comment_box("04") + [Spacer(1, 10)]

# --- §05 macro -------------------------------------------------------------
story += sec("MACRO & INFLAZIONE", "05")
def mlabel(base, key):
    p = macro.get(key)
    return f"{base} ({p})" if p else f"{base} (ultimo dato)"
story.append(grid(["Indicatore", "Valore", "Fonte (Tier)"], [
    ["CPI USA (YoY)", v(macro, "CPI_USA", "pct"), "BLS (T1)"],
    ["Core CPI USA (YoY)", v(macro, "CPI_CORE", "pct"), "BLS (T1)"],
    ["PPI USA (YoY)", v(macro, "PPI_USA", "pct"), "BLS (T1)"],
    ["HICP Eurozona", v(macro, "HICP_EZ", "pct"), "Eurostat (T1)"],
    ["CPI Italia", v(macro, "CPI_ITA", "pct"), "ISTAT (T1)"],
    [mlabel("PIL USA", "PIL_USA_PERIOD"), v(macro, "PIL_USA_Q1", "pct"), "BEA (T1)"],
    [mlabel("PIL Eurozona", "PIL_EZ_PERIOD"), v(macro, "PIL_EZ_Q1", "pct"), "Eurostat (T1)"],
], [8.6, 3.4, 6.0], num_cols=(1,)))
story += comment_box("05") + [Spacer(1, 10)]

# --- §06 banche centrali ---------------------------------------------------
story += sec("BANCHE CENTRALI", "06")
cb = mkt.get("central_banks")
if cb:
    cb_rows = [[str(b.get("bank", "N/D")), fmt(b.get("rate"), "pct"), str(b.get("bias", "N/D")),
                str(b.get("next", "N/D")), str(b.get("source", "N/D"))] for b in cb]
else:
    nxt = (date_it(FOMC_NEXT[0][0], FOMC_NEXT[0][1]) + ("*" if FOMC_NEXT[0][2] else "")) if FOMC_NEXT else "N/D"
    cb_rows = [["Fed", v(macro, "FED_RATE", "pct"), "N/D", nxt, "Fed.gov (T1)"],
               ["BCE", v(macro, "BCE_RATE", "pct"), "N/D", "N/D", "ECB (T1)"]]
    QUALITY.append("Banche centrali: chiave 'central_banks' assente; bias e riunione BCE N/D, "
                   "prossimo FOMC dal calendario 2026 interno.")
story.append(grid(["Banca", "Tasso", "Bias", "Prossima riunione", "Fonte (Tier)"],
                  cb_rows, [3.0, 3.2, 2.6, 5.0, 4.2], num_cols=(1,)))
story.append(Paragraph("* = riunione con SEP e dot plot", SS))
story += comment_box("06") + [Spacer(1, 10)]

# --- §07 credito & volatilità --------------------------------------------
story += sec("CREDITO & VOLATILITÀ", "07")
story += market_table(CRED, "Indicatore", "Livello")
story.append(Paragraph("iTraxx: N/D — abbonamento IHS Markit/ICE richiesto; "
                       "ICE BofA HY OAS non è un proxy equivalente.", SS))
story += comment_box("07") + [Spacer(1, 10)]

# --- §08 geopolitica -------------------------------------------------------
story += sec("GEOPOLITICA", "08")
geo = mkt.get("geo") or {}
if geo.get("driver"):
    story.append(Paragraph("<b>Driver:</b> " + escape(str(geo["driver"])), SB))
else:
    QUALITY.append("Geopolitica: chiave 'geo.driver' assente, driver non indicato.")
for it in geo.get("items", []):
    story.append(Paragraph("• " + escape(str(it)), SB))
story.append(Spacer(1, 4))
story.append(Paragraph("<b>Headline ANSA Economia</b> (non filtrate per tema)", SS))
for hl in (headlines[:5] if headlines else ["N/D - fetch ANSA fallito"]):
    story.append(Paragraph("- " + escape(str(hl)), SS))
story += comment_box("08") + [Spacer(1, 10)]

# --- §09 scenari -----------------------------------------------------------
story += sec("STRESS-TEST — SCENARI A/B/C", "09")
bf = num_val(comm.get("BRENT"), "px")
auto_a = f"<${_it(bf * 0.87, 1)}" if bf else "N/D"
scen = mkt.get("scenarios")
if not scen:
    QUALITY.append("Scenari: chiave 'scenarios' assente, usati i valori di default dello script "
                   "(Hormuz, A40/B50/C10): verificarne l'attualità.")
    scen = [{"name": "A - De-escalation Hormuz", "prob": 40, "condition": "Brent -13% max in 30gg"},
            {"name": "B - Stallo / status quo", "prob": 50, "target": "Laterale", "condition": "Brent range +-5%"},
            {"name": "C - Escalation (new shock)", "prob": 10, "target": ">$140", "condition": "Trigger: attacco Saudi/UAE"}]
s_rows, tot = [], 0.0
for i, s in enumerate(scen):
    p = num_val(s.get("prob"), "pct")
    tot += p or 0
    tgt = s.get("target") or (auto_a if i == 0 else "N/D")
    s_rows.append([str(s.get("name", "N/D")), f"{_it(p, 0)}%" if p is not None else "N/D",
                   str(tgt), str(s.get("condition", ""))])
s_rows.append(["Black Swan", "n.q.", "N/D", "Coda non quantificata, esclusa dalla somma"])
story.append(grid(["Scenario", "Prob.", "Target Brent", "Condizione"], s_rows,
                  [5.2, 1.8, 2.8, 8.2], num_cols=(1,)))
if abs(tot - 100) < 0.01:
    note = ("Probabilità: stima qualitativa esperta. Non derivata da modello quantitativo formale. "
            "Somma = 100% per costruzione. Black Swan (<5%) non incluso — corretto per definizione.")
    story.append(Paragraph(note, SS))
else:
    story.append(Paragraph(f"<b>ATTENZIONE: somma probabilità = {_it(tot, 0)}% (attesa 100%).</b>",
                           ps("sw", parent=SS, textColor=RED)))
    QUALITY.append(f"Scenari: somma probabilità {_it(tot, 0)}% invece di 100%.")
story.append(Spacer(1, 10))

# --- §10 agenda ------------------------------------------------------------
story += sec("AGENDA MACRO", "10")
ag = []
for e in mkt.get("agenda", []) or []:
    d1, d2 = _iso(e.get("date")), _iso(e.get("date_end")) or _iso(e.get("date"))
    if d1 and upcoming(d2):
        ag.append((d1, d2, str(e.get("event", "")), str(e.get("area", "")), str(e.get("note", ""))))
have_fomc = {a[0] for a in ag if "FOMC" in a[2].upper()}
for d1, d2, sep_ in FOMC_NEXT[:3]:
    if d1 not in have_fomc:
        ag.append((d1, d2, "FOMC", "USA", "SEP + dot plot" if sep_ else "Riunione standard"))
if not FOMC_NEXT:
    QUALITY.append("Calendario FOMC interno esaurito: inserire le date dell'anno successivo.")
if not mkt.get("agenda"):
    QUALITY.append("Agenda: chiave 'agenda' assente, mostrate solo le prossime riunioni FOMC.")
ag.sort(key=lambda a: a[0])
story.append(grid(["Data", "Evento", "Area", "Nota"],
                  [[date_it(a[0], a[1]), a[2], a[3], a[4]] for a in ag] or [["N/D", "", "", ""]],
                  [3.6, 4.6, 1.8, 8.0]))

# --- note qualita' ---------------------------------------------------------
if MISSING_COMMENTS:
    QUALITY.append("Commenti di sezione mancanti (chiave 'comments'): " + ", ".join(MISSING_COMMENTS) + ".")
errors = list(errors) + QUALITY
if errors:
    hr = HRFlowable(width="100%", thickness=0.5, color=AMBER, spaceBefore=12)
    hr._sec_start = True
    story.append(hr)
    story.append(Paragraph("<b>NOTE QUALITÀ DATI</b>",
                           ps("nb", fontName="Helvetica-Bold", fontSize=8.5, textColor=NAVY, leading=12)))
    for err in errors:
        story.append(Paragraph("WARNING: " + escape(str(err)), SS))

import shutil
_pdf = f"/home/claude/financial_daily_report_{DATE_STR}.pdf"
_out = f"/mnt/user-data/outputs/financial_daily_report_{DATE_STR}.pdf"
doc = SimpleDocTemplate(_pdf, pagesize=A4,
    leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=2.0*cm, bottomMargin=1.8*cm)
doc.build(keep_sections(story), onFirstPage=hdr_footer, onLaterPages=hdr_footer)
print(f"OK PDF: {_pdf}")
shutil.copy2(_pdf, _out)
print(f"OK PDF: {_out}")
