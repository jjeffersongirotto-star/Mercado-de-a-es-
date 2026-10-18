#!/usr/bin/env python3
"""Comparar → Modelos pré-calculado -> OUT/modelos_pre.json (o servidor responde na hora quando o pedido bate exatamente).
Casos: Todas e 5 maiores de cada setor × 5/10/15/20 anos e todo o período, valores padrão (modelos.PRE_INI/PRE_AP), fim = dados mais recentes.
Mesma conta do site (modelos.compare) com os sinais recém-gerados (OUT/modelos.json), CDI e ouro do histórico, empresas de /api/data
do site e cadastro B3 (OUT/b3_cad.json). Cada resposta leva a chave de toda a entrada: se algo diferir no servidor, ele calcula ao vivo.
Uso: build_modelos_pre.py OUT_DIR"""
import json, os, sys, time
from datetime import datetime, timedelta, timezone
import requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import history, modelos, snapshots, universe  # noqa: E402


def main(out):
    t0 = time.time()
    snap = json.load(open(os.path.join(out, "modelos.json"), encoding="utf-8"))
    try: gold = history.gold()
    except Exception: gold = None
    D = modelos.build(snap, history.bcb("cdi"), gold); del snap
    url = snapshots.APP_URL.rstrip("/")
    rows = []
    for i in range(12):  # site pode estar acordando
        r = requests.get(f"{url}/api/data", timeout=120)
        rows = (r.json() or {}).get("rows") or [] if r.status_code == 200 else []
        if rows: break
        time.sleep(20)
    rows = universe.universe(rows)
    if not rows: raise SystemExit("sem empresas do site")
    p = os.path.join(out, "b3_cad.json")
    cad = (json.load(open(p, encoding="utf-8")) if os.path.exists(p) else snapshots.load("b3_cad")[0] or {}).get("c") or {}
    modelos.set_setores(D, rows, cad)
    hoje = datetime.now(timezone(timedelta(hours=-3)))
    df = hoje.strftime("%Y-%m")
    E = {}
    for u, tick in (("all", modelos.todas(D, rows)), ("top5", modelos.top_sector(rows))):
        for n in modelos.PRE_ANOS:
            di = f"{hoje.year - n:04d}-{hoje.month:02d}" if n else "1900-01"
            aps = [modelos.PRE_INI] + [modelos.PRE_AP] * 600
            res = modelos.compare(D, tick, di, df, aps)
            if res.get("error"): print("  ", u, n, res["error"]); continue
            me = modelos._span(D, di, df); a = (aps + [0.0] * len(me))[:len(me)]
            idx = [D["ix"][t] for t in dict.fromkeys(tick) if t in D["ix"] and not modelos.np.isnan(D["C"][D["ix"][t], me[0]])]
            E[modelos.pre_key(D, tick, idx, me, a)] = res
            print(f"   {u} {n or 'todo'}: {res['ini']}..{res['fim']} {len(res['t'])} empresas")
    o = {"fetched_at": datetime.now(timezone.utc).isoformat(), "fp": D["fp"], "e": E}
    with open(os.path.join(out, "modelos_pre.json"), "w", encoding="utf-8") as fh: json.dump(o, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"modelos_pre: {len(E)} casos, {os.path.getsize(os.path.join(out, 'modelos_pre.json')) // 1024} KB, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main(sys.argv[1])
