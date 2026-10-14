#!/bin/bash
# Atualiza TODOS os snapshots da branch `data` a partir de uma máquina cujo IP NÃO é bloqueado
# (rotina diária 19:05). Roda em sequência, com taxa baixa (~1 req/s nos sites por ticker).
# Requer git com permissão de push. Não dispara deploy no Render (branch data).
#   Status Invest (CSV)  · Yahoo (desempate)   · TradingView (todos os países, fallback)
#   Investidor10 (~1 req/s, ~1000 páginas)     · Dados de Mercado (~1 req/2,5 s, ~300 páginas)
#   CVM dados abertos (DFP/ITR, pré-processado: data/cvm.json compacto)
#   Histórico (Yahoo 20a mensal/5a diário + Ibovespa + BCB) e perfis (brapi) do universo exibido
#   Índice de Medo e Ganância (B3: COTAHIST, fluxo, CDI) · Sinais dos modelos da Previsão · Base do chat (resumos da Wikipedia dos itens do conhecimento.json; renova uma vez por semana)
# ONLY="cvm tradingview" limita as etapas; PYTHON = interpretador com pandas/lxml/yfinance/requests.
set -e
REPO_URL="${REPO_URL:-https://github.com/jjeffersongirotto-star/Mercado-de-a-es-.git}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x /workspace/b3-api/.venv/bin/python ]; then PY=/workspace/b3-api/.venv/bin/python; else PY=python3; fi
fi
STEPS="${ONLY:-statusinvest yfinance tradingview cvm investidor10 dadosdemercado b3indices b3cad b3btb vol30 cotahist history metrics fg modelos kb}"
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
    b3indices)      run "Índices B3" "$PY" "$HERE/scripts/fetch_b3_indices.py" "$TMP/data" ;;
    b3cad)          run "Cadastro B3" "$PY" "$HERE/scripts/fetch_b3_cadastro.py" "$TMP/data" ;;
    b3btb)          run "Aluguel e fluxo B3" "$PY" "$HERE/scripts/fetch_b3_btb.py" "$TMP/data" ;;
    vol30)          run "Volume 30 pregões B3" "$PY" "$HERE/scripts/build_vol30.py" "${COTA_DIR:-/workspace/scratch/cotahist}" "$TMP/data" ;;
    cotahist)       run "B3 COTAHIST" "$PY" "$HERE/scripts/build_cotahist.py" "${COTA_DIR:-/workspace/scratch/cotahist}" "$TMP/data" ;;
    metrics)        run "Métricas Grupos" "$PY" "$HERE/scripts/build_metrics.py" "$TMP/data" ;;
    dadosdemercado) run "Dados de Mercado" "$PY" "$HERE/scripts/fetch_dadosdemercado.py" "$TMP/data" ;;
    fg)             run "Medo e Ganância" "$PY" "$HERE/scripts/build_fg.py" "$TMP/data" ;;
    modelos)        run "Modelos da Previsão" "$PY" "$HERE/scripts/build_modelos.py" "$TMP/data" ;;
    kb)             run "Base do chat" "$PY" "$HERE/scripts/build_kb.py" "$TMP/data" ;;
  esac
done
[ -n "$(ls "$TMP/data/history4" 2>/dev/null | head -1)" ] && "$PY" "$HERE/scripts/build_closes_bundle.py" "$TMP/data"
# Prioridade B3: com o histórico COTAHIST publicado, apaga o histórico Yahoo das ações brasileiras (fica só o Ibovespa)
if [ -n "$(ls "$TMP/data/history4" 2>/dev/null | head -1)" ]; then
  for d in history history2 history3; do [ -d "$TMP/data/$d" ] && find "$TMP/data/$d" -type f ! -name 'IBOV*' ! -name 'gold*' ! -name 'bcb_*' -delete; done
fi
[ ${#MSG[@]} -eq 0 ] && { echo "Nenhum snapshot gerado" >&2; exit 1; }
cd "$TMP" && git add -A data && (git diff --cached --quiet || git -c user.name="${GIT_NAME:-jjeffersongirotto-star}" -c user.email="${GIT_EMAIL:-jjeffersongirotto-star@users.noreply.github.com}" commit -q -m "Snapshot ${MSG[*]} $(date -u +%Y-%m-%dT%H:%MZ)")
# A rotina leva mais de 1 h; nesse tempo outra gravação (registro do chat, Status Invest) pode entrar na branch data:
# traz o que entrou e reaplica o snapshot por cima antes de gravar (até 4 tentativas).
for i in 1 2 3 4; do
  git push -q origin data && break
  [ $i -eq 4 ] && { echo "Não foi possível gravar na branch data" >&2; exit 1; }
  git fetch -q origin data && git -c user.name="${GIT_NAME:-jjeffersongirotto-star}" -c user.email="${GIT_EMAIL:-jjeffersongirotto-star@users.noreply.github.com}" rebase -q -X theirs origin/data || { git rebase --abort; exit 1; }
  sleep $((i * 5))
done
echo "Snapshot publicado na branch data: ${MSG[*]}."
