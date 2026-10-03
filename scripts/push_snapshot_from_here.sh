#!/bin/bash
# Atualiza os snapshots da branch `data` (Status Invest + yfinance/desempate) a partir de uma máquina
# cujo IP NÃO é bloqueado (ex.: seu PC ou a máquina da rotina diária). Requer git com permissão de push.
# Não dispara deploy no Render (branch data).
# PYTHON: interpretador com as dependências do app (pandas, lxml, yfinance) para o snapshot do yfinance.
set -e
REPO_URL="${REPO_URL:-https://github.com/jjeffersongirotto-star/Mercado-de-a-es-.git}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x /workspace/b3-api/.venv/bin/python ]; then PY=/workspace/b3-api/.venv/bin/python; else PY=python3; fi
fi
TMP="$(mktemp -d)"
git clone -q --depth 1 --branch data "$REPO_URL" "$TMP" 2>/dev/null || { git -C "$TMP" init -q -b data; git -C "$TMP" remote add origin "$REPO_URL"; }
MSG=()
if python3 "$HERE/scripts/fetch_statusinvest.py" "$TMP/data"; then MSG+=("Status Invest"); else echo "AVISO: snapshot Status Invest falhou" >&2; fi
if "$PY" "$HERE/scripts/fetch_yfinance.py" "$TMP/data"; then MSG+=("yfinance"); else echo "AVISO: snapshot yfinance falhou" >&2; fi
[ ${#MSG[@]} -eq 0 ] && { echo "Nenhum snapshot gerado" >&2; exit 1; }
cd "$TMP" && git add data && (git diff --cached --quiet || git -c user.name="${GIT_NAME:-jjeffersongirotto-star}" -c user.email="${GIT_EMAIL:-jjeffersongirotto-star@users.noreply.github.com}" commit -q -m "Snapshot ${MSG[*]} $(date -u +%Y-%m-%dT%H:%MZ)") && git push -q origin data
echo "Snapshot publicado na branch data: ${MSG[*]}."
