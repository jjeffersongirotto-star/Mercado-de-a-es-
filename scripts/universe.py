"""Universo exibido (mesma regra do app.js): 1 ticker por empresa e remoção de ilíquidas sem bons resultados.
Ilíquida: média diária negociada < R$ 50 mil (vol30 do TradingView; sem TV, liq2m do Fundamentus) ou liq2m = 0.
Bons resultados recentes (mantém mesmo ilíquida): LPA > 0, ROE >= 10% e crescimento do lucro 5a não negativo.
Classe preferida por empresa (4 letras): ON (3) > PN (4) > Unit (11) > demais; empate -> maior liquidez."""
import re

def illiquid(r):
    v = r.get("v") or {}
    liq = v.get("vol30") if v.get("vol30") is not None else v.get("liq2m")
    return (v.get("liq2m") or 0) <= 0 or liq is None or liq < 50_000

def promising(r):
    v = r.get("v") or {}
    lpa, roe, l5 = v.get("lpa"), v.get("roe"), v.get("lucro5a")
    return lpa is not None and lpa > 0 and roe is not None and roe >= 10 and not (l5 is not None and l5 < 0)

def cls_rank(t):
    m = re.match(r"^[A-Z0-9]{4}(\d+)$", t)
    n = m.group(1) if m else ""
    return {"11": 0, "4": 1, "3": 2, "5": 3, "6": 4}.get(n, 5)

def universe(rows):
    removed = [r["ticker"] for r in rows if illiquid(r) and not promising(r)]
    rem = set(removed)
    best = {}
    main = {r["ticker"][:4] for r in rows if cls_rank(r["ticker"]) < 5}
    for r in rows:
        if r["ticker"] in rem or (cls_rank(r["ticker"]) == 5 and r["ticker"][:4] in main):
            continue  # classes 5/6/sufixo B/BDR só quando a empresa não tem 3/4/11
        k = r["ticker"][:4]
        vv = r.get("v") or {}
        key = (-(vv.get("vol30") or 0), cls_rank(r["ticker"]), -(vv.get("liq2m") or 0))  # classe mais negociada (B3, 30 pregões); sem volume: 11>4>3>5>6
        if k not in best or key < best[k][0]:
            best[k] = (key, r)
    kept = [b[1] for b in best.values()]
    dups = sorted(r["ticker"] for r in rows if r["ticker"] not in rem and r not in kept)
    return kept, sorted(removed), dups


def tradable(rows):
    """Todas as classes negociadas; sai só o papel ilíquido sem resultados promissores (por ticker)."""
    return [r for r in rows if not (illiquid(r) and not promising(r))]
