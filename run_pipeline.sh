#!/usr/bin/env bash
# run_pipeline.sh - Financial Daily Report v3.1
#
# Uso:
#   ./run_pipeline.sh [--date-report DD/MM/YYYY] [--date-chiusura DD/MM/YYYY]
#                     [--supplement FILE] [--dashboard] [--wm] [--all] [--skip-fetch]
#
# Default: solo PDF (financial_daily_report_{DATE}.pdf).
#   --dashboard  aggiunge dashboard PNG
#   --wm         aggiunge WM appendix PDF + XLSX dati
#   --all        tutti gli output
#   --skip-fetch riusa market_data.json esistente (es. dopo correzioni al supplemento)
#
# Env: FDR_WORK_DIR (default /home/claude), FDR_OUTPUT_DIR (default /mnt/user-data/outputs)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"

FETCH_ARGS=(); SUPPLEMENT=""; DASH=0; WM=0; SKIP_FETCH=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --date-report|--date-chiusura) FETCH_ARGS+=("$1" "$2"); shift 2 ;;
    --supplement) SUPPLEMENT="$2"; shift 2 ;;
    --dashboard) DASH=1; shift ;;
    --wm) WM=1; shift ;;
    --all) DASH=1; WM=1; shift ;;
    --skip-fetch) SKIP_FETCH=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Argomento sconosciuto: $1" >&2; exit 64 ;;
  esac
done

cd "$HERE"
if [[ $SKIP_FETCH -eq 0 ]]; then
  "$PY" fetch_market_data.py "${FETCH_ARGS[@]+"${FETCH_ARGS[@]}"}"
fi
if [[ -n "$SUPPLEMENT" ]]; then
  "$PY" merge_supplement.py "$SUPPLEMENT"
else
  "$PY" merge_supplement.py
fi
"$PY" report_full_pipeline.py
[[ $DASH -eq 1 ]] && "$PY" dashboard_wm.py
[[ $WM -eq 1 ]] && "$PY" wm_appendix.py
echo "Pipeline completata."
