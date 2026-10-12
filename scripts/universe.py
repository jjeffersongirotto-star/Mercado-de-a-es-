"""Universo exibido (fonte única da regra; o servidor marca cada linha de /api/data e o site e os scripts só leem as marcas).
Ilíquida: média diária negociada < R$ 50 mil nos últimos 30 pregões da B3 (snapshot b3_vol30, COTAHIST) ou sem negócios.
Bons resultados recentes (mantém mesmo ilíquida): LPA > 0, ROE >= 10% e crescimento do lucro 5a não negativo.
1 ticker por empresa (4 letras): classe mais negociada na B3 (30 pregões); sem volume 11 > 4 > 3 > 5 > 6;
classes 5/6/sufixo B/BDR só quando a empresa não tem 3/4/11.
Marcas: il = ilíquida sem bons resultados (sai da lista) · k1 = ticker escolhido da empresa (Grupos prontos, histórico)."""
import re

def illiquid(liq):
    return liq is None or liq < 50_000

def promising(r):
    v = r.get("v") or {}
    lpa, roe, l5 = v.get("lpa"), v.get("roe"), v.get("lucro5a")
    return lpa is not None and lpa > 0 and roe is not None and roe >= 10 and not (l5 is not None and l5 < 0)

def cls_rank(t):
    m = re.match(r"^[A-Z0-9]{4}(\d+)$", t)
    n = m.group(1) if m else ""
    return {"11": 0, "4": 1, "3": 2, "5": 3, "6": 4}.get(n, 5)

def mark(rows, liq):
    """liq = {ticker: volume financeiro médio dos últimos 30 pregões (B3)}. Grava r['il'] e r['k1']."""
    best = {}
    main = {r["ticker"][:4] for r in rows if cls_rank(r["ticker"]) < 5}
    for r in rows:
        r.pop("il", None); r.pop("k1", None)
        if illiquid(liq.get(r["ticker"])) and not promising(r):
            r["il"] = 1
            continue
        if cls_rank(r["ticker"]) == 5 and r["ticker"][:4] in main:
            continue
        k = r["ticker"][:4]
        key = (-(liq.get(r["ticker"]) or 0), cls_rank(r["ticker"]))
        if k not in best or key < best[k][0]:
            best[k] = (key, r)
    for _, r in best.values():
        r["k1"] = 1

def tradable(rows):
    """Todas as classes negociadas (sai só o papel ilíquido sem resultados promissores)."""
    return [r for r in rows if not r.get("il")]

def universe(rows):
    """1 ticker por empresa."""
    return [r for r in rows if r.get("k1")]
