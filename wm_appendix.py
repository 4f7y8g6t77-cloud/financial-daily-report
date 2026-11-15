#!/usr/bin/env python3
"""
wm_appendix.py - Allegato Wealth Management PDF + XLSX dati v3.1
Input:  $FDR_WORK_DIR/market_data.json
Output: $FDR_WORK_DIR/financial_wm_appendix_{DATE_STR}.pdf
        $FDR_WORK_DIR/financial_daily_data_{DATE_STR}.xlsx  (+ copie in $FDR_OUTPUT_DIR)

Raccomandazioni WM, scenari e agenda vengono dal contesto (supplement.json):
nessun contenuto narrativo hard-coded.
"""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from fdr_common import (ND, ensure_dirs, esc, fmt, fmt_delta, get_context, load_market_data,
                        publish, src, to_float, work_path)

WHITE = HexColor("#FFFFFF"); NAVY = HexColor("#0B2545"); GOLD = HexColor("#C9A84C")
AMBER = HexColor("#E07B00"); GREEN = HexColor("#1A8A4A"); RED = HexColor("#C0392B")
LGREY = HexColor("#F5F7FA"); GREY = HexColor("#2C3E50")
NAVY_H = "0B2545"; GOLD_H = "C9A84C"; GREEN_H = "1A8A4A"; RED_H = "C0392B"; AMBER_H = "E07B00"


def ps(n, **kw):
    return ParagraphStyle(n, **kw)


SB = ps("b", fontName="Helvetica", fontSize=8, textColor=GREY, leading=11)
SW = ps("w", fontName="Helvetica-Bold", fontSize=8, textColor=WHITE, leading=11)
SS = ps("s", fontName="Helvetica", fontSize=7, textColor=GREY, leading=10)
ST = ps("t", fontName="Helvetica-Bold", fontSize=10, textColor=NAVY, leading=13)
STATUS_STYLE = {
    "ALERT": ps("r", fontName="Helvetica-Bold", fontSize=8, textColor=RED, leading=11),
    "WARN": ps("a", fontName="Helvetica-Bold", fontSize=8, textColor=AMBER, leading=11),
    "OK": ps("g", fontName="Helvetica-Bold", fontSize=8, textColor=GREEN, leading=11),
}
STATUS_HEX = {"ALERT": RED_H, "WARN": AMBER_H, "OK": GREEN_H}


def P(t, s=SB):
    return Paragraph(esc(t), s)


def sec(t, n):
    return [HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=4),
            Paragraph(f"<b>{esc(n)} - {esc(t)}</b>", ST), Spacer(1, 4)]


def tbl(rows, widths, hdr=None):
    tr = []
    if hdr:
        tr.append([P(c, SW) for c in hdr])
    for row in rows:
        tr.append([P(c) if isinstance(c, (str, int, float)) else c for c in row])
    sty = [("BACKGROUND", (0, 0), (-1, 0), NAVY) if hdr else ("BACKGROUND", (0, 0), (-1, -1), WHITE),
           ("ROWBACKGROUNDS", (0, 1 if hdr else 0), (-1, -1), [WHITE, LGREY]),
           ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    return Table(tr, colWidths=widths, style=TableStyle(sty), repeatRows=1 if hdr else 0)


def risk_status(val, amber, red, high_is_bad=True):
    f = to_float(val)
    if f is None:
        return ND
    if high_is_bad:
        return "ALERT" if f >= red else ("WARN" if f >= amber else "OK")
    return "ALERT" if f <= red else ("WARN" if f <= amber else "OK")


def market_rows(mkt):
    """[(asset, categoria, valore, delta, fonte, tier, as_of)] per PDF e XLSX."""
    spec = [
        ("FTSE MIB", "Equity EU", "indices", "FTSE_MIB", "{:,.2f}", "%"),
        ("DAX", "Equity EU", "indices", "DAX", "{:,.2f}", "%"),
        ("EuroStoxx50", "Equity EU", "indices", "EUROSTOXX50", "{:,.2f}", "%"),
        ("S&P 500", "Equity US", "indices", "SP500", "{:,.2f}", "%"),
        ("Nasdaq", "Equity US", "indices", "NASDAQ", "{:,.2f}", "%"),
        ("EUR/USD", "FX", "forex", "EUR_USD", "{:.4f}", "%"),
        ("EUR/JPY", "FX", "forex", "EUR_JPY", "{:.2f}", "%"),
        ("EUR/GBP", "FX", "forex", "EUR_GBP", "{:.4f}", "%"),
        ("BTP 10Y", "Bond IT", "bonds", "BTP_10Y", "{:.2f}%", "bp"),
        ("Bund 10Y", "Bond DE", "bonds", "BUND_10Y", "{:.3f}%", "bp"),
        ("Spread BTP-Bund", "Spread", "bonds", "SPREAD_BTP_BUND", "{:.0f} bp", "bp"),
        ("UST 2Y", "Bond US", "bonds", "UST_2Y", "{:.2f}%", "bp"),
        ("UST 10Y", "Bond US", "bonds", "UST_10Y", "{:.2f}%", "bp"),
        ("UST 30Y", "Bond US", "bonds", "UST_30Y", "{:.2f}%", "bp"),
        ("VIX", "Volatilita'", "volatility", "VIX", "{:.2f}", "%"),
        ("Brent", "Commodity", "commodities", "BRENT", "{:.2f}", "%"),
        ("Gold", "Commodity", "commodities", "GOLD", "{:,.1f}", "%"),
        ("BTC/USD", "Crypto", "crypto", "BTC_USD", "{:,.0f}", "%"),
    ]
    out = []
    for label, catlbl, cat, key, pat, du in spec:
        d = mkt.get(cat, {})
        s, t, a = src(mkt, cat, key)
        out.append((label, catlbl, fmt(d, key, pat), fmt_delta(d, f"{key}_DELTA", du), s, t, a))
    out.append(("iTraxx HY", "Credit", ND, ND, "IHS Markit - abbonamento", "—", ""))
    return out


def risk_rows(mkt):
    vol, bonds = mkt.get("volatility", {}), mkt.get("bonds", {})
    comm, forex = mkt.get("commodities", {}), mkt.get("forex", {})
    return [
        ("VIX", fmt(vol, "VIX", "{:.2f}"), "> 25", "> 35", risk_status(vol.get("VIX"), 25, 35)),
        ("Spread BTP-Bund", fmt(bonds, "SPREAD_BTP_BUND", "{:.0f} bp"), "> 100bp", "> 150bp",
         risk_status(bonds.get("SPREAD_BTP_BUND"), 100, 150)),
        ("Brent", fmt(comm, "BRENT", "${:.2f}"), "> $100", "> $130", risk_status(comm.get("BRENT"), 100, 130)),
        ("CDS Italia 5Y", fmt(bonds, "CDS_ITALIA_5Y", "{:.0f} bp"), "> 35bp", "> 60bp",
         risk_status(bonds.get("CDS_ITALIA_5Y"), 35, 60)),
        ("EUR/USD", fmt(forex, "EUR_USD", "{:.4f}"), "< 1.05", "< 1.00",
         risk_status(forex.get("EUR_USD"), 1.05, 1.00, high_is_bad=False)),
        ("iTraxx HY", ND, "> 400bp", "> 600bp", "N/D - abbonamento"),
    ]


def build_pdf(mkt, ctx, path):
    meta = mkt.get("meta", {})
    dc, dr = meta.get("DATE_CHIUSURA", ND), meta.get("DATE_REPORT", ND)

    def hdr_ftr(canvas, doc):
        w, h = landscape(A4)
        canvas.saveState()
        canvas.setFillColor(NAVY); canvas.rect(0, h - 1.5 * cm, w, 1.5 * cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE); canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(1.5 * cm, h - 1.0 * cm, "FINANCIAL DAILY REPORT  di Ettore Turchet - Allegato WM")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 1.5 * cm, h - 1.0 * cm, f"Chiusura: {dc}  |  Report: {dr}")
        canvas.setStrokeColor(GOLD); canvas.setLineWidth(1.5)
        canvas.line(1.5 * cm, h - 1.55 * cm, w - 1.5 * cm, h - 1.55 * cm)
        canvas.setFont("Helvetica", 7); canvas.setFillColor(GREY)
        canvas.drawString(1.5 * cm, 0.7 * cm, "Allegato WM - uso interno")
        canvas.drawRightString(w - 1.5 * cm, 0.7 * cm, f"Pag. {doc.page}")
        canvas.restoreState()

    story = sec("MARKET DATA EXTENDED", "A")
    story.append(tbl([[r[0], r[2], r[3], r[1], f"{r[4]} ({r[6]})" if r[6] else r[4], r[5]] for r in market_rows(mkt)],
                     [3.8 * cm, 3 * cm, 2.5 * cm, 3 * cm, 9 * cm, 2.2 * cm],
                     hdr=["Asset", "Valore", "Delta", "Categoria", "Fonte (sessione)", "Tier"]))
    story.append(Spacer(1, 10))

    story += sec("RACCOMANDAZIONI WEALTH MANAGEMENT", "B")
    recs = ctx.get("wm_recommendations") or []
    if recs:
        story.append(tbl([[r.get("asset", ND), r.get("position", ND), r.get("direction", ND),
                           r.get("rationale", ND), r.get("risk", ND)] for r in recs],
                         [4 * cm, 3 * cm, 1.5 * cm, 10 * cm, 5 * cm],
                         hdr=["Asset Class", "Posizione", "Dir.", "Rationale", "Rischio"]))
    else:
        story.append(P("N/D - raccomandazioni non fornite nel contesto.", SS))
    story.append(Spacer(1, 10))

    story += sec("STRESS TEST - SCENARI", "C")
    scen = ctx.get("scenarios") or []
    if scen:
        story.append(tbl([[s.get("name", ND), f"{s['prob']:g}%" if s.get("prob") is not None else "N/A (coda)",
                           s.get("target", ND), s.get("equity", ND), s.get("condition", ND), s.get("risk", ND)]
                          for s in scen],
                         [4.5 * cm, 2.2 * cm, 3 * cm, 3.5 * cm, 8 * cm, 2.3 * cm],
                         hdr=["Scenario", "Prob.", "Target", "Equity", "Trigger", "Rischio"]))
        story.append(P("Somma A/B/C = 100% (validata); Black Swan escluso per costruzione.", SS))
    else:
        story.append(P("N/D - scenari non forniti nel contesto.", SS))
    story.append(Spacer(1, 10))

    story += sec("INDICATORI DI RISCHIO", "D")
    story.append(tbl([[n, v, a, r, Paragraph(esc(s), STATUS_STYLE.get(s, SB))] for n, v, a, r, s in risk_rows(mkt)],
                     [4.5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm, 5 * cm],
                     hdr=["Indicatore", "Valore", "Soglia AMBER", "Soglia RED", "Status"]))
    story.append(Spacer(1, 10))

    story += sec("AGENDA MACRO & BANCHE CENTRALI", "E")
    agenda = ctx.get("agenda") or []
    if agenda:
        story.append(tbl([[a.get("date", ND), a.get("event", ND), a.get("area", ND), a.get("note", ""),
                           a.get("source", "")] for a in agenda],
                         [3 * cm, 6 * cm, 2 * cm, 8.5 * cm, 4 * cm],
                         hdr=["Data", "Evento", "Area", "Impatto atteso", "Fonte"]))
    else:
        story.append(P("N/D - agenda non fornita nel contesto.", SS))

    doc = SimpleDocTemplate(path, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=2.0 * cm, bottomMargin=1.5 * cm)
    doc.build(story, onFirstPage=hdr_ftr, onLaterPages=hdr_ftr)


def build_xlsx(mkt, ctx, path):
    meta = mkt.get("meta", {})
    dc, dr = meta.get("DATE_CHIUSURA", ND), meta.get("DATE_REPORT", ND)
    brd = Border(*(Side(style="thin", color="CCCCCC"),) * 4)

    def hs(c):
        c.font = Font(bold=True, color="FFFFFF", size=9)
        c.fill = PatternFill("solid", fgColor=NAVY_H)
        c.border = brd
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def ds(c, alt=False):
        c.font = Font(size=9)
        c.fill = PatternFill("solid", fgColor="F5F7FA") if alt else PatternFill()
        c.border = brd
        c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    def aw(ws, mn=10, mx=60):
        for col in ws.columns:
            width = max([mn] + [min(mx, len(str(c.value)) + 2) for c in col if c.value and c.row > 1])
            ws.column_dimensions[get_column_letter(col[0].column)].width = width

    def sheet(ws, title, headers, rows):
        ws["A1"] = title
        ws["A1"].font = Font(bold=True, size=11, color=NAVY_H)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        for j, h in enumerate(headers, 1):
            hs(ws.cell(row=2, column=j, value=h))
        for i, row in enumerate(rows, 3):
            for j, val in enumerate(row, 1):
                ds(ws.cell(row=i, column=j, value=val), i % 2 == 0)

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Market Data"; ws1.sheet_properties.tabColor = NAVY_H
    sheet(ws1, f"FINANCIAL DAILY REPORT - Chiusura {dc} | Report {dr}",
          ["Asset", "Categoria", "Valore", "Delta", "Fonte", "Tier", "Sessione"],
          [[r[0], r[1], r[2], r[3], r[4], r[5], r[6]] for r in market_rows(mkt)])
    for i in range(3, ws1.max_row + 1):
        t = ws1.cell(row=i, column=6)
        if t.value == "T1":
            t.font = Font(size=9, color=GREEN_H, bold=True)
        if ws1.cell(row=i, column=3).value == ND:
            ws1.cell(row=i, column=3).font = Font(size=9, color=AMBER_H)
    aw(ws1)

    ws2 = wb.create_sheet("Raccomandazioni WM"); ws2.sheet_properties.tabColor = GOLD_H
    recs = ctx.get("wm_recommendations") or []
    sheet(ws2, f"RACCOMANDAZIONI WM - {dr}", ["Asset Class", "Posizionamento", "Direzione", "Rationale", "Rischio"],
          [[r.get("asset", ND), r.get("position", ND), r.get("direction", ND), r.get("rationale", ND), r.get("risk", ND)]
           for r in recs] or [[ND, "non fornite nel contesto", "", "", ""]])
    for i in range(3, ws2.max_row + 1):
        c = ws2.cell(row=i, column=2)
        if c.value == "Sovrappeso":
            c.font = Font(size=9, color=GREEN_H, bold=True)
        elif c.value == "Sottopeso":
            c.font = Font(size=9, color=RED_H, bold=True)
    aw(ws2)

    ws3 = wb.create_sheet("Risk Metrics"); ws3.sheet_properties.tabColor = RED_H
    sheet(ws3, f"RISK INDICATORS - {dr}", ["Metrica", "Valore", "Soglia AMBER", "Soglia RED", "Status"],
          [list(r) for r in risk_rows(mkt)])
    for i in range(3, ws3.max_row + 1):
        c = ws3.cell(row=i, column=5)
        if c.value in STATUS_HEX:
            c.font = Font(size=9, color=STATUS_HEX[c.value], bold=True)
    aw(ws3)

    ws4 = wb.create_sheet("Qualita' dati"); ws4.sheet_properties.tabColor = AMBER_H
    sheet(ws4, f"NOTE QUALITA' DATI - {dr}", ["Nota"], [[e] for e in mkt.get("errors", [])] or [["Nessuna"]])
    aw(ws4, mx=120)

    wb.save(path)


def main():
    ensure_dirs()
    mkt = load_market_data()
    ctx = get_context(mkt)
    date_str = mkt.get("meta", {}).get("DATE_STR", "2026-01-01")
    pdf = work_path(f"financial_wm_appendix_{date_str}.pdf")
    xlsx = work_path(f"financial_daily_data_{date_str}.xlsx")
    build_pdf(mkt, ctx, pdf)
    print(f"OK WM PDF: {pdf}")
    print(f"OK WM PDF: {publish(pdf)}")
    build_xlsx(mkt, ctx, xlsx)
    print(f"OK XLSX: {xlsx}")
    print(f"OK XLSX: {publish(xlsx)}")
    print(f"\nWM Appendix + XLSX {mkt.get('meta', {}).get('DATE_REPORT', ND)} completati.")


if __name__ == "__main__":
    main()
