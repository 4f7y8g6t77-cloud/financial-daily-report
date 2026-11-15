#!/usr/bin/env python3
"""
dashboard_wm.py - Dashboard PNG 4 pannelli v3.1
Input:  $FDR_WORK_DIR/market_data.json
Output: $FDR_WORK_DIR/financial_daily_dashboard_{DATE_STR}.png (+ copia in $FDR_OUTPUT_DIR)

Dati mancanti: barra grigia vuota con etichetta "N/D", mai un valore 0 fittizio.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

from fdr_common import ensure_dirs, get_context, load_market_data, publish, to_float, work_path  # noqa: E402

NAVY = "#0B2545"; GOLD = "#C9A84C"; GREEN = "#1A8A4A"; RED = "#C0392B"
AMBER = "#E07B00"; WHITE = "#FFFFFF"; GREY = "#6C7A89"; PANEL = "#0D1B2A"; BLUE = "#4FC3F7"


def style_ax(ax, title):
    ax.set_facecolor(PANEL)
    ax.set_title(title, color=GOLD, fontsize=10, fontweight="bold", pad=8)
    ax.tick_params(colors=WHITE, labelsize=7.5)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GOLD)


def bar_panel(ax, title, items, fmt="{:+.2f}%", signed=True, band=None):
    """items: [(label, value|None)]. None -> barra N/D grigia a altezza zero."""
    style_ax(ax, title)
    labels = [lb for lb, _ in items]
    vals = [v for _, v in items]
    heights = [v if v is not None else 0 for v in vals]
    if signed:
        colors = [GREY if v is None else (GREEN if v >= 0 else RED) for v in vals]
    else:
        colors = [GREY if v is None else BLUE for v in vals]
    bars = ax.bar(labels, heights, color=colors, width=0.6, edgecolor=NAVY, linewidth=0.5)
    if signed:
        ax.axhline(y=0, color=GOLD, linewidth=0.8, linestyle="--", alpha=0.7)
    if band:
        for y in (band, -band):
            ax.axhline(y=y, color=AMBER, linewidth=0.5, linestyle=":", alpha=0.5)
    known = [v for v in vals if v is not None]
    if not known:
        ax.set_ylim(-1, 1)
        ax.text(0.5, 0.5, "Dati N/D", transform=ax.transAxes, ha="center", va="center",
                color=GREY, fontsize=12, fontweight="bold")
    else:
        ax.margins(y=0.18)
    span = (max(known) - min(min(known), 0)) if known else 1
    pad = max(span * 0.04, 0.02)
    for bar, v in zip(bars, vals):
        x = bar.get_x() + bar.get_width() / 2
        if v is None:
            ax.text(x, 0, "N/D", ha="center", va="bottom", color=GREY, fontsize=7.5, fontweight="bold")
        else:
            up = v >= 0
            ax.text(x, v + (pad if up else -pad), fmt.format(v), ha="center",
                    va="bottom" if up else "top", color=WHITE, fontsize=7, fontweight="bold")


def main():
    ensure_dirs()
    mkt = load_market_data()
    meta, forex, idx = mkt.get("meta", {}), mkt.get("forex", {}), mkt.get("indices", {})
    bonds, comm, vol = mkt.get("bonds", {}), mkt.get("commodities", {}), mkt.get("volatility", {})
    ctx = get_context(mkt)
    sf = lambda d, k: to_float(d.get(k))  # noqa: E731

    fig = plt.figure(figsize=(19.2, 10.8), facecolor=NAVY)
    gs = GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.30, left=0.05, right=0.97, top=0.88, bottom=0.08)
    fig.text(0.5, 0.95, f"FINANCIAL DAILY REPORT  -  Chiusura {meta.get('DATE_CHIUSURA', 'N/D')}",
             ha="center", fontsize=15, fontweight="bold", color=WHITE, fontfamily="monospace")
    fig.text(0.5, 0.91, f"Report: {meta.get('DATE_REPORT', 'N/D')}", ha="center", fontsize=10,
             color=GOLD, fontfamily="monospace")

    bar_panel(fig.add_subplot(gs[0, 0]), "INDICI AZIONARI (Delta% giornaliero)", [
        ("FTSE MIB", sf(idx, "FTSE_MIB_DELTA")), ("DAX", sf(idx, "DAX_DELTA")),
        ("CAC 40", sf(idx, "CAC40_DELTA")), ("S&P 500", sf(idx, "SP500_DELTA")),
        ("Nasdaq", sf(idx, "NASDAQ_DELTA")), ("DJI", sf(idx, "DJI_DELTA"))])

    ax2 = fig.add_subplot(gs[0, 1])
    bar_panel(ax2, "RENDIMENTI OBBLIGAZIONARI (%)", [
        ("BTP 10Y", sf(bonds, "BTP_10Y")), ("Bund 10Y", sf(bonds, "BUND_10Y")),
        ("OAT 10Y", sf(bonds, "OAT_10Y")), ("UST 2Y", sf(bonds, "UST_2Y")),
        ("UST 10Y", sf(bonds, "UST_10Y")), ("UST 30Y", sf(bonds, "UST_30Y"))],
        fmt="{:.2f}%", signed=False)
    sp_val = sf(bonds, "SPREAD_BTP_BUND")
    ax2.text(0.02, 0.97, f"Spread BTP-Bund: {sp_val:.0f}bp" if sp_val is not None else "Spread BTP-Bund: N/D",
             transform=ax2.transAxes, ha="left", va="top", fontsize=8.5, fontweight="bold",
             color=GREY if sp_val is None else (AMBER if sp_val > 100 else GREEN))

    bar_panel(fig.add_subplot(gs[1, 0]), "COMMODITIES (Delta% giornaliero)", [
        ("Brent", sf(comm, "BRENT_DELTA")), ("WTI", sf(comm, "WTI_DELTA")),
        ("Gold", sf(comm, "GOLD_DELTA")), ("Silver", sf(comm, "SILVER_DELTA")),
        ("NatGas", sf(comm, "NAT_GAS_DELTA"))], band=5)

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor(PANEL)
    ax4.set_title("SCENARI PROBABILISTICI", color=GOLD, fontsize=10, fontweight="bold", pad=8)
    scen = [s for s in (ctx.get("scenarios") or []) if s.get("prob")]
    if scen:
        palette = [GREEN, BLUE, RED, AMBER, GREY]
        ax4.pie([s["prob"] for s in scen], labels=[s.get("short", s.get("name", "")) for s in scen],
                colors=palette[:len(scen)], startangle=90,
                autopct=lambda p: f"{p:.0f}%", textprops={"color": WHITE, "fontsize": 9},
                wedgeprops={"edgecolor": NAVY, "linewidth": 1.5})
    else:
        ax4.axis("off")
        ax4.text(0.5, 0.5, "Scenari N/D", ha="center", va="center", transform=ax4.transAxes,
                 color=WHITE, fontsize=12)
    vix, eur, br = sf(vol, "VIX"), sf(forex, "EUR_USD"), sf(comm, "BRENT")
    info = (f"VIX: {vix:.1f}  " if vix is not None else "VIX: N/D  ") + \
           (f"EUR/USD: {eur:.4f}  " if eur is not None else "EUR/USD: N/D  ") + \
           (f"Brent: ${br:.1f}" if br is not None else "Brent: N/D")
    fig.text(0.75, 0.04, info, ha="center", color=GOLD, fontsize=8.5, fontweight="bold")

    out = work_path(f"financial_daily_dashboard_{meta.get('DATE_STR', '2026-01-01')}.png")
    plt.savefig(out, dpi=100, bbox_inches="tight", facecolor=NAVY, edgecolor="none")
    plt.close(fig)
    print(f"OK PNG: {out}")
    print(f"OK PNG: {publish(out)}")


if __name__ == "__main__":
    main()
