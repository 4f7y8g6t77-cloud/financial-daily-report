# financial-daily-report
Pipeline del report finanziario giornaliero (v3.1).

## Flusso
1. `fetch_market_data.py` raccoglie in automatico dati T1: BCE (cambi + variazione sulla seduta precedente), FRED (UST, VIX, S&P/Nasdaq/Dow, Brent/WTI/gas, Fed, BCE) e i titoli ANSA.
2. `merge_supplement.py` integra il supplemento (`supplement.json`), cioè dati raccolti via Bigdata.com o altre fonti, ciascuno con fonte, tier e data della seduta, più il contesto (geopolitica, scenari, banche centrali, agenda, raccomandazioni WM).
3. `report_full_pipeline.py` genera il PDF (output di default).
4. `dashboard_wm.py` genera la dashboard PNG; `wm_appendix.py` genera l'allegato WM in PDF e l'XLSX. Entrambi solo su richiesta.

## Uso
```bash
./run_pipeline.sh --supplement supplement.json               # solo PDF
./run_pipeline.sh --supplement supplement.json --all         # PDF + PNG + WM + XLSX
./run_pipeline.sh --skip-fetch --supplement supplement.json  # riusa market_data.json
```
Variabili d'ambiente: `FDR_WORK_DIR` (default `/home/claude`), `FDR_OUTPUT_DIR` (default `/mnt/user-data/outputs`). Le cartelle vengono create se non esistono.

Formato del supplemento: vedi `supplement.example.json`.

## Regole di merge (Protocollo Fonti)
- Un campo N/D viene riempito con il valore del supplemento.
- Se le sessioni sono diverse, vince la più recente; il delta della vecchia sessione viene azzerato a N/D.
- Se la sessione è la stessa, resta il tier più alto. Una divergenza oltre la soglia A genera un flag amber, senza fare medie.
- Lo spread BTP-Bund viene calcolato solo se i due rendimenti sono della stessa sessione.
- Le variazioni giornaliere anomale (soglia B) generano un flag amber.
- Gli scenari devono sommare al 100%, altrimenti la pipeline si ferma con errore (exit code 2).

## Test
```bash
python3 -m pytest -q tests
```
