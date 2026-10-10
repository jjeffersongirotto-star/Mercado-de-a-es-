#!/bin/bash
# Atualiza TODOS os snapshots da branch `data` a partir de uma máquina cujo IP NÃO é bloqueado
# (rotina diária 19:05). Roda em sequência, com taxa baixa (~1 req/s nos sites por ticker).
# Requer git com permissão de push. Não dispara deploy no Render (branch data).
#   Status Invest (CSV)  · Yahoo (desempate)   · TradingView (todos os países, fallback)
#   Investidor10 (~1 req/s, ~1000 páginas)     · Dados de Mercado (~1 req/2,5 s, ~300 páginas)
#   CVM dados abertos (DFP/ITR, pré-processado: data/cvm.json compacto)
#   Histórico (Yahoo 20a mensal/5a diário + Ibovespa + BCB) e perfis (brapi) do universo exibido
# ONLY="cvm tradingview" limita as etapas; PYTHON = interpretador com pandas/lxml/yfinance/requests.
set -e
REPO_URL="${REPO_URL:-https://github.com/jjeffersongirotto-star/Mercado-de-a-es-.git}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x /workspace/b3-api/.venv/bin/python ]; then PY=/workspace/b3-api/.venv/bin/python; else PY=python3; fi
fi
STEPS="${ONLY:-statusinvest yfinance tradingview cvm investidor10 dadosdemercado history metrics}"
TMP="$(mktemp -d)"
git clone -q --depth 1 --branch data "$REPO_URL" "$TMP" 2>/dev/null || { git -C "$TMP" init -q -b data; git -C "$TMP" remote add origin "$REPO_URL"; }
mkdir -p "$TMP/data"
MSG=()
run() {  # nome, comando...
  local n="$1"; shift
  echo "== $n ($(date +%H:%M:%S))"
  if "$@"; then MSG+=("$n"); else echo "AVISO: snapshot $n falhou" >&2; fi
}
for s in $STEPS; do
  case "$s" in
    statusinvest)   run "Status Invest"    python3 "$HERE/scripts/fetch_statusinvest.py" "$TMP/data" ;;
    yfinance)       run "yfinance"         "$PY" "$HERE/scripts/fetch_yfinance.py" "$TMP/data" ;;
    tradingview)    run "TradingView"      "$PY" "$HERE/scripts/fetch_tradingview.py" "$TMP/data" ;;
    cvm)            run "CVM"              "$PY" "$HERE/scripts/build_cvm.py" "$TMP/data" "${CVM_CACHE:-/tmp/cvmraw}" ;;
    investidor10)   run "Investidor10"     "$PY" "$HERE/scripts/fetch_investidor10.py" "$TMP/data" ;;
    history)        run "Histórico+perfis" "$PY" "$HERE/scripts/fetch_history.py" "$TMP/data" ;;
    metrics)        run "Métricas Grupos" "$PY" "$HERE/scripts/build_metrics.py" "$TMP/data" ;;
    dadosdemercado) run "Dados de Mercado" "$PY" "$HERE/scripts/fetch_dadosdemercado.py" "$TMP/data" ;;
  esac
done
[ ${#MSG[@]} -eq 0 ] && { echo "Nenhum snapshot gerado" >&2; exit 1; }
cd "$TMP" && git add data && (git diff --cached --quiet || git -c user.name="${GIT_NAME:-jjeffersongirotto-star}" -c user.email="${GIT_EMAIL:-jjeffersongirotto-star@users.noreply.github.com}" commit -q -m "Snapshot ${MSG[*]} $(date -u +%Y-%m-%dT%H:%MZ)") && git push -q origin data
echo "Snapshot publicado na branch data: ${MSG[*]}."
