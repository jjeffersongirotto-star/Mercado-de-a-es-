#!/usr/bin/env python3
"""Métricas por ticker para os Grupos (a partir do histórico mensal do Yahoo, range=max, com dividendos e desdobramentos):
ret{n}: variação % do preço em n anos (1..5) · dy{n}: proventos médios por ano nos últimos n anos ÷ preço atual (%)
prov12: proventos 12m ÷ preço (%) + bonificações 12m (%) · anual: proventos por ano (5 anos fechados) ÷ preço médio do ano (%)
vol: volume financeiro médio por pregão (B3) no dia, 10 pregões e 1, 2, 3, 6, 9 e 12 meses (chaves dos campos do servidor).
ytd: eventos do ano corrente [data-com, valor/ação, tipo, rótulo]. Preços: B3 COTAHIST (ajustados por desdobramentos/grupamentos/bonificações da B3).
Proventos: B3 (últimos ~12 meses, com tipo JCP/Dividendo) e Yahoo antes disso (dividendos+JCP somados).
Uso: build_metrics.py OUT_DIR  (grava OUT_DIR/metrics.json). DATA_JSON = /api/data local (senão baixa do app)."""
import gzip, json, os, sys, time
from datetime import datetime, timezone
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import universe
from snaputil import APP_API

out = sys.argv[1]
HIST = os.environ.get("HIST_DIR") or os.path.join(out, "history4")
if os.environ.get("DATA_JSON"):
    rows = json.load(open(os.environ["DATA_JSON"]))["rows"]
else:
    rows = []
    for _ in range(10):
        d = requests.get(APP_API, timeout=120).json()
        rows = d.get("rows") or []
        if rows:
            break
        time.sleep(20)
kept = universe.tradable(rows)  # todas as classes negociadas
now = datetime.now(timezone.utc); Y = now.year
res, fail = {}, 0
for r in kept:
    t = r["ticker"]
    try:
        # Fonte: histórico oficial da B3 (COTAHIST, ajustado por eventos) gerado por build_cotahist.py
        H = json.loads(gzip.decompress(open(os.path.join(HIST, t + ".json.gz"), "rb").read()))
        pts = [(a, b) for a, b in zip(H["d"]["t"], H["d"]["c"]) if b]
        if len(pts) < 2:
            raise ValueError("vazio")
        divs = [(a, b) for a, b, *_ in H["divs"]]
        vols = [(a, b) for a, b in zip(H["d"]["t"], H["d"].get("vol") or []) if b is not None]
        lab = {a: (x[2] if len(x) > 2 else "") for a, *x in [[d[0], d[1], d[2] if len(d) > 2 else ""] for d in H["divs"]]}
        spl = [(a, m_, l_) for a, m_, l_ in H.get("splits", [])]
        x = {"meta": {}}
        p = pts[-1][1]; tnow = pts[-1][0]
        ftd = (x.get("meta") or {}).get("firstTradeDate") or pts[0][0]
        m = {"p": round(p, 2), "first": datetime.fromtimestamp(pts[0][0], timezone.utc).strftime("%Y-%m"),
             "ftd": datetime.fromtimestamp(ftd, timezone.utc).strftime("%Y-%m-%d"),              "mc0": None, "mc": None}
        mm = {}
        for ts, c in pts: mm[datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m")] = c
        ks = sorted(mm); m["mc0"] = ks[0]; m["mc"] = [round(mm[k], 2) for k in ks]
        dnow = datetime.fromtimestamp(tnow, timezone.utc)
        def back(years=0, months=0):  # mesma data do calendário, n anos/meses antes
            y, mo = dnow.year - years, dnow.month - months
            while mo < 1: mo += 12; y -= 1
            import calendar
            return dnow.replace(year=y, month=mo, day=min(dnow.day, calendar.monthrange(y, mo)[1])).timestamp()
        for n in range(1, 6):
            b = back(years=n)
            old = [c for ts, c in pts if ts <= b]  # último fechamento até a data de n anos atrás
            m[f"ret{n}"] = round((p / old[-1] - 1) * 100, 2) if old else None
            if old:
                s = sum(v for ts, v in divs if ts > b)
                m[f"dy{n}"] = round(s / n / p * 100, 2)
        avg = lambda w: round(sum(w) / len(w)) if w else None
        vol = {"voldia": avg([b for a, b in vols[-1:]]), "vol10": avg([b for a, b in vols[-10:]])}
        for k, n in (("vol30", 1), ("liq2m", 2), ("vol90", 3), ("vol6m", 6), ("vol9m", 9), ("vol12m", 12)):
            vol[k] = avg([b for a, b in vols if a > back(months=n)])
        m["vol"] = {k: x for k, x in vol.items() if x is not None}
        for n in (1, 2, 3, 6, 9):  # média simples dos fechamentos diários dos últimos n meses
            w = [c for ts, c in pts if ts > back(months=n)]
            m[f"avg{n}"] = round(sum(w) / len(w), 2) if w else None
        d12 = sum(v for ts, v in divs if ts > back(years=1))
        b12 = sum((rt - 1) * 100 for ts, rt, l_ in spl if ts > back(years=1) and l_.startswith("BONIF"))  # bonificações (B3)
        m["prov12"] = round(d12 / p * 100 + b12, 2)
        an = {}
        for y in range(Y - 5, Y):
            cl = [c for ts, c in pts if datetime.fromtimestamp(ts, timezone.utc).year == y]
            dv = sum(v for ts, v in divs if datetime.fromtimestamp(ts, timezone.utc).year == y)
            if cl:
                an[str(y)] = round(dv / (sum(cl) / len(cl)) * 100, 3)
        m["anual"] = an
        LB = {"JRS CAP PROPRIO": "JCP", "DIVIDENDO": "Dividendo", "RENDIMENTO": "Rendimento"}
        m["ytd"] = [[datetime.fromtimestamp(ts, timezone.utc).strftime("%d/%m/%Y"), round(v, 4), "provento", LB.get(lab.get(ts, ""), "")] for ts, v in divs if datetime.fromtimestamp(ts, timezone.utc).year == Y] + \
                   [[datetime.fromtimestamp(ts, timezone.utc).strftime("%d/%m/%Y"), round(rt, 4), "bonificação" if l_.startswith("BONIF") else "desdobramento" if rt > 1 else "grupamento"] for ts, rt, l_ in spl if datetime.fromtimestamp(ts, timezone.utc).year == Y]
        res[t] = m
    except Exception as e:
        fail += 1
json.dump({"fetched_at": now.isoformat(), "metrics": res}, open(os.path.join(out, "metrics.json"), "w"), separators=(",", ":"))
print(f"métricas: {len(res)} ok, {fail} falhas")
