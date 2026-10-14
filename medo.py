"""Comparar → Medo e Ganância: o que aconteceu com uma ação da B3 em cada faixa do Índice de Medo e Ganância (snapshot fg).
Tudo em base mensal (fechamento do mês da ação e índice no último pregão do mês), porque o histórico mensal da B3 vai
até os anos 1990 (o diário guardado no servidor tem 6 anos). Cálculo leve, feito na hora e guardado em memória por ticker/período."""
import time
from collections import OrderedDict
import history
import snapshots

_C = OrderedDict()


def _ym(ts):
    return time.strftime("%Y-%m", time.gmtime(ts))


def _fg():
    d = snapshots.load("fg", max_mem_age=3 * 3600)[0] or {}
    fim = {}
    for day, v in zip(d.get("d", []), d.get("v", [])): fim[day[:7]] = v  # último pregão de cada mês
    return fim, d.get("faixas") or [], (d["v"][-1] if d.get("v") else None), (d["d"][-1] if d.get("d") else None), d.get("fetched_at")


def _band(v, fx):
    return next((i for i, f in enumerate(fx) if v <= f[0]), len(fx) - 1)


def _avg(x):
    return round(sum(x) / len(x), 2) if x else None


def _add(ym, n):
    y, m = int(ym[:4]), int(ym[5:7]) + n
    y += (m - 1) // 12; m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def analyze(t, di, df):
    fim, fx, now, now_d, at = _fg()
    if not fim: raise RuntimeError("índice de Medo e Ganância ainda não calculado")
    key = (t, di, df, at)
    if key in _C: _C.move_to_end(key); return _C[key]
    h = history.b3hist(t)
    C = {}
    for ts, c in zip(h["m"]["t"], h["m"]["c"]):
        if c: C[_ym(ts)] = c
    divs = {}
    for x in h.get("divs") or []: divs[_ym(x[0])] = divs.get(_ym(x[0]), 0) + x[1]
    try:
        ib = history.get("IBOV", "m"); IB = {_ym(a): b for a, b in zip(ib["t"], ib["c"]) if b}
    except Exception:
        IB = {}
    ms = [m for m in sorted(C) if di[:7] <= m <= df[:7] and m in fim]
    ret = lambda D, m, n=1: (D[_add(m, n)] / D[m] - 1) * 100 if m in D and _add(m, n) in D else None
    B = lambda m: _band(fim[m], fx)
    # 1–2. maiores quedas e altas do mês × índice no fim do mês anterior
    mv = [(m, ret(C, _add(m, -1)), fim.get(_add(m, -1))) for m in ms]
    mv = [(m, round(r, 2), f, _band(f, fx)) for m, r, f in mv if r is not None and f is not None]
    top = lambda L: [{"m": m, "r": r, "fg": f, "b": b} for m, r, f, b in L]
    out = {"t": t, "faixas": fx, "per": [ms[0] if ms else None, ms[-1] if ms else None], "n": len(ms),
           "quedas": top(sorted(mv, key=lambda x: x[1])[:10]), "altas": top(sorted(mv, key=lambda x: -x[1])[:10])}
    # 3. retorno de quem comprou em cada faixa (1, 6, 12 meses) e 7. DY dos 12 meses seguintes
    fa = [{"b": i, "n": 0, "r1": [], "r6": [], "r12": [], "dy": []} for i in range(len(fx))]
    for m in ms:
        x = fa[B(m)]; x["n"] += 1
        for n in (1, 6, 12):
            r = ret(C, m, n)
            if r is not None: x[f"r{n}"].append(r)
        if _add(m, 12) in C: x["dy"].append(sum(divs.get(_add(m, k), 0) for k in range(1, 13)) / C[m] * 100)
    out["faixa"] = [{"b": x["b"], "n": x["n"], "r1": _avg(x["r1"]), "r6": _avg(x["r6"]), "r12": _avg(x["r12"]), "n12": len(x["r12"]),
                     "up12": sum(1 for r in x["r12"] if r > 0), "dy": _avg(x["dy"]) if divs else None, "ndy": len(x["dy"])} for x in fa]  # sem proventos no histórico: sem DY
    # 4. mínimas e máximas de 12 meses: em que faixa estava o índice
    lo, hi = [0] * len(fx), [0] * len(fx)
    for m in ms:
        w = [C[_add(m, -k)] for k in range(12) if _add(m, -k) in C]
        if len(w) < 12: continue
        if C[m] <= min(w): lo[B(m)] += 1
        if C[m] >= max(w): hi[B(m)] += 1
    out["fundos"], out["topos"] = lo, hi
    # 5. depois de entrar em Medo extremo, quantos meses até voltar ao preço do mês anterior
    rec, aberto = [], 0
    for m in ms:
        p = _add(m, -1)
        if B(m) == 0 and p in fim and _band(fim[p], fx) != 0 and p in C:
            j = next((k for k in range(0, 121) if _add(m, k) in C and C[_add(m, k)] >= C[p]), None)
            if j is None: aberto += 1
            else: rec.append(j)
    out["recup"] = {"n": len(rec) + aberto, "media": _avg(rec), "pior": max(rec) if rec else None, "aberto": aberto}
    # 6. defensiva ou de ciclo: variação média no mês em Medo (faixas 0–1) e em Ganância (3–4), ação × Ibovespa
    def dfs(sel):
        a, i = [], []
        for m in ms:
            if B(m) in sel:
                ra, ri = ret(C, _add(m, -1)), ret(IB, _add(m, -1))
                if ra is not None and ri is not None: a.append(ra); i.append(ri)
        return {"acao": _avg(a), "ibov": _avg(i), "n": len(a)}
    out["defe"] = {"medo": dfs({0, 1}), "gan": dfs({len(fx) - 2, len(fx) - 1})}
    # 8. situação de hoje: outras vezes na mesma faixa -> 3 meses seguintes
    hb = _band(now, fx) if now is not None else None
    r3 = [ret(C, m, 3) for m in ms if B(m) == hb]; r3 = [r for r in r3 if r is not None]
    out["hoje"] = {"v": now, "d": now_d, "b": hb, "n": len(r3), "up": sum(1 for r in r3 if r > 0), "dn": sum(1 for r in r3 if r <= 0), "r3": _avg(r3)}
    # 9. gráfico: preço e índice no fim de cada mês
    out["serie"] = {"m": ms, "c": [C[m] for m in ms], "fg": [fim[m] for m in ms]}
    _C[key] = out
    while len(_C) > 300: _C.popitem(last=False)
    return out
