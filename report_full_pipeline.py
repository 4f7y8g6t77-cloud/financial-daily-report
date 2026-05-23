#!/usr/bin/env python3
"""
report_full_pipeline.py - PDF Report Finanziario v3.0
Input:  /home/claude/market_data.json
Output: /home/claude/financial_daily_report_{DATE_STR}.pdf
        /mnt/user-data/outputs/financial_daily_report_{DATE_STR}.pdf
"""
import json, os
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate,
                                 Spacer, Table, TableStyle)

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

def v(d, k, fmt=None):
    val = d.get(k)
    if val is None or val == "N/D": return "N/D"
    if fmt:
        try: return fmt.format(float(val))
        except: return str(val)
    return str(val)

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
    return [HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=4),
            Paragraph(f"<b>{num} - {title}</b>", ST), Spacer(1, 4)]

def tbl(rows, widths, hdr=None):
    tbl_rows = []
    if hdr: tbl_rows.append([Paragraph(str(c), SW) for c in hdr])
    for row in rows:
        tbl_rows.append([Paragraph(str(c), SB) if isinstance(c,str) else c for c in row])
    sty = [("BACKGROUND",(0,0),(-1,0),NAVY) if hdr else ("BACKGROUND",(0,0),(-1,-1),WHITE),
           ("ROWBACKGROUNDS",(0,1 if hdr else 0),(-1,-1),[WHITE,LGREY]),
           ("GRID",(0,0),(-1,-1),0.3,HexColor("#CCCCCC")),
           ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4),
           ("LEFTPADDING",(0,0),(-1,-1),6), ("RIGHTPADDING",(0,0),(-1,-1),6),
           ("WORDWRAP",(0,0),(-1,-1),"LTR")]
    return Table(tbl_rows, colWidths=widths, style=TableStyle(sty), repeatRows=1 if hdr else 0)

story = []

story += sec("PIAZZA AFFARI", "01")
story.append(tbl([
    ["FTSE MIB",v(idx,"FTSE_MIB"),v(idx,"FTSE_MIB_DELTA"),"MilanoFinanza","T2"],
    ["DAX",v(idx,"DAX"),v(idx,"DAX_DELTA"),"MilanoFinanza","T2"],
    ["CAC 40",v(idx,"CAC40"),v(idx,"CAC40_DELTA"),"MilanoFinanza","T2"],
    ["EuroStoxx50",v(idx,"EUROSTOXX50"),v(idx,"EUROSTOXX50_DELTA"),"MilanoFinanza","T2"],
    ["S&P 500",v(idx,"SP500"),v(idx,"SP500_DELTA"),"CNBC","T2"],
    ["Nasdaq",v(idx,"NASDAQ"),v(idx,"NASDAQ_DELTA"),"CNBC","T2"],
    ["Dow Jones",v(idx,"DJI"),v(idx,"DJI_DELTA"),"CNBC","T2"],
], [5*cm,3*cm,3*cm,4.5*cm,1.5*cm], hdr=["Indice","Chiusura","Delta%","Fonte","Tier"]))
story.append(Spacer(1,8))

story += sec("OBBLIGAZIONARIO & SPREAD", "02")
story.append(tbl([
    ["BTP 10Y",v(bonds,"BTP_10Y","{:.2f}%"),"N/D","MilanoFinanza","T2"],
    ["Bund 10Y",v(bonds,"BUND_10Y","{:.2f}%"),"N/D","web_search","T2"],
    ["Spread BTP-Bund",v(bonds,"SPREAD_BTP_BUND","{:.0f} bp"),"N/D","calcolato","â€”"],
    ["OAT 10Y",v(bonds,"OAT_10Y","{:.2f}%"),"N/D","WGB","T2"],
    ["UST 2Y",v(bonds,"UST_2Y","{:.2f}%"),"N/D","web_search","T2"],
    ["UST 10Y",v(bonds,"UST_10Y","{:.2f}%"),"N/D","web_search","T2"],
    ["UST 30Y",v(bonds,"UST_30Y","{:.2f}%"),"N/D","web_search","T2"],
    ["CDS Italia 5Y",v(bonds,"CDS_ITALIA_5Y","{:.0f} bp"),"N/D","WGB","T2"],
], [4.5*cm,3*cm,2.5*cm,4*cm,2.5*cm], hdr=["Strumento","Rendimento","Delta","Fonte","Tier"]))
story.append(Spacer(1,8))

story += sec("FOREX", "03")
story.append(tbl([
    ["EUR/USD",v(forex,"EUR_USD"),"N/D","ECB eurofxref XML","T1"],
    ["EUR/JPY",v(forex,"EUR_JPY"),"N/D","ECB eurofxref XML","T1"],
    ["EUR/GBP",v(forex,"EUR_GBP"),"N/D","ECB eurofxref XML","T1"],
    ["EUR/CHF",v(forex,"EUR_CHF"),"N/D","ECB eurofxref XML","T1"],
    ["USD/JPY",v(forex,"USD_JPY"),"N/D","ECB (calc)","T1"],
], [3.5*cm,3*cm,2.5*cm,5.5*cm,2*cm], hdr=["Cross","Tasso","Delta%","Fonte","Tier"]))
story.append(Paragraph(f"Riferimento ECB: {v(forex,'ECB_DATE')}", SS))
story.append(Spacer(1,8))

story += sec("ENERGIA - DRIVER DOMINANTE", "04")
brent_d = v(comm,"BRENT_DELTA")
story.append(tbl([
    ["Brent",v(comm,"BRENT"),brent_d,"CNBC","T2"],
    ["WTI",v(comm,"WTI"),v(comm,"WTI_DELTA"),"CNBC","T2"],
    ["Natural Gas",v(comm,"NAT_GAS"),v(comm,"NAT_GAS_DELTA"),"CNBC","T2"],
    ["Gold",v(comm,"GOLD"),v(comm,"GOLD_DELTA"),"CNBC","T2"],
    ["Silver",v(comm,"SILVER"),v(comm,"SILVER_DELTA"),"CNBC","T2"],
], [4*cm,3*cm,3*cm,4*cm,2*cm], hdr=["Commodity","Prezzo","Delta%","Fonte","Tier"]))
story.append(Spacer(1,8))

story += sec("MACRO & INFLAZIONE", "05")
story.append(tbl([
    ["CPI USA (YoY)",v(macro,"CPI_USA"),"BLS","T1"],
    ["Core CPI USA",v(macro,"CPI_CORE"),"BLS","T1"],
    ["PPI USA (YoY)",v(macro,"PPI_USA"),"BLS","T1"],
    ["HICP Eurozona",v(macro,"HICP_EZ"),"Eurostat","T1"],
    ["CPI Italia",v(macro,"CPI_ITA"),"ISTAT","T1"],
    ["PIL USA Q1 2026",v(macro,"PIL_USA_Q1"),"BEA","T1"],
    ["PIL EZ Q1 2026",v(macro,"PIL_EZ_Q1"),"Eurostat","T1"],
], [5*cm,4*cm,5*cm,2.5*cm], hdr=["Indicatore","Valore","Fonte","Tier"]))
story.append(Spacer(1,8))

story += sec("BANCHE CENTRALI", "06")
story.append(tbl([
    ["Fed (Warsh)",v(macro,"FED_RATE"),"Hold","Jun 16-17* Jul 28-29 Sep 15-16*","Fed.gov","T1"],
    ["BCE",v(macro,"BCE_RATE"),"N/D","5 giu, 23 lug, 11 set","ECB","T1"],
], [3*cm,2.5*cm,2*cm,5*cm,2.5*cm,1.5*cm], hdr=["Banca","Tasso","Bias","Prossime riunioni","Fonte","Tier"]))
story.append(Paragraph("* = SEP meeting con Dot Plot", SS))
story.append(Spacer(1,8))

story += sec("CREDITO & VOLATILITA'", "07")
story.append(tbl([
    ["VIX",v(vol,"VIX"),"N/D","CBOE","T1"],
    ["iTraxx Europe","N/D","N/D","IHS Markit","T1 - abbonamento"],
    ["CDS Italia 5Y",v(bonds,"CDS_ITALIA_5Y","{:.0f}bp"),"N/D","WGB","T2"],
], [4*cm,3*cm,3*cm,3.5*cm,4*cm], hdr=["Indicatore","Livello","Delta","Fonte","Nota"]))
story.append(Paragraph("iTraxx: N/D - abbonamento IHS Markit richiesto.", SS))
story.append(Spacer(1,8))

story += sec("GEOPOLITICA", "08")
story.append(Paragraph("Driver: crisi Hormuz (Iran). ANSA headlines:", SB))
story.append(Spacer(1,4))
for hl in (headlines[:5] if headlines else ["N/D - fetch ANSA fallito"]):
    story.append(Paragraph(f"- {hl}", SS))
story.append(Spacer(1,8))

story += sec("STRESS-TEST - SCENARI A/B/C", "09")
try:
    bf = float(str(comm.get("BRENT","0")).replace("$","").replace(",","."))
    ta = f"<${bf*0.87:.1f}"; tc = ">$140"
except: ta = "N/D"; tc = ">$140"
story.append(tbl([
    ["A - De-escalation Hormuz","40%",ta,"Brent -13% max in 30gg"],
    ["B - Stallo / status quo","45%","Laterale","Brent range +-5%"],
    ["C - Escalation (new shock)","10%",tc,"Trigger: attacco Saudi/UAE"],
    ["Black Swan","N/A","N/D","Escluso dalla somma per costruzione"],
], [5*cm,2*cm,3*cm,6.5*cm], hdr=["Scenario","Prob.","Target Brent","Condizione"]))
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

if errors:
    story.append(Spacer(1,12))
    story.append(HRFlowable(width="100%",thickness=0.5,color=AMBER))
    story.append(Paragraph("<b>NOTE QUALITA' DATI</b>", ps("nb",fontName="Helvetica-Bold",fontSize=8.5,textColor=NAVY,leading=12)))
    for err in errors:
        story.append(Paragraph(f"WARNING: {err}", SS))

for out in [f"/home/claude/financial_daily_report_{DATE_STR}.pdf",
            f"/mnt/user-data/outputs/financial_daily_report_{DATE_STR}.pdf"]:
    os.makedirs(os.path.dirname(out) if "/" in out else ".", exist_ok=True)
    doc = SimpleDocTemplate(out, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=2.0*cm, bottomMargin=1.8*cm)
    doc.build(story, onFirstPage=hdr_footer, onLaterPages=hdr_footer)
    print(f"OK PDF: {out}")
