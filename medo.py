"""Comparar → Medo e Ganância de uma ação da B3.
Índice da ação (stock_index, calculado na hora com o histórico diário completo): situação de hoje, retorno por faixa, maiores
altas e quedas semanais (índice do dia em que a semana começou), recuperação e gráfico. Índice do mercado (snapshot fg): topos e
fundos e defensiva ou de ciclo (comparar com o índice da própria ação seria circular: mínima de 1 ano já é "medo" por definição).
Retorno por faixa, topos/fundos, recuperação e defensiva são mensais (fechamento do mês e índice no último pregão do mês).
Gráfico: diário nos últimos 6 anos do período e semanal antes. Guardado em memória por ticker/período."""
import time
from collections import OrderedDict
from datetime import date, timedelta
import history
import snapshots

_C = OrderedDict()  # análises prontas: LRU de C_MAX
C_MAX = 30
WEEK = 5  # pregões
WIN = 252  # um ano de pregões: cada parte do índice é comparada com o último ano


def rank(a, i, invert=False):
    """Nota 0–100 do valor a[i] entre os últimos 252 (precisa de 120): regra única do índice (mercado em scripts/build_fg.py e ações)."""
    x = a[i]
    if x != x: return None  # NaN
    w = a[max(0, i - WIN + 1):i + 1]; w = w[w == w]
    if len(w) < 120: return None
    p = float((w < x).mean() * 100 + (w == x).mean() * 50)
    return 100 - p if invert else p


def stock_index(c, v):
    """Índice de Medo e Ganância de uma ação (0–100) em cada pregão, com as partes que fazem sentido para uma ação só:
    preço × média de 6 meses, posição entre a mínima e a máxima de 1 ano, oscilação (alta = medo) e volume em altas × quedas."""
    import numpy as np, pandas as pd
    C = pd.Series(c, dtype="float64"); V = pd.Series([np.nan if x is None else x for x in v], dtype="float64")
    R = C.pct_change().where(lambda x: x.abs() < 0.5)
    hi, lo = C.rolling(WIN, min_periods=200).max(), C.rolling(WIN, min_periods=200).min()
    parts = [((C / C.rolling(125, min_periods=100).mean() - 1).to_numpy(), False),
             (((C - lo) / (hi - lo).replace(0, np.nan)).to_numpy(), False),
             (R.rolling(20, min_periods=15).std().to_numpy(), True),
             ((V.where(R > 0).rolling(20, min_periods=15).sum() / V.where(R.notna()).rolling(20, min_periods=15).sum().replace(0, np.nan)).to_numpy(), False)]
    out = []
    for i in range(len(C)):
        sc = [s for s in (rank(a, i, inv) for a, inv in parts) if s is not None]
        out.append(int(round(sum(sc) / len(sc))) if len(sc) >= 3 else None)
    return out


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
    fim = {}
    for day, v in zip(FD, FV): fim[day[:7]] = v  # último pregão de cada mês
    B = lambda m: _band(fim[m], fx)
    vel = lambda L, k: L[-1 - k] if len(L) > k else None
    h = history.b3full(t)
    days = [(_ds(a), c, x) for a, c, x in zip(h["t"], h["c"], h.get("v") or [None] * len(h["t"])) if c]
    SI = stock_index([x[1] for x in days], [x[2] for x in days])  # índice da ação em cada pregão
    SD = {days[i][0]: s for i, s in enumerate(SI) if s is not None}
    SL = [s for s in SI if s is not None]
    out = {"t": t, "faixas": fx, "hoje_d": days[-1][0],
           "mercado": [vel(FV, k) for k in (0, 1, 5, 21)], "acao": [vel(SL, k) for k in (0, 1, 5, 21)] if SL else None}
    # ---- diário: maiores altas e quedas semanais (índice da ação no dia em que a semana começou) e série do gráfico
    ix = [i for i, x in enumerate(days) if di <= x[0] <= df]
    mv = [(i, (days[i + WEEK][1] / days[i][1] - 1) * 100) for i in ix if i + WEEK < len(days) and days[i + WEEK][0] <= df]
    mv = [x for x in mv if SI[x[0]] is not None]
    wk = lambda L: [{"d": days[i][0], "d2": days[i + WEEK][0], "r": round(r, 2), "fg": SI[i], "b": _band(SI[i], fx)} for i, r in L]
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
    ser = [i for i in ser if SI[i] is not None]
    out["serie"] = {"d": [days[i][0] for i in ser], "c": [days[i][1] for i in ser], "fg": [SI[i] for i in ser]}
    # ---- mensal
    C, SM = {}, {}
    for s, c, _ in days: C[s[:7]] = c  # fechamento do mês = último pregão do mês
    for s, v in SD.items(): SM[s[:7]] = v  # índice da ação no último pregão do mês
    try:
        ib = history.get("IBOV", "m"); IB = {_ym(a): b for a, b in zip(ib["t"], ib["c"]) if b}
    except Exception:
        IB = {}
    ms = [m for m in sorted(C) if di[:7] <= m <= df[:7] and m in fim]
    msa = [m for m in ms if m in SM]  # meses com índice da ação
    BA = lambda m: _band(SM[m], fx)
    out["per"], out["n"] = [ms[0] if ms else None, ms[-1] if ms else None], len(ms)
    ret = lambda D, m, n=1: (D[_add(m, n)] / D[m] - 1) * 100 if m in D and _add(m, n) in D else None
    # retorno de quem comprou em cada faixa do índice da ação (1, 6, 12 meses)
    fa = [{"b": i, "n": 0, "r1": [], "r6": [], "r12": []} for i in range(len(fx))]
    for m in msa:
        x = fa[BA(m)]; x["n"] += 1
        for n in (1, 6, 12):
            r = ret(C, m, n)
            if r is not None: x[f"r{n}"].append(r)
    out["faixa"] = [{"b": x["b"], "n": x["n"], "r1": _avg(x["r1"]), "r6": _avg(x["r6"]), "r12": _avg(x["r12"]), "n12": len(x["r12"]),
                     "up12": sum(1 for r in x["r12"] if r > 0)} for x in fa]
    # mínimas e máximas de 12 meses: em que faixa estava o índice do mercado
    lo, hi = [0] * len(fx), [0] * len(fx)
    for m in ms:
        w = [C[_add(m, -k)] for k in range(12) if _add(m, -k) in C]
        if len(w) < 12: continue
        if C[m] <= min(w): lo[B(m)] += 1
        if C[m] >= max(w): hi[B(m)] += 1
    out["fundos"], out["topos"] = lo, hi
    # depois de o índice da ação entrar em Medo extremo, quantos meses até voltar ao preço do mês anterior
    rec, aberto = [], 0
    for m in msa:
        p = _add(m, -1)
        if BA(m) == 0 and p in SM and BA(p) != 0 and p in C:
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
    # situação de hoje (índice da ação): outras vezes na mesma faixa (meses do período) -> 3 meses seguintes
    hv = SL[-1] if SL else None; hb = _band(hv, fx) if hv is not None else None
    r3 = [ret(C, m, 3) for m in msa if BA(m) == hb]; r3 = [r for r in r3 if r is not None]
    out["hoje"] = {"v": hv, "d": days[-1][0], "b": hb, "n": len(r3), "up": sum(1 for r in r3 if r > 0), "dn": sum(1 for r in r3 if r <= 0), "r3": _avg(r3)}
    _C[key] = out
    while len(_C) > C_MAX: _C.popitem(last=False)
    return out
