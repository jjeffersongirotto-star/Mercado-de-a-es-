"""Comparar → Medo e Ganância: como uma ação da B3 reage ao Índice de Medo e Ganância (snapshot fg).
- Maiores altas e quedas: semanais (5 pregões), com o índice do dia em que a semana começou (histórico diário completo, b3full).
- Retorno por faixa, topos e fundos, recuperação, defensiva ou de ciclo: mensais (fechamento do mês e índice no último pregão do mês).
- Gráfico: preço e índice diários nos últimos 6 anos do período e semanais antes disso.
- Velocímetros: índice da ação e do mercado (hoje, ontem, 1 semana, 1 mês), calculados na rotina diária (scripts/build_fg.py).
Cálculo leve, feito na hora e guardado em memória por ticker/período."""
import bisect, time
from collections import OrderedDict
from datetime import date, timedelta
import history
import snapshots

_C = OrderedDict()
WEEK = 5  # pregões


def _ym(ts):
    return time.strftime("%Y-%m", time.gmtime(ts))


def _ds(ts):
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def _band(v, fx):
    return next((i for i, f in enumerate(fx) if v <= f[0]), len(fx) - 1)


def _avg(x):
    return round(sum(x) / len(x), 2) if x else None


def _add(ym, n):
    y, m = int(ym[:4]), int(ym[5:7]) + n
    y += (m - 1) // 12; m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def _top(moves, n, worst):
    """As n maiores variações semanais sem sobreposição (duas semanas escolhidas não dividem pregões)."""
    used, out = [], []
    for i, r in sorted(moves, key=lambda x: x[1] if worst else -x[1]):
        if (r < 0) != worst or any(abs(i - j) < WEEK for j in used): continue
        used.append(i); out.append((i, r))
        if len(out) == n: break
    return out


def analyze(t, di, df):
    d = snapshots.load("fg", max_mem_age=3 * 3600)[0] or {}
    if not d.get("d"): raise RuntimeError("índice de Medo e Ganância ainda não calculado")
    key = (t, di, df, d.get("fetched_at"))
    if key in _C: _C.move_to_end(key); return _C[key]
    fx, FD, FV = d.get("faixas") or [], d["d"], d["v"]
    fgat = lambda s: FV[max(0, bisect.bisect_right(FD, s) - 1)] if s >= FD[0] else None  # índice do dia (ou do pregão anterior)
    fim = {}
    for day, v in zip(FD, FV): fim[day[:7]] = v  # último pregão de cada mês
    B = lambda m: _band(fim[m], fx)
    vel = lambda L, k: L[-1 - k] if len(L) > k else None
    out = {"t": t, "faixas": fx, "hoje_d": FD[-1],
           "mercado": [vel(FV, k) for k in (0, 1, 5, 21)], "acao": (d.get("acoes") or {}).get(t)}
    # ---- diário: maiores altas e quedas semanais e série do gráfico
    h = history.b3full(t)
    days = [(_ds(a), c) for a, c in zip(h["t"], h["c"]) if c]
    ix = [i for i, (s, _) in enumerate(days) if di <= s <= df]
    mv = [(i, (days[i + WEEK][1] / days[i][1] - 1) * 100) for i in ix if i + WEEK < len(days) and days[i + WEEK][0] <= df]
    wk = lambda L: [{"d": days[i][0], "d2": days[i + WEEK][0], "r": round(r, 2), "fg": fgat(days[i][0]), "b": _band(fgat(days[i][0]), fx)}
                    for i, r in L if fgat(days[i][0]) is not None]
    out["quedas"], out["altas"] = wk(_top(mv, 10, True)), wk(_top(mv, 10, False))
    cut = (date.fromisoformat(df) - timedelta(days=int(6 * 365.25))).isoformat()  # antes disso: um ponto por semana
    ser, last_w = [], None
    for i in ix:
        s = days[i][0]
        if s < cut:
            w = date.fromisoformat(s).isocalendar()[:2]
            if ser and w == last_w: ser[-1] = i
            else: ser.append(i)
            last_w = w
        else: ser.append(i)
    ser = [i for i in ser if fgat(days[i][0]) is not None]
    out["serie"] = {"d": [days[i][0] for i in ser], "c": [days[i][1] for i in ser], "fg": [fgat(days[i][0]) for i in ser]}
    # ---- mensal
    C = {}
    for a, c in zip(h["t"], h["c"]):
        if c: C[_ym(a)] = c  # fechamento do mês = último pregão do mês
    try:
        ib = history.get("IBOV", "m"); IB = {_ym(a): b for a, b in zip(ib["t"], ib["c"]) if b}
    except Exception:
        IB = {}
    ms = [m for m in sorted(C) if di[:7] <= m <= df[:7] and m in fim]
    out["per"], out["n"] = [ms[0] if ms else None, ms[-1] if ms else None], len(ms)
    ret = lambda D, m, n=1: (D[_add(m, n)] / D[m] - 1) * 100 if m in D and _add(m, n) in D else None
    # retorno de quem comprou em cada faixa (1, 6, 12 meses)
    fa = [{"b": i, "n": 0, "r1": [], "r6": [], "r12": []} for i in range(len(fx))]
    for m in ms:
        x = fa[B(m)]; x["n"] += 1
        for n in (1, 6, 12):
            r = ret(C, m, n)
            if r is not None: x[f"r{n}"].append(r)
    out["faixa"] = [{"b": x["b"], "n": x["n"], "r1": _avg(x["r1"]), "r6": _avg(x["r6"]), "r12": _avg(x["r12"]), "n12": len(x["r12"]),
                     "up12": sum(1 for r in x["r12"] if r > 0)} for x in fa]
    # mínimas e máximas de 12 meses: em que faixa estava o índice
    lo, hi = [0] * len(fx), [0] * len(fx)
    for m in ms:
        w = [C[_add(m, -k)] for k in range(12) if _add(m, -k) in C]
        if len(w) < 12: continue
        if C[m] <= min(w): lo[B(m)] += 1
        if C[m] >= max(w): hi[B(m)] += 1
    out["fundos"], out["topos"] = lo, hi
    # depois de entrar em Medo extremo, quantos meses até voltar ao preço do mês anterior
    rec, aberto = [], 0
    for m in ms:
        p = _add(m, -1)
        if B(m) == 0 and p in fim and _band(fim[p], fx) != 0 and p in C:
            j = next((k for k in range(0, 121) if _add(m, k) in C and C[_add(m, k)] >= C[p]), None)
            if j is None: aberto += 1
            else: rec.append(j)
    out["recup"] = {"n": len(rec) + aberto, "media": _avg(rec), "pior": max(rec) if rec else None, "aberto": aberto}
    # defensiva ou de ciclo: variação média no mês em Medo (faixas 0–1) e em Ganância (3–4), ação × Ibovespa
    def dfs(sel):
        a, i = [], []
        for m in ms:
            if B(m) in sel:
                ra, ri = ret(C, _add(m, -1)), ret(IB, _add(m, -1))
                if ra is not None and ri is not None: a.append(ra); i.append(ri)
        return {"acao": _avg(a), "ibov": _avg(i), "n": len(a)}
    out["defe"] = {"medo": dfs({0, 1}), "gan": dfs({len(fx) - 2, len(fx) - 1})}
    # situação de hoje: outras vezes na mesma faixa (meses do período) -> 3 meses seguintes
    hb = _band(FV[-1], fx)
    r3 = [ret(C, m, 3) for m in ms if B(m) == hb]; r3 = [r for r in r3 if r is not None]
    out["hoje"] = {"v": FV[-1], "d": FD[-1], "b": hb, "n": len(r3), "up": sum(1 for r in r3 if r > 0), "dn": sum(1 for r in r3 if r <= 0), "r3": _avg(r3)}
    _C[key] = out
    while len(_C) > 300: _C.popitem(last=False)
    return out
