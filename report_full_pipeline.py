#!/usr/bin/env python3
"""
report_full_pipeline.py - PDF Report Finanziario v3.1
Input:  $FDR_WORK_DIR/market_data.json
Output: $FDR_WORK_DIR/financial_daily_report_{DATE_STR}.pdf (+ copia in $FDR_OUTPUT_DIR)
"""
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from fdr_common import (ND, ensure_dirs, esc, fmt, fmt_delta, get_context, headlines_of,
                        load_market_data, publish, src_label, tier, work_path)

WHITE = HexColor("#FFFFFF"); NAVY = HexColor("#0B2545"); GOLD = HexColor("#C9A84C")
AMBER = HexColor("#E07B00"); GREEN = HexColor("#1A8A4A"); RED = HexColor("#C0392B")
LGREY = HexColor("#F5F7FA"); GREY = HexColor("#2C3E50")


def ps(name, **kw):
    return ParagraphStyle(name, **kw)


SB = ps("b", fontName="Helvetica", fontSize=8.5, textColor=GREY, leading=12)
SW = ps("w", fontName="Helvetica-Bold", fontSize=8.5, textColor=WHITE, leading=12)
SS = ps("s", fontName="Helvetica", fontSize=7.5, textColor=GREY, leading=10)
ST = ps("t", fontName="Helvetica-Bold", fontSize=11, textColor=NAVY, leading=14)
SN = ps("nb", fontName="Helvetica-Bold", fontSize=8.5, textColor=NAVY, leading=12)


def P(text, style=SB):
    return Paragraph(esc(text), style)


def sec(title, num):
    return [HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=4),
            Paragraph(f"<b>{esc(num)} - {esc(title)}</b>", ST), Spacer(1, 4)]


def tbl(rows, widths, hdr=None):
    data = []
    if hdr:
        data.append([P(c, SW) for c in hdr])
    for row in rows:
        data.append([P(c) if isinstance(c, (str, int, float)) else c for c in row])
    sty = [("BACKGROUND", (0, 0), (-1, 0), NAVY) if hdr else ("BACKGROUND", (0, 0), (-1, -1), WHITE),
           ("ROWBACKGROUNDS", (0, 1 if hdr else 0), (-1, -1), [WHITE, LGREY]),
           ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    return Table(data, colWidths=widths, style=TableStyle(sty), repeatRows=1 if hdr else 0)


def build_story(mkt):
    forex, idx, bonds = mkt.get("forex", {}), mkt.get("indices", {}), mkt.get("bonds", {})
    comm, vol, macro = mkt.get("commodities", {}), mkt.get("volatility", {}), mkt.get("macro", {})
    ctx = get_context(mkt)

    def row(label, d, cat, key, pattern=None, dunit="%"):
        return [label, fmt(d, key, pattern), fmt_delta(d, f"{key}_DELTA", dunit),
                src_label(mkt, cat, key), tier(mkt, cat, key)]

    story = []
    story += sec("MERCATI AZIONARI", "01")
    story.append(tbl([
        row("FTSE MIB", idx, "indices", "FTSE_MIB", "{:,.2f}"),
        row("DAX", idx, "indices", "DAX", "{:,.2f}"),
        row("CAC 40", idx, "indices", "CAC40", "{:,.2f}"),
        row("EuroStoxx50", idx, "indices", "EUROSTOXX50", "{:,.2f}"),
        row("S&P 500", idx, "indices", "SP500", "{:,.2f}"),
        row("Nasdaq Comp.", idx, "indices", "NASDAQ", "{:,.2f}"),
        row("Dow Jones", idx, "indices", "DJI", "{:,.2f}"),
    ], [3.5 * cm, 2.7 * cm, 2.2 * cm, 6.6 * cm, 3 * cm], hdr=["Indice", "Chiusura", "Delta", "Fonte (sessione)", "Tier"]))
    story.append(Spacer(1, 8))

    story += sec("OBBLIGAZIONARIO & SPREAD", "02")
    story.append(tbl([
        row("BTP 10Y", bonds, "bonds", "BTP_10Y", "{:.2f}%", "bp"),
        row("Bund 10Y", bonds, "bonds", "BUND_10Y", "{:.3f}%", "bp"),
        row("Spread BTP-Bund", bonds, "bonds", "SPREAD_BTP_BUND", "{:.0f} bp", "bp"),
        row("OAT 10Y", bonds, "bonds", "OAT_10Y", "{:.2f}%", "bp"),
        row("UST 2Y", bonds, "bonds", "UST_2Y", "{:.2f}%", "bp"),
        row("UST 5Y", bonds, "bonds", "UST_5Y", "{:.2f}%", "bp"),
        row("UST 10Y", bonds, "bonds", "UST_10Y", "{:.2f}%", "bp"),
        row("UST 30Y", bonds, "bonds", "UST_30Y", "{:.2f}%", "bp"),
        row("CDS Italia 5Y", bonds, "bonds", "CDS_ITALIA_5Y", "{:.0f} bp", "bp"),
    ], [3.5 * cm, 2.7 * cm, 2.2 * cm, 6.6 * cm, 3 * cm], hdr=["Strumento", "Rendimento", "Delta", "Fonte (sessione)", "Tier"]))
    story.append(Spacer(1, 8))

    story += sec("FOREX", "03")
    story.append(tbl([row(lbl, forex, "forex", k, "{:.4f}") for lbl, k in
                      [("EUR/USD", "EUR_USD"), ("EUR/JPY", "EUR_JPY"), ("EUR/GBP", "EUR_GBP"),
                       ("EUR/CHF", "EUR_CHF"), ("USD/JPY", "USD_JPY")]],
                     [3.5 * cm, 2.7 * cm, 2.2 * cm, 6.6 * cm, 3 * cm], hdr=["Cross", "Tasso", "Delta", "Fonte (sessione)", "Tier"]))
    story.append(Spacer(1, 8))

    story += sec("ENERGIA & METALLI", "04")
    story.append(tbl([
        row("Brent ($/bbl)", comm, "commodities", "BRENT", "{:.2f}"),
        row("WTI ($/bbl)", comm, "commodities", "WTI", "{:.2f}"),
        row("Natural Gas ($/MMBtu)", comm, "commodities", "NAT_GAS", "{:.2f}"),
        row("Gold ($/oz)", comm, "commodities", "GOLD", "{:,.1f}"),
        row("Silver ($/oz)", comm, "commodities", "SILVER", "{:.2f}"),
    ], [3.5 * cm, 2.7 * cm, 2.2 * cm, 6.6 * cm, 3 * cm], hdr=["Commodity", "Prezzo", "Delta", "Fonte (sessione)", "Tier"]))
    story.append(Spacer(1, 8))

    story += sec("MACRO & INFLAZIONE", "05")
    story.append(tbl([[lbl, fmt(macro, k), src_label(mkt, "macro", k), tier(mkt, "macro", k)] for lbl, k in [
        ("CPI USA (YoY)", "CPI_USA"), ("Core CPI USA (YoY)", "CPI_CORE"), ("PPI USA (YoY)", "PPI_USA"),
        ("HICP Eurozona (YoY)", "HICP_EZ"), ("CPI Italia (YoY)", "CPI_ITA"),
        ("PIL USA", "PIL_USA"), ("PIL Eurozona", "PIL_EZ")]],
        [4.5 * cm, 4 * cm, 6.5 * cm, 3 * cm], hdr=["Indicatore", "Valore", "Fonte (data)", "Tier"]))
    story.append(Spacer(1, 8))

    story += sec("BANCHE CENTRALI", "06")
    cbs = ctx.get("central_banks") or []
    rates = {"Fed": ("FED_RATE", "{:.2f}%"), "BCE": ("BCE_RATE", "{:.2f}%")}
    cb_rows = []
    for cb in cbs:
        key, pat = rates.get(cb.get("bank"), (None, None))
        rate = fmt(macro, key, pat) if key else cb.get("rate", ND)
        cb_rows.append([cb.get("label", cb.get("bank", ND)), rate, cb.get("bias", ND),
                        cb.get("next", ND), src_label(mkt, "macro", key) if key else cb.get("source", ND)])
    if not cb_rows:
        cb_rows = [[b, fmt(macro, k, p), ND, ND, src_label(mkt, "macro", k)] for b, (k, p) in rates.items()]
    story.append(tbl(cb_rows, [3 * cm, 2.3 * cm, 2.2 * cm, 5.5 * cm, 5 * cm],
                     hdr=["Banca", "Tasso", "Bias", "Prossima riunione", "Fonte tasso"]))
    story.append(Spacer(1, 8))

    story += sec("CREDITO & VOLATILITA'", "07")
    story.append(tbl([
        row("VIX", vol, "volatility", "VIX", "{:.2f}"),
        ["iTraxx Europe", ND, ND, "IHS Markit - abbonamento richiesto", "—"],
        row("CDS Italia 5Y", bonds, "bonds", "CDS_ITALIA_5Y", "{:.0f} bp", "bp"),
    ], [3.5 * cm, 2.7 * cm, 2.2 * cm, 6.6 * cm, 3 * cm], hdr=["Indicatore", "Livello", "Delta", "Fonte (sessione)", "Tier"]))
    story.append(Spacer(1, 8))

    story += sec("GEOPOLITICA", "08")
    story.append(P(f"Driver: {ctx.get('geo_driver') or 'N/D - driver non fornito nel contesto'}"))
    for item in ctx.get("geo_notes") or []:
        story.append(P(f"- {item}", SS))
    story.append(Spacer(1, 4))
    story.append(P("ANSA headlines:", SN))
    for hl in headlines_of(mkt)[:5] or ["N/D - fetch ANSA fallito"]:
        story.append(P(f"- {hl}", SS))
    story.append(Spacer(1, 8))

    story += sec("STRESS-TEST - SCENARI", "09")
    scen = ctx.get("scenarios") or []
    if scen:
        rows = [[s.get("name", ND), f"{s['prob']:g}%" if s.get("prob") is not None else "N/A (coda)",
                 s.get("target", ND), s.get("condition", ND)] for s in scen]
        story.append(tbl(rows, [5 * cm, 2.3 * cm, 3.2 * cm, 7.5 * cm], hdr=["Scenario", "Prob.", "Target", "Condizione / trigger"]))
        story.append(P("Somma scenari A/B/C = 100% (validata). Black Swan escluso dalla somma. "
                       + (ctx.get("scenarios_note") or "Stima qualitativa esperta."), SS))
    else:
        story.append(P("N/D - scenari non forniti nel contesto (nessuna probabilita' di default).", SS))
    story.append(Spacer(1, 8))

    story += sec("AGENDA MACRO", "10")
    agenda = ctx.get("agenda") or []
    if agenda:
        story.append(tbl([[a.get("date", ND), a.get("event", ND), a.get("area", ND), a.get("note", "")] for a in agenda],
                         [3 * cm, 6 * cm, 2 * cm, 7 * cm], hdr=["Data", "Evento", "Area", "Nota"]))
    else:
        story.append(P("N/D - agenda non fornita nel contesto.", SS))

    errors = mkt.get("errors", [])
    if errors:
        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=0.5, color=AMBER))
        story.append(P("NOTE QUALITA' DATI", SN))
        for err in errors:
            story.append(P(f"WARNING: {err}", SS))
    return story


def make_header(mkt):
    meta = mkt.get("meta", {})
    dc, dr = meta.get("DATE_CHIUSURA", ND), meta.get("DATE_REPORT", ND)

    def hdr_footer(canvas, doc):
        w, h = A4
        canvas.saveState()
        canvas.setFillColor(NAVY); canvas.rect(0, h - 1.5 * cm, w, 1.5 * cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE); canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(1.5 * cm, h - 1.0 * cm, "FINANCIAL DAILY REPORT  di Ettore Turchet")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 1.5 * cm, h - 1.0 * cm, f"Chiusura: {dc}  |  Report: {dr}")
        canvas.setStrokeColor(GOLD); canvas.setLineWidth(1.5)
        canvas.line(1.5 * cm, h - 1.55 * cm, w - 1.5 * cm, h - 1.55 * cm)
        canvas.setFont("Helvetica", 7); canvas.setFillColor(GREY)
        canvas.drawString(1.5 * cm, 0.7 * cm, "Report finanziario a uso interno - fonti e tier indicati per ogni dato")
        canvas.drawRightString(w - 1.5 * cm, 0.7 * cm, f"Pag. {doc.page}")
        canvas.restoreState()
    return hdr_footer


def main():
    ensure_dirs()
    mkt = load_market_data()
    date_str = mkt.get("meta", {}).get("DATE_STR", "2026-01-01")
    pdf = work_path(f"financial_daily_report_{date_str}.pdf")
    doc = SimpleDocTemplate(pdf, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=2.0 * cm, bottomMargin=1.8 * cm)
    hf = make_header(mkt)
    doc.build(build_story(mkt), onFirstPage=hf, onLaterPages=hf)
    print(f"OK PDF: {pdf}")
    print(f"OK PDF: {publish(pdf)}")


if __name__ == "__main__":
    main()
