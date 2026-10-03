#!/bin/bash
# Atualiza o snapshot da branch `data` a partir de uma máquina cujo IP NÃO é bloqueado pelo Status Invest
# (ex.: seu PC). Requer git com permissão de push no repositório. Não dispara deploy no Render (branch data).
set -e
REPO_URL="${REPO_URL:-https://github.com/jjeffersongirotto-star/Mercado-de-a-es-.git}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
git clone -q --depth 1 --branch data "$REPO_URL" "$TMP" 2>/dev/null || { git -C "$TMP" init -q -b data; git -C "$TMP" remote add origin "$REPO_URL"; }
python3 "$HERE/scripts/fetch_statusinvest.py" "$TMP/data"
cd "$TMP" && git add data && (git diff --cached --quiet || git commit -q -m "Snapshot Status Invest $(date -u +%Y-%m-%dT%H:%MZ)") && git push -q origin data
echo "Snapshot publicado na branch data."
