"""Previsão → card Modelos: regras dos modelos (fonte única: MODELOS) e simulação semanal com custos, IR e CDB.
Sinais semanais de cada ação: snapshot `modelos` (scripts/build_modelos.py). CDB: história do CDI do Banco Central (history.bcb).
Cada semana usa o sinal da semana anterior (decide com o fechamento de sexta e opera na semana seguinte).
Aportes e retiradas entram no último pregão de cada mês (mês 1 = valor inicial), como na tabela da Previsão.
Imposto: 15% do lucro líquido das vendas do mês quando as vendas passam de R$ 20 mil; prejuízo compensa os meses seguintes.
Proventos: mesma regra de imposto da tabela (automático = 10% no mês acima de R$ 50 mil, ou o % escolhido)."""
import threading, time
from collections import OrderedDict
import numpy as np

# id, nome, vende? e regras (o painel ⓘ → Modelos explica cada um com estas regras)
MODELOS = [
    {"id": "hold", "n": "Comprar e segurar", "vende": False},
    {"id": "medo_mercado", "n": "Aporta com medo do mercado", "vende": False},
    {"id": "medo_acao", "n": "Aporta com medo da ação", "vende": False},
    {"id": "media200", "n": "Aporta acima da média de 200 dias", "vende": False},
    {"id": "alg1", "n": "Algoritmo 1 mês", "vende": True, "p": "p1", "min": 12},
    {"id": "alg3", "n": "Algoritmo 3 meses", "vende": True, "p": "p3", "min": 12},
    {"id": "tendencia", "n": "Tendência", "vende": True, "min": 4},
    {"id": "hibrido", "n": "Híbrido adaptativo", "vende": False, "frac": True},
]
MOD = {m["id"]: m for m in MODELOS}
CUSTO = 0.003      # corretagem + emolumentos + diferença de preço, por operação
IR, ISENTO = 0.15, 20000.0
MEDO = 45          # abaixo disso o índice está em Medo (faixas de fg.json)
MED_SEM = 52       # chance do algoritmo "favorável" = acima da mediana das últimas 52 semanas da própria ação
TROCA_SEM = 12     # rodízio: semanas mínimas na empresa antes de trocar por outra melhor
# rodízio: grupos prontos (nome, subsetor, quantas maiores por valor de mercado) + os grupos do usuário (aba Grupos)
GRUPOS = [("5 maiores bancos", r"^Bancos", 5), ("5 maiores de energia elétrica", r"^Energia Elétrica", 5), ("10 maiores da B3", None, 10)]
# Híbrido: especialistas (exposição de cada um) e peso pelo acerto recente na própria ação (painel ⓘ → Modelos da Previsão)
HIB = ("hold", "alg1", "alg3", "media200")
# Ajusta a parte na ação com aportes e proventos (compra só até a exposição alvo; o resto espera no CDB) e não vende:
# no teste com IR e custos, vender (mesmo em parte ou dentro da isenção) sempre rendeu menos que manter.
HIB_SEM, HIB_ETA = 52, 5  # janela do acerto recente (semanas) e o quanto o melhor recebe mais peso
HIB_COMPRA = .125  # compra quando a parte na ação está pelo menos 12,5 pontos abaixo do alvo (no teste rendeu mais que comprar aos poucos)
MARGEM = {"alg1": 20, "alg3": 20, "tendencia": 100}  # rodízio: vantagem mínima para trocar (chance ×1000; alta 12 m ×1000)

_D = {"at": 0, "key": None, "d": None}
_lock = threading.Lock()
_C = OrderedDict()


def build(snap, cdi):
    """snapshot `modelos` + CDI diário {d, v (% ao dia)} -> matrizes ações × semanas (numpy)."""
    W = snap["w"]; T = len(W); tick = sorted(snap["a"]); N = len(tick)
    arr = lambda: np.full((N, T), np.nan)
    C, DV, SI, M2, R12, P1, P3 = (arr() for _ in range(7))
    for k, t in enumerate(tick):
        a = snap["a"][t]; i0 = a["i0"]
        for M, key in ((C, "c"), (SI, "si"), (M2, "m2"), (R12, "r12"), (P1, "p1"), (P3, "p3")):
            v = a.get(key) or []
            M[k, i0:i0 + len(v)] = [np.nan if x is None else x for x in v]
        DV[k, i0:] = 0
        for j, v in (a.get("dv") or {}).items(): DV[k, i0 + int(j)] = v
    import pandas as pd
    fav = {}
    for key, P in (("p1", P1), ("p3", P3)):
        med = pd.DataFrame(P.T).rolling(MED_SEM, min_periods=MED_SEM // 2).median().to_numpy().T
        fav[key] = (P >= med) & ~np.isnan(P)
    # CDB (100% do CDI): fator de cada semana = produto das taxas diárias desde a semana anterior
    cs = pd.Series(np.cumprod(1 + np.array(cdi["v"], dtype=float) / 100), index=pd.to_datetime(cdi["d"]))
    wk = pd.to_datetime(W)
    acc = cs.reindex(cs.index.union(wk)).ffill().reindex(wk).to_numpy()
    cdb = np.ones(T)
    ok = ~np.isnan(acc)
    cdb[1:] = np.where(ok[1:] & ok[:-1], acc[1:] / np.where(ok[:-1], acc[:-1], 1), 1.0)
    # híbrido: exposição (0, 25, 50, 75 ou 100%) = média das exposições dos especialistas, pesadas pelo retorno de cada um nas últimas
    # HIB_SEM semanas (ação + proventos quando dentro, CDB quando fora); decide com dados até a semana (opera na seguinte)
    Cf = pd.DataFrame(C.T).ffill().to_numpy().T
    rs = np.zeros((N, T)); rs[:, 1:] = np.nan_to_num((Cf[:, 1:] + np.nan_to_num(DV[:, 1:])) / Cf[:, :-1] - 1)
    X = np.stack([np.ones((N, T)), fav["p1"], fav["p3"], np.nan_to_num(M2) > 0]).astype(float)
    lr = np.zeros_like(X); lr[:, :, 1:] = np.log1p(X[:, :, :-1] * rs[None, :, 1:] + (1 - X[:, :, :-1]) * (cdb[1:] - 1)[None, None, :])
    cs = np.cumsum(lr, axis=2); perf = cs.copy(); perf[:, :, HIB_SEM:] -= cs[:, :, :-HIB_SEM]
    wt = np.exp(HIB_ETA * (perf - perf.max(axis=0, keepdims=True))); wt /= wt.sum(axis=0, keepdims=True)
    HX = np.round((wt * X).sum(axis=0) * 4) / 4
    HW = np.round(wt * 100).astype(np.int16)  # peso de cada especialista (%): a tabela mostra quem o híbrido está seguindo
    ym = [w[:7] for w in W]
    first = next((i for i in range(T) if ok[i]), 0)  # modelos começam no 1º mês com CDB
    return {"w": W, "ym": ym, "tick": tick, "ix": {t: k for k, t in enumerate(tick)}, "C": C, "DV": DV, "SI": SI, "M2": M2, "R12": R12,
            "P": {"p1": P1, "p3": P3}, "FAV": fav, "HX": HX, "HW": HW, "MI": np.array([np.nan if x is None else x for x in snap["mi"]], dtype=float), "cdb": cdb,
            "me": np.array([i == T - 1 or ym[i + 1] != ym[i] for i in range(T)]), "ini": ym[first], "fim": ym[-1],
            "acerto": snap.get("acerto") or {}, "at": snap.get("fetched_at")}


def data():
    """Matrizes prontas (recalcula quando o snapshot muda; guarda 6 h)."""
    import snapshots, history
    with _lock:
        if _D["d"] is not None and time.time() - _D["at"] < 6 * 3600: return _D["d"]
        snap = snapshots.load("modelos", max_mem_age=6 * 3600)[0]
        if not snap or not snap.get("a"): raise RuntimeError("sinais dos modelos ainda não calculados")
        if _D["key"] != snap.get("fetched_at") or _D["d"] is None:
            _D["d"] = build(snap, history.bcb("cdi")); _D["key"] = snap.get("fetched_at"); _C.clear()
        _D["at"] = time.time()
        return _D["d"]


def ready_groups(rows):
    """Grupos prontos do rodízio a partir das linhas de /api/data (1 ticker por empresa)."""
    import re
    vm = lambda r: (r.get("v") or {}).get("valmerc") or 0
    out = []
    for n, rx, k in GRUPOS:
        sel = [r for r in rows if rx is None or re.search(rx, r.get("subsetor") or "")]
        out.append({"n": n, "t": [r["ticker"] for r in sorted(sel, key=lambda r: -vm(r))[:k]]})
    return out


def meta(D):
    return {"modelos": [{"id": m["id"], "n": m["n"], "vende": m["vende"]} for m in MODELOS], "ini": D["ini"], "fim": D["fim"], "at": D["at"], "tick": D["tick"]}


def _span(D, di, df):
    """Semanas de fim de mês entre di e df (AAAA-MM): mês 1 = fim de di."""
    di = max(di, D["ini"]); ym = D["ym"]
    me = [i for i in range(len(ym)) if D["me"][i] and di <= ym[i] <= df]
    return me


def _signals(D, mid, idx, i):
    """(fica comprado?, pode aplicar?) de cada ação em idx com os dados da semana i (sinal sem estado)."""
    n = len(idx)
    if mid == "hold": return np.ones(n, bool)
    if mid == "medo_mercado": return np.full(n, bool(D["MI"][i] < MEDO))
    if mid == "medo_acao": return D["SI"][idx, i] < MEDO
    if mid in ("media200", "tendencia"): return D["M2"][idx, i] > 0
    if mid == "hibrido": return D["HX"][idx, i] > 0  # (só para o 1º sinal; a simulação usa a exposição HX)
    return D["FAV"][MOD[mid]["p"]][idx, i]


class Conta:
    """Carteira de uma ou várias ações em paralelo (vetores): ações, caixa no CDB, custo, IR do mês e prejuízo a compensar."""

    def __init__(s, n):
        z = lambda: np.zeros(n)
        s.sh, s.cash, s.basis, s.carry, s.msales, s.mgain, s.mdiv = z(), z(), z(), z(), z(), z(), z()
        s.ir, s.dtax, s.divT, s.compras, s.vendas = z(), z(), z(), z(), z()

    def sell(s, mask, p, frac=None):
        """Vende (tudo ou a fração frac) das ações marcadas; -> resultado (valor recebido − custo médio) de cada uma."""
        f = np.where(mask, 1.0 if frac is None else frac, 0.0)
        q = s.sh * f; v = q * p * (1 - CUSTO); b = s.basis * f; g = np.where(mask, v - b, 0.0)
        s.msales += np.where(mask, q * p, 0); s.mgain += g; s.cash += np.where(mask, v, 0)
        s.sh -= q; s.basis -= b
        if frac is None: s.vendas += mask & (q > 0)
        return g

    def buy(s, mask, p, amt=None):
        """Compra com todo o caixa (ou só `amt`) das ações marcadas."""
        a = s.cash if amt is None else np.minimum(s.cash, amt)
        m = mask & (a > 0.005)
        s.compras += m & (s.sh <= 0) if amt is None else m
        s.sh += np.where(m, a * (1 - CUSTO) / np.where(m, p, 1), 0); s.basis += np.where(m, a, 0)
        s.cash = s.cash - np.where(m, a, 0)

    def raise_cash(s, need, p):
        """Vende só o necessário para ter `need` em caixa (retirada, imposto)."""
        falta = np.maximum(0, need - s.cash); val = s.sh * p * (1 - CUSTO)
        m = (falta > 0) & (val > 0)
        s.sell(m, p, np.where(m, np.minimum(1, falta / np.where(val > 0, val, 1)), 0))

    def close_month(s, p, ap, w, tx):
        """Fim do mês: retirada, imposto das vendas (com isenção e prejuízo a compensar) e dos proventos, aporte."""
        s.raise_cash(w, p); s.cash = np.maximum(0, s.cash - w)
        tax = np.where(s.msales > ISENTO, np.maximum(0, s.mgain - s.carry), 0) * IR
        s.carry = np.where(s.mgain < 0, s.carry - s.mgain, np.where(s.msales > ISENTO, np.maximum(0, s.carry - np.maximum(0, s.mgain)), s.carry))
        dt = np.where(s.mdiv > 50000, s.mdiv * 0.10, 0) if tx is None else s.mdiv * tx / 100
        s.raise_cash(tax + dt, p); s.cash -= tax + dt; s.ir += tax; s.dtax += dt
        s.msales[:] = 0; s.mgain[:] = 0; s.mdiv[:] = 0
        s.cash += ap
        return tax + dt


F0 = lambda x: f"{x:.0f}"


def simulate(D, mid, idx, me, ap, wd, tx=None, divs=True, rec=False):
    """Um modelo em várias ações ao mesmo tempo (cada uma sozinha). me: semanas de fim de mês; ap/wd: aporte/retirada de cada mês.
    -> dict de vetores (valor final, aportado, IR, compras, vendas) e, com rec, as linhas mensais de cada ação."""
    idx = np.asarray(idx); n = len(idx); s, e = me[0], me[-1]
    A = Conta(n); C, DV = D["C"], D["DV"]; mod = MOD[mid]
    sig0 = _signals(D, mid, idx, s - 1) if s > 0 else np.zeros(n, bool)
    st, k = np.nan_to_num(sig0, nan=0).astype(bool), np.full(n, 10 ** 6)
    lastp = C[idx, s].copy(); mi = 0; rows = [[] for _ in range(n)] if rec else None
    meset = {w: j for j, w in enumerate(me)}
    A.cash += ap[0]
    for i in range(s, e + 1):
        p = C[idx, i]; ok = ~np.isnan(p); lastp = np.where(ok, p, lastp); P = lastp
        if i > s:
            A.cash *= D["cdb"][i]
            if divs:
                d = A.sh * np.nan_to_num(DV[idx, i]); A.cash += d; A.mdiv += d; A.divT += d
        sig = _signals(D, mid, idx, i - 1) if i > s else sig0
        sig = np.nan_to_num(sig, nan=0).astype(bool)
        if mod.get("frac"):  # híbrido: ajusta a parte na ação à exposição alvo (vende ou compra só a diferença)
            want = buy = None
        elif mod["vende"]:  # entra/sai com tempo mínimo em cada posição
            k += 1; ch = (sig != st) & (k >= mod["min"]); st = np.where(ch, sig, st); k = np.where(ch, 0, k)
            want = buy = st
        else:
            want, buy = np.ones(n, bool), sig
        if mod.get("frac"):
            e = D["HX"][idx, i - 1] if i > 0 else np.ones(n)
        elif i > s:
            A.sell(~want & (A.sh > 0) & ok, P)
        tax = 0
        j = meset.get(i)
        if j is not None and i > s:
            tax = A.close_month(P, ap[j] if j < len(ap) else 0, wd[j] if j < len(wd) else 0, tx)
        if mod.get("frac"):
            V = A.sh * P + A.cash; falta = e * V - A.sh * P
            A.buy(ok & (falta > np.maximum(HIB_COMPRA * V, 100)), P, falta)  # só compra quando a diferença para o alvo é relevante
        else:
            A.buy(buy & ok, P)
        if rec and j is not None:
            v = A.sh * P + A.cash
            for q in range(n):
                rows[q].append({"ym": D["ym"][i], "v": float(v[q]), "div": float(A.divT[q]), "tax": float(A.ir[q] + A.dtax[q]),
                                "pos": (f"{F0(100 * A.sh[q] * P[q] / v[q])}% na ação · segue {MOD[HIB[int(np.argmax(D['HW'][:, idx[q], i - 1]))]]['n']}"
                                        if mod.get("frac") and v[q] > 0 else
                                        "Ação" if A.sh[q] > 0 and A.cash[q] < 1 else "CDB" if A.sh[q] <= 0 else "Ação + CDB"),
                                "c": int(A.compras[q]), "s": int(A.vendas[q])})
        mi += 1
    v = A.sh * lastp + A.cash
    return {"v": v, "ir": A.ir + A.dtax, "c": A.compras, "s": A.vendas, "rows": rows}


def rotate(D, mid, gidx, me, ap, wd, tx=None):
    """Rodízio: um modelo que vende, uma empresa do grupo por vez (a de melhor sinal), CDB quando nenhuma está favorável.
    -> valor final, IR e o histórico (por empresa e cada troca com o motivo)."""
    gidx = list(gidx); s, e = me[0], me[-1]; mod = MOD[mid]; nm = D["tick"]
    C, DV = D["C"], D["DV"]
    alg = mid != "tendencia"
    A = Conta(1); cur, k = -1, 0; lastp = {g: C[g, s] for g in gidx}
    per = {g: {"t": nm[g], "c": 0, "sem": 0, "n": 0, "res": 0.0, "ir": 0.0} for g in gidx}
    moves, cdbw, tot = [], 0, 0; nav, navpk, dd, vprev = 1.0, 1.0, 0.0, None
    meset = {w: j for j, w in enumerate(me)}; A.cash += ap[0]; mg = {}  # resultado das vendas do mês por empresa (para dividir o IR)
    pct = lambda x: f"{x / 10:.1f}%".replace(".", ",")

    def score(g, i):
        if alg: return D["P"][mod["p"]][g, i], bool(D["FAV"][mod["p"]][g, i])
        return D["R12"][g, i], bool(D["M2"][g, i] > 0)

    def why(g, i):
        sc, _ = score(g, i)
        return f"chance de alta {pct(sc)}" if alg else f"alta de {pct(sc)} em 12 meses e acima da média de 200 dias"

    def sell_cur(P, i, motivo):
        nonlocal cur
        g = A.sell(np.array([True]), np.array([P]))[0]
        per[cur]["res"] += g; mg[cur] = mg.get(cur, 0) + g; per[cur]["n"] += 1
        moves.append({"d": D["w"][i], "de": nm[cur], "para": None, "m": motivo}); cur = -1

    for i in range(s, e + 1):
        for g in gidx:
            if not np.isnan(C[g, i]): lastp[g] = C[g, i]
        if i > s:
            A.cash *= D["cdb"][i]
            if cur >= 0:
                d = A.sh[0] * np.nan_to_num(DV[cur, i]); A.cash += d; A.mdiv += d; A.divT += d; per[cur]["res"] += d
        if i > 0:
            cand = [(score(g, i - 1)[0], g) for g in gidx if not np.isnan(C[g, i]) and score(g, i - 1)[1] and not np.isnan(score(g, i - 1)[0])]
            best = max(cand)[1] if cand else -1
            if cur >= 0:
                k += 1
                sc, fav = score(cur, i - 1)
                if not fav and k >= mod["min"] and not np.isnan(C[cur, i]):
                    sell_cur(lastp[cur], i, "previsão desfavorável" if alg else "abaixo da média de 200 dias")
                elif best >= 0 and best != cur and k >= TROCA_SEM and not np.isnan(C[cur, i]) and score(best, i - 1)[0] >= sc + MARGEM[mid]:
                    sell_cur(lastp[cur], i, f"{nm[best]} com sinal melhor")
            if cur < 0 and best >= 0:
                cur, k = best, 0; per[cur]["c"] += 1
                if moves and moves[-1]["para"] is None and moves[-1]["d"] == D["w"][i]: moves[-1]["para"] = nm[cur]; moves[-1]["m2"] = why(cur, i - 1)
                else: moves.append({"d": D["w"][i], "de": None, "para": nm[cur], "m": None, "m2": why(cur, i - 1)})
        P = lastp[cur] if cur >= 0 else 0.0
        j = meset.get(i)
        flow = 0.0
        if j is not None and i > s:
            a, w = (ap[j] if j < len(ap) else 0), (wd[j] if j < len(wd) else 0)
            ir0, mgain = A.ir[0], dict(mg)
            A.close_month(np.array([P]), np.array([a]), np.array([w]), tx)
            ir = A.ir[0] - ir0
            pos = {g: x for g, x in mgain.items() if x > 0}
            for g, x in pos.items(): per[g]["ir"] += ir * x / sum(pos.values())
            mg.clear(); flow = a - w
        if cur >= 0: A.buy(np.array([True]), np.array([P]))
        else: cdbw += 1
        tot += 1
        if cur >= 0: per[cur]["sem"] += 1
        v = A.sh[0] * P + A.cash[0]
        if vprev: nav *= (v - flow) / vprev if vprev > 0 else 1
        vprev = v; navpk = max(navpk, nav); dd = min(dd, nav / navpk - 1)
    v = A.sh[0] * (lastp[cur] if cur >= 0 else 0) + A.cash[0]
    if cur >= 0:
        per[cur]["res"] += A.sh[0] * lastp[cur] - A.basis[0]; per[cur]["n"] += 1
    emp = [dict(x, sem=round(x["sem"] / max(1, x["n"]), 1), res=round(x["res"], 2), ir=round(x["ir"], 2)) for x in per.values() if x["c"]]
    emp.sort(key=lambda x: -x["res"])
    return {"v": float(v), "ir": float(A.ir[0] + A.dtax[0]), "c": int(A.compras[0]), "s": int(A.vendas[0]),
            "hist": {"emp": emp, "trocas": sum(1 for m in moves if m["de"] and m["para"]), "cdb": round(cdbw / max(1, tot) * 100, 1),
                     "dd": round(dd * 100, 1), "mov": moves[-200:]}}


def run(D, req):
    """Pedido da aba Previsão -> linhas do Desempenho (grupos primeiro) e, com tab, as linhas mensais de uma simulação."""
    di, df = str(req.get("di") or ""), str(req.get("df") or "")
    me = _span(D, di, df)
    if len(me) < 2: return {"error": f"Período curto ou fora dos dados dos modelos ({D['ini']} a {D['fim']})."}
    ap = [max(0.0, float(x or 0)) for x in (req.get("ap") or [])][:len(me)]
    wd = [max(0.0, float(x or 0)) for x in (req.get("w") or [])][:len(me)]
    ap += [0.0] * (len(me) - len(ap)); wd += [0.0] * (len(me) - len(wd))
    tx = req.get("tx"); tx = None if tx is None else max(0.0, min(100.0, float(tx)))
    key = repr((D["at"], di, df, ap, wd, tx, req.get("ticker"), req.get("modelo"), req.get("grupos"), req.get("tab")))
    if key in _C: _C.move_to_end(key); return _C[key]
    apT = sum(ap)
    ini = {"ini": D["ym"][me[0]], "fim": D["ym"][me[-1]], "meses": len(me), "apT": apT}
    ok = lambda k: not np.isnan(D["C"][k, me[0]])
    if req.get("tab"):  # tabela mês a mês de uma empresa com um modelo (com e sem proventos)
        t, mid = req["tab"].get("t"), req["tab"].get("m")
        if t not in D["ix"] or mid not in MOD: return {"error": "Empresa ou modelo sem dados."}
        k = D["ix"][t]
        if not ok(k): return {"error": f"{t} ainda não negociava em {D['ym'][me[0]]}."}
        com = simulate(D, mid, [k], me, ap, wd, tx, True, True)["rows"][0]
        sem = simulate(D, mid, [k], me, ap, wd, tx, False, True)["rows"][0]
        out = dict(ini, tab=[dict(c, sem=x["v"], com=c.pop("v")) for c, x in zip(com, sem)])
    else:
        mids = [m["id"] for m in MODELOS] if req.get("modelo") == "*" else [req.get("modelo")]
        if any(m not in MOD for m in mids): return {"error": "Modelo desconhecido."}
        rows = []
        pc = lambda v: round((v - apT) / apT * 100, 2) if apT > 0 else None
        if req.get("ticker") == "*":
            uni = [D["ix"][t] for t in (req.get("universo") or []) if t in D["ix"]]
            uni = [k for k in uni if ok(k)]
            for mid in mids:
                if MOD[mid]["vende"] and not MOD[mid].get("frac"):  # rodízio: uma empresa por vez (o híbrido divide a exposição na própria ação)
                    for g in (req.get("grupos") or [])[:12]:
                        gi = [D["ix"][t] for t in (g.get("t") or [])[:30] if t in D["ix"]]
                        if len(gi) < 2: continue  # empresa listada depois do início entra no rodízio quando passa a ter preço
                        r = rotate(D, mid, gi, me, ap, wd, tx)
                        rows.append({"k": "g", "m": mid, "n": str(g.get("n") or "")[:60], "t": [D["tick"][x] for x in gi], "v": round(r["v"], 2),
                                     "pct": pc(r["v"]), "ir": round(r["ir"], 2), "c": r["c"], "s": r["s"], "hist": r["hist"]})
                if not uni: continue
                r = simulate(D, mid, uni, me, ap, wd, tx)
                best = sorted(range(len(uni)), key=lambda q: -r["v"][q])[:10]
                rows += [{"k": "a", "m": mid, "t": D["tick"][uni[q]], "v": round(float(r["v"][q]), 2), "pct": pc(r["v"][q]),
                          "ir": round(float(r["ir"][q]), 2), "c": int(r["c"][q]), "s": int(r["s"][q])} for q in best]
        else:
            t = req.get("ticker")
            if t not in D["ix"]: return {"error": f"{t} sem dados para os modelos."}
            k = D["ix"][t]
            if not ok(k): return {"error": f"{t} ainda não negociava em {D['ym'][me[0]]}."}
            if len(mids) == 1 and mids[0] != "hold": mids = mids + ["hold"]  # referência: comprar e segurar
            for mid in mids:
                r = simulate(D, mid, [k], me, ap, wd, tx)
                rows.append({"k": "a", "m": mid, "t": t, "v": round(float(r["v"][0]), 2), "pct": pc(r["v"][0]), "ir": round(float(r["ir"][0]), 2),
                             "c": int(r["c"][0]), "s": int(r["s"][0])})
        rows.sort(key=lambda x: (x["k"] != "g", -(x["pct"] if x["pct"] is not None else -1e9)))
        out = dict(ini, rows=rows)
    _C[key] = out
    while len(_C) > 60: _C.popitem(last=False)
    return out


def top_sector(rows, n=5):
    """As n maiores empresas (valor de mercado) de cada setor, 1 ticker por empresa (linhas de /api/data já filtradas)."""
    by = {}
    for r in rows: by.setdefault(r.get("setor") or "?", []).append(r)
    vm = lambda r: (r.get("v") or {}).get("valmerc") or 0
    return [r["ticker"] for rs in by.values() for r in sorted(rs, key=lambda r: -vm(r))[:n]]


def ranking(V):
    """V: modelos × empresas (valor final). -> posição (0 = 1º) de cada modelo em cada empresa e a ordem das Colocações:
    mais 1º lugares; empate -> mais 2º lugares, e assim por diante; empate em tudo -> maior média."""
    rk = (-V).argsort(axis=0, kind="stable").argsort(axis=0)
    cnt = np.array([[int((rk[i] == p).sum()) for p in range(V.shape[0])] for i in range(V.shape[0])])
    order = sorted(range(V.shape[0]), key=lambda i: tuple(-cnt[i]) + (-V[i].mean(),))
    return rk, cnt, order


def compare(D, tickers, di, df, ini, ap):
    """Comparar → Modelos: todos os modelos em cada empresa com o mesmo valor inicial e aporte mensal.
    -> empresas usadas (com preço no início), lucro % de cada modelo × empresa, posições e os resumos das tabelas."""
    me = _span(D, di, df)
    if len(me) < 2: return {"error": f"Período curto ou fora dos dados dos modelos ({D['ini']} a {D['fim']})."}
    key = repr(("cmp", D["at"], tuple(tickers), di, df, ini, ap))
    if key in _C: _C.move_to_end(key); return _C[key]
    aps = [ini] + [ap] * (len(me) - 1); apT = sum(aps); w = [0.0] * len(me)
    idx = [D["ix"][t] for t in dict.fromkeys(tickers) if t in D["ix"] and not np.isnan(D["C"][D["ix"][t], me[0]])]
    if not idx: return {"error": f"Nenhuma das empresas tinha preço em {D['ym'][me[0]]}."}
    V = np.array([simulate(D, m["id"], idx, me, aps, w)["v"] for m in MODELOS])
    P = (V / apT - 1) * 100
    rk, cnt, order = ranking(V)
    hold = V[[m["id"] for m in MODELOS].index("hold")]
    res = [{"m": m["id"], "media": round(float(P[i].mean()), 2), "vmedio": round(float(V[i].mean()), 2), "mediana": round(float(np.median(P[i])), 2),
            "ganha": None if m["id"] == "hold" else round(float((V[i] > hold).mean() * 100), 1), "pior": int(rk[i].max()) + 1, "pos": cnt[i].tolist()}
           for i, m in enumerate(MODELOS)]
    out = {"ini": D["ym"][me[0]], "fim": D["ym"][me[-1]], "meses": len(me), "apT": apT, "pedidas": len(dict.fromkeys(tickers)),
           "t": [D["tick"][k] for k in idx], "m": [m["id"] for m in MODELOS], "p": np.round(P, 2).tolist(), "rk": rk.tolist(),
           "res": res, "ord_media": sorted(range(len(MODELOS)), key=lambda i: -P[i].mean()), "ord_pos": order}
    _C[key] = out
    while len(_C) > 60: _C.popitem(last=False)
    return out
