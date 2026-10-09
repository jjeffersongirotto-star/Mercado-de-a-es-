#!/usr/bin/env python3
"""Gera data/yfinance.json (3ª fonte do desempate) para os tickers com divergência grosseira.
Rode numa máquina onde o Yahoo não bloqueia; usado por scripts/push_snapshot_from_here.sh.
Requer as dependências do app (pandas, lxml, yfinance...). Uso: fetch_yfinance.py [pasta_saida]"""
import json, os, sys
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import server, tiebreak  # noqa: E402

out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data")
os.makedirs(out_dir, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from snaputil import app_api_data  # noqa: E402

def base_from_app():
    """Base (linhas por liquidez com 'div' Fundamentus × Status Invest) a partir da API do app no Render,
    usada quando o Fundamentus bloqueia esta máquina. Recalcula 'div' com a mesma regra do server.build()."""
    rows = []
    for r in app_api_data()["rows"]:
        S = r.get("S") or {}; f = S.get("fund") or {}; s = S.get("si") or {}
        div = {}
        for key, *_x, absthr, cmp in server.FIELDS:
            fv, sv = f.get(key), s.get(key)
            if cmp and fv is not None and sv is not None and server.divergente(fv, sv, absthr): div[key] = [fv, sv]
        rows.append({"ticker": r["ticker"], "div": div})
    return {"rows": rows}

try:
    base = server.build()
except Exception as e:
    print(f"server.build() falhou ({type(e).__name__}: {str(e)[:120]}); usando a API do app no Render", file=sys.stderr)
    base = base_from_app()
need = tiebreak.tickers_needing(base["rows"])
store = tiebreak.YFStore(os.environ.get("YF_STORE", os.path.join(ROOT, "cache", "yfinance.json")))
ok, fail, blocked, msg = tiebreak.run_fetch(store, need)
if blocked:
    print(f"Falhou: {msg}", file=sys.stderr); sys.exit(1)
tick = {t: store.get(t) for t in need if store.has(t)}  # None = Yahoo sem dado para o ticker
with_data = sum(1 for v in tick.values() if v)
if with_data < max(10, len(need) // 3):
    print(f"Poucos dados ({with_data}/{len(need)}); não sobrescrevendo", file=sys.stderr); sys.exit(1)
snap = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tickers": tick,
        "fields": {k: f for k, (f, _) in tiebreak.YF_MAP.items()}}
with open(os.path.join(out_dir, "yfinance.json"), "w", encoding="utf-8") as f:
    json.dump(snap, f, ensure_ascii=False, separators=(",", ":"))
print(json.dumps({"fetched_at": snap["fetched_at"], "tickers": len(tick), "with_data": with_data, "needed": len(need), "msg": msg}))
