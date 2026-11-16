# market_data.json — schema v3.2

`fetch_market_data.py` crea il file (Layer 1: ECB, ANSA), la sessione lo completa
(Layer 2: web_search) e `report_full_pipeline.py` lo legge.

**Compatibilità:** tutte le chiavi marcate *v3.2* sono opzionali. Se mancano,
il PDF viene generato comunque e la lacuna compare in **NOTE QUALITÀ DATI**
(nessun contenuto statico scaduto viene stampato al loro posto).

## Formato dei valori

- Preferire **numeri JSON** (`3.41`, `-0.37`, `4050.5`) alle stringhe: nessuna ambiguità.
- Le stringhe sono accettate (`"3.41%"`, `"+0,84%"`, `"$71.20"`, `"44.812"`).
  Una stringa ambigua — es. prezzo `"$4.050"` (4,05 o 4.050?) — **non viene interpretata**:
  resta invariata e genera una nota qualità.
- Valore mancante: `"N/D"`.
- I decimali della fonte vengono conservati (ECB EUR/GBP `0.83559` → `0,83559`).

## Chiavi esistenti (v3.0)

| Blocco | Chiavi |
|---|---|
| `meta` | `DATE_REPORT`, `DATE_CHIUSURA`, `DATE_STR` (ISO `YYYY-MM-DD`, usata per filtrare agenda e riunioni) |
| `indices` | `FTSE_MIB`, `DAX`, `CAC40`, `EUROSTOXX50`, `SP500`, `NASDAQ`, `DJI` + `<KEY>_DELTA` (variazione %) |
| `bonds` | `BTP_10Y`, `BUND_10Y`, `OAT_10Y`, `UST_2Y`, `UST_5Y`, `UST_10Y`, `UST_30Y` (rendimento %), `SPREAD_BTP_BUND`, `CDS_ITALIA_5Y` (bp) |
| `forex` | `EUR_USD`, `EUR_JPY`, `EUR_GBP`, `EUR_CHF`, `USD_JPY`, `ECB_DATE` (dal fetch ECB) |
| `commodities` | `BRENT`, `WTI`, `NAT_GAS`, `GOLD`, `SILVER` + `<KEY>_DELTA` (variazione %) |
| `volatility` | `VIX` |
| `macro` | `CPI_USA`, `CPI_CORE`, `PPI_USA`, `HICP_EZ`, `CPI_ITA`, `PIL_USA_Q1`, `PIL_EZ_Q1`, `FED_RATE`, `BCE_RATE` |
| `headlines` | lista di titoli ANSA Economia (dal fetch) |
| `errors` | lista di avvisi (dal fetch e dalla sessione) |

## Chiavi nuove (v3.2, opzionali)

| Chiave | Tipo | Uso nel PDF |
|---|---|---|
| `summary` | stringa (2-3 frasi, BLUF) | §00 Sintesi esecutiva |
| `comments` | `{"01": "...", …, "08": "..."}` | box [COMMENTO] in fondo alle sezioni 01-08 |
| `bonds.<KEY>_DELTA` | numero, **bp** (es. `-4`) | colonna Var. §02 e §07; soglia ±15 bp |
| `forex.<PAIR>_DELTA`, `forex.ECB_PREV_DATE` | numero, % | **calcolati dal fetch** (storico ECB 90 gg, T1) |
| `volatility.VIX_DELTA` | numero, punti | colonna Var. §07 |
| `macro.PIL_USA_PERIOD`, `macro.PIL_EZ_PERIOD` | stringa (es. `"Q3 2026, advance"`) | etichetta riga PIL in §05 |
| `central_banks` | lista di `{bank, rate, bias, next, source}` | §06; se assente: Fed dal calendario FOMC interno, BCE N/D |
| `agenda` | lista di `{date, date_end?, event, area, note}` (date ISO) | §10; gli eventi passati vengono scartati, i prossimi 3 FOMC aggiunti se mancano |
| `geo` | `{driver: str, items: [str]}` | §08, prima delle headline ANSA |
| `scenarios` | lista di `{name, prob, target?, condition}` | §09; `target` assente sul primo scenario = Brent −13%; se la somma ≠ 100% compare un avviso rosso |

## Soglie di anomalia applicate

| Dato | Soglia | Tipo |
|---|---|---|
| Indici azionari | \|Δ\| > 3% | variazione giornaliera |
| Commodity | \|Δ\| > 5% | variazione giornaliera |
| FX | \|Δ\| > 2% | variazione giornaliera |
| Rendimenti, spread, CDS | \|Δ\| > 15 bp | variazione giornaliera |
| Spread BTP-Bund | > 100 bp | livello |
| VIX | > 25 | livello |

Le celle oltre soglia sono evidenziate in ambra con asterisco e riassunte nel
riquadro **SEGNALI OLTRE SOGLIA** di §00.

## Esempio minimo delle chiavi v3.2

```json
{
  "summary": "FTSE MIB +0,8% sovraperforma l'Europa. Spread stabile a 73 bp. UST 10Y +18 bp.",
  "comments": {"01": "Milano positiva, Francoforte debole.", "02": "Curva UST in irripidimento."},
  "bonds": {"BTP_10Y_DELTA": -4, "BUND_10Y_DELTA": -2, "SPREAD_BTP_BUND_DELTA": -2},
  "volatility": {"VIX_DELTA": -0.9},
  "macro": {"PIL_USA_PERIOD": "Q3 2026, advance"},
  "central_banks": [
    {"bank": "Fed", "rate": "3.75-4.00%", "bias": "Hold", "next": "8-9 dic 2026*", "source": "Fed.gov (T1)"}
  ],
  "agenda": [{"date": "2026-12-08", "date_end": "2026-12-09", "event": "FOMC", "area": "USA", "note": "SEP + dot plot"}],
  "geo": {"driver": "…", "items": ["… (fonti confermano)"]},
  "scenarios": [
    {"name": "A - …", "prob": 40, "condition": "…"},
    {"name": "B - …", "prob": 50, "target": "Laterale", "condition": "…"},
    {"name": "C - …", "prob": 10, "target": ">$140", "condition": "…"}
  ]
}
```

## Manutenzione

- `report_full_pipeline.py` contiene il calendario FOMC 2026 (`FOMC`). Da fine
  dicembre 2026 è esaurito: il PDF lo segnala nelle note qualità finché non si
  inseriscono le date 2027 (o la sessione non le passa in `agenda`).
