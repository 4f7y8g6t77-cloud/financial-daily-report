#!/usr/bin/env python3
"""
report_full_pipeline.py - PDF Report Finanziario v3.0
Input:  /home/claude/market_data.json
Output: /home/claude/financial_daily_report_{DATE_STR}.pdf
        /mnt/user-data/outputs/financial_daily_report_{DATE_STR}.pdf
"""
import json, os, re
from xml.sax.saxutils import escape
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (HRFlowable, KeepTogether, Paragraph,
                                 SimpleDocTemplate, Spacer, Table, TableStyle)

WHITE     = HexColor("#FFFFFF"); NAVY   = HexColor("#0B2545")
GOLD      = HexColor("#C9A84C"); AMBER  = HexColor("#E07B00")
AMBER_BG  = HexColor("#FFF8E1"); GREEN  = HexColor("#1A8A4A")
RED       = HexColor("#C0392B"); LGREY  = HexColor("#F5F7FA")
GREY      = HexColor("#2C3E50"); BLIGHT = HexColor("#E8F4FD")

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

def ps(name, **kw): return ParagraphStyle(name, **kw)
SB = ps("b", fontName="Helvetica",      fontSize=8.5, textColor=GREY,  leading=12)
SW = ps("w", fontName="Helvetica-Bold", fontSize=8.5, textColor=WHITE, leading=12)
SS = ps("s", fontName="Helvetica",      fontSize=7.5, textColor=GREY,  leading=10)
ST = ps("t", fontName="Helvetica-Bold", fontSize=11,  textColor=NAVY,  leading=14)
SG = ps("g", fontName="Helvetica-Bold", fontSize=8.5, textColor=GREEN, leading=12)
SR = ps("r", fontName="Helvetica-Bold", fontSize=8.5, textColor=RED,   leading=12)
SA = ps("a", fontName="Helvetica-Bold", fontSize=8.5, textColor=AMBER, leading=12)
SBR = ps("br", parent=SB, alignment=TA_RIGHT)
SWR = ps("wr", parent=SW, alignment=TA_RIGHT)

# ---------------------------------------------------------------------------
# Formato numeri: stile italiano (migliaia "." / decimali ",") per tutto il PDF.
# kind: idx (indici), px (prezzi commodity), fx, yield, pct, delta, bp.
# Un input ambiguo (es. "$4.050": 4,05 o 4.050?) NON viene indovinato:
# resta invariato e finisce nelle NOTE QUALITA' DATI.
# ---------------------------------------------------------------------------
QUALITY = []
_TOK = re.compile(r"\d[\d.,]*\d|\d")
_DOT_DECIMAL = {"fx", "yield", "pct", "delta", "bp"}
_DEFAULT_DEC = {"idx": 2, "px": 2, "fx": 4, "yield": 2, "pct": 1, "delta": 2, "bp": 0}

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

def fmt(raw, kind, unit=""):
    """Valore grezzo (str o numero) -> stringa formattata, 'N/D' se mancante."""
    if raw is None or raw == "N/D" or raw == "": return "N/D"
    if isinstance(raw, (int, float)):
        r = repr(raw)   # conserva la precisione della fonte (es. ECB 0.83559)
        if isinstance(raw, int): dec = _DEFAULT_DEC[kind] if kind in ("yield", "fx") else 0
        else: dec = len(r.split(".")[1]) if "." in r and "e" not in r else _DEFAULT_DEC[kind]
        out = _it(float(raw), dec)
        if kind == "delta" and raw > 0: out = "+" + out
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
    if kind == "delta" and s[0].isdigit() and parsed[0][0] != 0: s = "+" + s
    if unit and not s.endswith(unit.strip()): s += unit
    return s

def num_val(raw, kind):
    """Valore numerico (float) da un campo grezzo, None se mancante/ambiguo."""
    if isinstance(raw, (int, float)): return float(raw)
    m = _TOK.search(str(raw or ""))
    p = _parse_tok(m.group(), kind) if m else None
    return p[0] if p else None

def v(d, k, kind=None, unit=""):
    val = d.get(k)
    if val is None or val == "N/D": return "N/D"
    return fmt(val, kind, unit) if kind else str(val)

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

def sec(title, num):
    hr = HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=4)
    hr._sec_start = True   # marcatore: inizio sezione, usato da keep_sections()
    return [hr,
            Paragraph(f"<b>{num} - {title}</b>", ST), Spacer(1, 4)]

def tbl(rows, widths, hdr=None, num_cols=()):
    """num_cols: indici delle colonne numeriche, allineate a destra."""
    tbl_rows = []
    if hdr: tbl_rows.append([Paragraph(escape(str(c)), SWR if j in num_cols else SW)
                             for j, c in enumerate(hdr)])
    for row in rows:
        tbl_rows.append([Paragraph(escape(c), SBR if j in num_cols else SB)
                         if isinstance(c, str) else c for j, c in enumerate(row)])
    sty = [("BACKGROUND",(0,0),(-1,0),NAVY) if hdr else ("BACKGROUND",(0,0),(-1,-1),WHITE),
           ("ROWBACKGROUNDS",(0,1 if hdr else 0),(-1,-1),[WHITE,LGREY]),
           ("GRID",(0,0),(-1,-1),0.3,HexColor("#CCCCCC")),
           ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4),
           ("LEFTPADDING",(0,0),(-1,-1),6), ("RIGHTPADDING",(0,0),(-1,-1),6),
           ("WORDWRAP",(0,0),(-1,-1),"LTR")]
    return Table(tbl_rows, colWidths=widths, style=TableStyle(sty), repeatRows=1 if hdr else 0)

def keep_sections(flows):
    """Raggruppa ogni sezione (titolo + tabella + note) in un KeepTogether:
    niente titoli orfani a fondo pagina."""
    out, cur = [], []
    for fl in flows:
        if getattr(fl, "_sec_start", False) and cur:
            out.append(KeepTogether(cur)); cur = []
        cur.append(fl)
    if cur: out.append(KeepTogether(cur))
    return out

story = []

story += sec("PIAZZA AFFARI", "01")
story.append(tbl([
    ["FTSE MIB",v(idx,"FTSE_MIB","idx"),v(idx,"FTSE_MIB_DELTA","delta"),"MilanoFinanza","T2"],
    ["DAX",v(idx,"DAX","idx"),v(idx,"DAX_DELTA","delta"),"MilanoFinanza","T2"],
    ["CAC 40",v(idx,"CAC40","idx"),v(idx,"CAC40_DELTA","delta"),"MilanoFinanza","T2"],
    ["EuroStoxx50",v(idx,"EUROSTOXX50","idx"),v(idx,"EUROSTOXX50_DELTA","delta"),"MilanoFinanza","T2"],
    ["S&P 500",v(idx,"SP500","idx"),v(idx,"SP500_DELTA","delta"),"CNBC","T2"],
    ["Nasdaq",v(idx,"NASDAQ","idx"),v(idx,"NASDAQ_DELTA","delta"),"CNBC","T2"],
    ["Dow Jones",v(idx,"DJI","idx"),v(idx,"DJI_DELTA","delta"),"CNBC","T2"],
], [5*cm,3*cm,3*cm,4.5*cm,1.5*cm], hdr=["Indice","Chiusura","Delta%","Fonte","Tier"], num_cols=(1,2)))
story.append(Spacer(1,8))

story += sec("OBBLIGAZIONARIO & SPREAD", "02")
story.append(tbl([
    ["BTP 10Y",v(bonds,"BTP_10Y","yield","%"),"N/D","MilanoFinanza","T2"],
    ["Bund 10Y",v(bonds,"BUND_10Y","yield","%"),"N/D","web_search","T2"],
    ["Spread BTP-Bund",v(bonds,"SPREAD_BTP_BUND","bp"," bp"),"N/D","calcolato","—"],
    ["OAT 10Y",v(bonds,"OAT_10Y","yield","%"),"N/D","WGB","T2"],
    ["UST 2Y",v(bonds,"UST_2Y","yield","%"),"N/D","web_search","T2"],
    ["UST 10Y",v(bonds,"UST_10Y","yield","%"),"N/D","web_search","T2"],
    ["UST 30Y",v(bonds,"UST_30Y","yield","%"),"N/D","web_search","T2"],
    ["CDS Italia 5Y",v(bonds,"CDS_ITALIA_5Y","bp"," bp"),"N/D","WGB","T2"],
], [4.5*cm,3*cm,2.5*cm,4*cm,2.5*cm], hdr=["Strumento","Rendimento","Delta","Fonte","Tier"], num_cols=(1,2)))
story.append(Spacer(1,8))

story += sec("FOREX", "03")
story.append(tbl([
    ["EUR/USD",v(forex,"EUR_USD","fx"),"N/D","ECB eurofxref XML","T1"],
    ["EUR/JPY",v(forex,"EUR_JPY","fx"),"N/D","ECB eurofxref XML","T1"],
    ["EUR/GBP",v(forex,"EUR_GBP","fx"),"N/D","ECB eurofxref XML","T1"],
    ["EUR/CHF",v(forex,"EUR_CHF","fx"),"N/D","ECB eurofxref XML","T1"],
    ["USD/JPY",v(forex,"USD_JPY","fx"),"N/D","ECB (calc)","T1"],
], [3.5*cm,3*cm,2.5*cm,5.5*cm,2*cm], hdr=["Cross","Tasso","Delta%","Fonte","Tier"], num_cols=(1,2)))
story.append(Paragraph(f"Riferimento ECB: {v(forex,'ECB_DATE')}", SS))
story.append(Spacer(1,8))

story += sec("ENERGIA - DRIVER DOMINANTE", "04")
brent_d = v(comm,"BRENT_DELTA","delta")
story.append(tbl([
    ["Brent",v(comm,"BRENT","px"),brent_d,"CNBC","T2"],
    ["WTI",v(comm,"WTI","px"),v(comm,"WTI_DELTA","delta"),"CNBC","T2"],
    ["Natural Gas",v(comm,"NAT_GAS","px"),v(comm,"NAT_GAS_DELTA","delta"),"CNBC","T2"],
    ["Gold",v(comm,"GOLD","px"),v(comm,"GOLD_DELTA","delta"),"CNBC","T2"],
    ["Silver",v(comm,"SILVER","px"),v(comm,"SILVER_DELTA","delta"),"CNBC","T2"],
], [4*cm,3*cm,3*cm,4*cm,2*cm], hdr=["Commodity","Prezzo","Delta%","Fonte","Tier"], num_cols=(1,2)))
story.append(Spacer(1,8))

story += sec("MACRO & INFLAZIONE", "05")
story.append(tbl([
    ["CPI USA (YoY)",v(macro,"CPI_USA","pct"),"BLS","T1"],
    ["Core CPI USA",v(macro,"CPI_CORE","pct"),"BLS","T1"],
    ["PPI USA (YoY)",v(macro,"PPI_USA","pct"),"BLS","T1"],
    ["HICP Eurozona",v(macro,"HICP_EZ","pct"),"Eurostat","T1"],
    ["CPI Italia",v(macro,"CPI_ITA","pct"),"ISTAT","T1"],
    ["PIL USA Q1 2026",v(macro,"PIL_USA_Q1","pct"),"BEA","T1"],
    ["PIL EZ Q1 2026",v(macro,"PIL_EZ_Q1","pct"),"Eurostat","T1"],
], [5*cm,4*cm,5*cm,2.5*cm], hdr=["Indicatore","Valore","Fonte","Tier"], num_cols=(1,)))
story.append(Spacer(1,8))

story += sec("BANCHE CENTRALI", "06")
story.append(tbl([
    ["Fed (Warsh)",v(macro,"FED_RATE","pct"),"Hold","Jun 16-17* Jul 28-29 Sep 15-16*","Fed.gov","T1"],
    ["BCE",v(macro,"BCE_RATE","pct"),"N/D","5 giu, 23 lug, 11 set","ECB","T1"],
], [3*cm,2.5*cm,2*cm,5*cm,2.5*cm,1.5*cm], hdr=["Banca","Tasso","Bias","Prossime riunioni","Fonte","Tier"], num_cols=(1,)))
story.append(Paragraph("* = SEP meeting con Dot Plot", SS))
story.append(Spacer(1,8))

story += sec("CREDITO & VOLATILITA'", "07")
story.append(tbl([
    ["VIX",v(vol,"VIX","pct"),"N/D","CBOE","T1"],
    ["iTraxx Europe","N/D","N/D","IHS Markit","T1 - abbonamento"],
    ["CDS Italia 5Y",v(bonds,"CDS_ITALIA_5Y","bp"," bp"),"N/D","WGB","T2"],
], [4*cm,3*cm,3*cm,3.5*cm,4*cm], hdr=["Indicatore","Livello","Delta","Fonte","Nota"], num_cols=(1,2)))
story.append(Paragraph("iTraxx: N/D - abbonamento IHS Markit richiesto.", SS))
story.append(Spacer(1,8))

story += sec("GEOPOLITICA", "08")
story.append(Paragraph("Driver: crisi Hormuz (Iran). ANSA headlines:", SB))
story.append(Spacer(1,4))
for hl in (headlines[:5] if headlines else ["N/D - fetch ANSA fallito"]):
    story.append(Paragraph(f"- {hl}", SS))
story.append(Spacer(1,8))

story += sec("STRESS-TEST - SCENARI A/B/C", "09")
bf = num_val(comm.get("BRENT"), "px")
ta = f"<${_it(bf*0.87, 1)}" if bf else "N/D"; tc = ">$140"
story.append(tbl([
    ["A - De-escalation Hormuz","40%",ta,"Brent -13% max in 30gg"],
    ["B - Stallo / status quo","50%","Laterale","Brent range +-5%"],
    ["C - Escalation (new shock)","10%",tc,"Trigger: attacco Saudi/UAE"],
    ["Black Swan","N/A","N/D","Escluso dalla somma per costruzione"],
], [5*cm,2*cm,3*cm,6.5*cm], hdr=["Scenario","Prob.","Target Brent","Condizione"], num_cols=(1,)))
story.append(Paragraph("Stima qualitativa esperta. Non modello quantitativo formale. Somma=100% per costruzione.", SS))
story.append(Spacer(1,8))

story += sec("AGENDA MACRO", "10")
story.append(tbl([
    ["Jun 16-17*","FOMC","USA","Fed SEP + dot plot"],
    ["Jun 5","BCE riunione","EU","Possibile +25bp"],
    ["Jul 28-29","FOMC","USA","Fed standard meeting"],
    ["Sep 15-16*","FOMC","USA","Fed SEP meeting"],
    ["Oct 27-28","FOMC","USA","Fed standard meeting"],
    ["Dec 8-9*","FOMC","USA","Fed SEP + dot plot"],
], [3*cm,4*cm,2*cm,7.5*cm], hdr=["Data","Evento","Area","Nota"]))

errors = list(errors) + QUALITY
if errors:
    story.append(Spacer(1,12))
    story.append(HRFlowable(width="100%",thickness=0.5,color=AMBER))
    story.append(Paragraph("<b>NOTE QUALITA' DATI</b>", ps("nb",fontName="Helvetica-Bold",fontSize=8.5,textColor=NAVY,leading=12)))
    for err in errors:
        story.append(Paragraph(f"WARNING: {err}", SS))

import shutil
_pdf = f"/home/claude/financial_daily_report_{DATE_STR}.pdf"
_out = f"/mnt/user-data/outputs/financial_daily_report_{DATE_STR}.pdf"
doc = SimpleDocTemplate(_pdf, pagesize=A4,
    leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=2.0*cm, bottomMargin=1.8*cm)
doc.build(keep_sections(story), onFirstPage=hdr_footer, onLaterPages=hdr_footer)
print(f"OK PDF: {_pdf}")
shutil.copy2(_pdf, _out)
print(f"OK PDF: {_out}")
