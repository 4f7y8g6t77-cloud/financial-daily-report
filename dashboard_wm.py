#!/usr/bin/env python3
"""
dashboard_wm.py - Dashboard PNG 4 pannelli v3.0
Input:  /home/claude/market_data.json
Output: /home/claude/financial_daily_dashboard_{DATE_STR}.png (1920x1080)
"""
import json, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

with open("/home/claude/market_data.json", "r", encoding="utf-8") as f:
    mkt = json.load(f)

meta  = mkt.get("meta", {}); forex = mkt.get("forex", {})
idx   = mkt.get("indices", {}); bonds = mkt.get("bonds", {})
comm  = mkt.get("commodities", {}); vol = mkt.get("volatility", {})

DATE_REPORT   = meta.get("DATE_REPORT",   "N/D")
DATE_CHIUSURA = meta.get("DATE_CHIUSURA", "N/D")
DATE_STR      = meta.get("DATE_STR",      "2026-01-01")

NAVY="#0B2545"; GOLD="#C9A84C"; GREEN="#1A8A4A"; RED="#C0392B"; AMBER="#E07B00"; WHITE="#FFFFFF"; GREY="#6C7A89"

def sf(d, k):
    val = d.get(k)
    if val is None or val == "N/D": return None
    try: return float(str(val).replace("%","").replace("+","").replace(",",".").replace("$","").replace("bp",""))
    except: return None

def bc(val): return GREEN if val is not None and val >= 0 else RED

fig = plt.figure(figsize=(19.2,10.8), facecolor=NAVY)
gs  = GridSpec(2,2,figure=fig,hspace=0.38,wspace=0.30,left=0.05,right=0.97,top=0.88,bottom=0.08)
fig.text(0.5,0.95,f"FINANCIAL DAILY REPORT  -  Chiusura {DATE_CHIUSURA}",ha="center",fontsize=15,fontweight="bold",color=WHITE,fontfamily="monospace")
fig.text(0.5,0.91,f"Report: {DATE_REPORT}",ha="center",fontsize=10,color=GOLD,fontfamily="monospace")

# Pannello 1: Indici
ax1 = fig.add_subplot(gs[0,0]); ax1.set_facecolor("#0D1B2A")
ind_d = [("FTSE MIB",sf(idx,"FTSE_MIB_DELTA")),("DAX",sf(idx,"DAX_DELTA")),
         ("CAC 40",sf(idx,"CAC40_DELTA")),("S&P 500",sf(idx,"SP500_DELTA")),
         ("Nasdaq",sf(idx,"NASDAQ_DELTA")),("DJI",sf(idx,"DJI_DELTA"))]
lb1=[x[0] for x in ind_d]; v1=[x[1] if x[1] is not None else 0 for x in ind_d]; c1=[bc(x[1]) for x in ind_d]
bars1=ax1.bar(lb1,v1,color=c1,width=0.6,edgecolor=NAVY,linewidth=0.5)
ax1.axhline(y=0,color=GOLD,linewidth=0.8,linestyle="--",alpha=0.7)
ax1.set_title("INDICI AZIONARI",color=GOLD,fontsize=10,fontweight="bold",pad=8)
ax1.tick_params(colors=WHITE,labelsize=7.5)
for sp in ["top","right","left"]: ax1.spines[sp].set_visible(False)
ax1.spines["bottom"].set_color(GOLD)
for bar,val in zip(bars1,v1):
    ax1.text(bar.get_x()+bar.get_width()/2,bar.get_height()+(0.05 if val>=0 else -0.15),
             f"{val:+.2f}%",ha="center",va="bottom" if val>=0 else "top",color=WHITE,fontsize=7,fontweight="bold")

# Pannello 2: Bond
ax2 = fig.add_subplot(gs[0,1]); ax2.set_facecolor("#0D1B2A")
bl=["BTP 10Y","Bund 10Y","OAT 10Y","UST 2Y","UST 10Y","UST 30Y"]
bv=[sf(bonds,"BTP_10Y"),sf(bonds,"BUND_10Y"),sf(bonds,"OAT_10Y"),sf(bonds,"UST_2Y"),sf(bonds,"UST_10Y"),sf(bonds,"UST_30Y")]
bp=[v if v is not None else 0 for v in bv]; bcc=["#4FC3F7" if v is not None else GREY for v in bv]
bars2=ax2.bar(bl,bp,color=bcc,width=0.6,edgecolor=NAVY,linewidth=0.5)
ax2.set_title("RENDIMENTI OBBLIGAZIONARI (%)",color=GOLD,fontsize=10,fontweight="bold",pad=8)
ax2.tick_params(colors=WHITE,labelsize=7.5)
for sp in ["top","right","left"]: ax2.spines[sp].set_visible(False)
ax2.spines["bottom"].set_color(GOLD)
sp_val=sf(bonds,"SPREAD_BTP_BUND")
if sp_val: ax2.text(0.98,0.95,f"Spread: {sp_val:.0f}bp",transform=ax2.transAxes,ha="right",va="top",color=AMBER if sp_val>100 else GREEN,fontsize=8.5,fontweight="bold")
for bar,val in zip(bars2,bv):
    ax2.text(bar.get_x()+bar.get_width()/2,bar.get_height()+0.03,f"{val:.2f}%" if val is not None else "N/D",ha="center",va="bottom",color=WHITE,fontsize=7,fontweight="bold")

# Pannello 3: Commodities
ax3 = fig.add_subplot(gs[1,0]); ax3.set_facecolor("#0D1B2A")
cd=[("Brent",sf(comm,"BRENT_DELTA")),("WTI",sf(comm,"WTI_DELTA")),("Gold",sf(comm,"GOLD_DELTA")),("Silver",sf(comm,"SILVER_DELTA")),("NatGas",sf(comm,"NAT_GAS_DELTA"))]
lb3=[x[0] for x in cd]; v3=[x[1] if x[1] is not None else 0 for x in cd]; c3=[bc(x[1]) for x in cd]
bars3=ax3.bar(lb3,v3,color=c3,width=0.6,edgecolor=NAVY,linewidth=0.5)
ax3.axhline(y=0,color=GOLD,linewidth=0.8,linestyle="--",alpha=0.7)
ax3.axhline(y=5,color=AMBER,linewidth=0.5,linestyle=":",alpha=0.5); ax3.axhline(y=-5,color=AMBER,linewidth=0.5,linestyle=":",alpha=0.5)
ax3.set_title("COMMODITIES (Delta% giornaliero)",color=GOLD,fontsize=10,fontweight="bold",pad=8)
ax3.tick_params(colors=WHITE,labelsize=7.5)
for sp in ["top","right","left"]: ax3.spines[sp].set_visible(False)
ax3.spines["bottom"].set_color(GOLD)
for bar,val in zip(bars3,v3):
    ax3.text(bar.get_x()+bar.get_width()/2,bar.get_height()+(0.1 if val>=0 else -0.2),f"{val:+.2f}%",ha="center",va="bottom" if val>=0 else "top",color=WHITE,fontsize=7,fontweight="bold")

# Pannello 4: Scenari
ax4 = fig.add_subplot(gs[1,1]); ax4.set_facecolor("#0D1B2A")
try:
    ax4.pie([40,45,10],labels=["A: De-esc.","B: Stallo","C: Esc."],colors=[GREEN,"#4FC3F7",RED],
            autopct="%1.0f%%",startangle=90,textprops={"color":WHITE,"fontsize":9},
            wedgeprops={"edgecolor":NAVY,"linewidth":1.5})
    ax4.set_title("SCENARI PROBABILISTICI",color=GOLD,fontsize=10,fontweight="bold",pad=8)
    vix=sf(vol,"VIX"); eur=sf(forex,"EUR_USD"); br=sf(comm,"BRENT")
    info=f"VIX: {vix:.1f}  " if vix else "VIX: N/D  "
    info+=f"EUR/USD: {eur:.4f}  " if eur else "EUR/USD: N/D  "
    info+=f"Brent: ${br:.1f}" if br else "Brent: N/D"
    fig.text(0.75,0.06,info,ha="center",color=GOLD,fontsize=8.5,fontweight="bold")
except: ax4.text(0.5,0.5,"Scenari N/D",ha="center",va="center",transform=ax4.transAxes,color=WHITE,fontsize=12)

for out in [f"/home/claude/financial_daily_dashboard_{DATE_STR}.png",
            f"/mnt/user-data/outputs/financial_daily_dashboard_{DATE_STR}.png"]:
    plt.savefig(out,dpi=100,bbox_inches="tight",facecolor=NAVY,edgecolor="none")
    print(f"OK PNG: {out}")
plt.close()
