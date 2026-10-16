"""Previsão → card Modelos: regras dos modelos (fonte única: MODELOS) e simulação semanal com custos, IR e CDB.
Sinais semanais de cada ação: snapshot `modelos` (scripts/build_modelos.py). CDB: história do CDI do Banco Central (history.bcb).
Cada semana usa o sinal da semana anterior (decide com o fechamento de sexta e opera na semana seguinte).
Aportes e retiradas entram no último pregão de cada mês (mês 1 = valor inicial), como na tabela da Previsão.
Imposto: 15% do lucro líquido das vendas do mês quando as vendas passam de R$ 20 mil; prejuízo compensa os meses seguintes.
Proventos: mesma regra de imposto da tabela (automático = 10% no mês acima de R$ 50 mil, ou o % escolhido)."""
import gc, threading, time, warnings
from collections import OrderedDict
import numpy as np

# id, nome, vende? e regras (o painel ⓘ → Modelos explica cada um com estas regras)
MODELOS = [
    {"id": "hold", "n": "Comprar e segurar", "vende": False},
    {"id": "medo_mercado", "n": "Aporta com medo do mercado", "vende": False},
    {"id": "medo_acao", "n": "Aporta com medo da ação", "vende": False},
    {"id": "media200", "n": "Aporta acima da média de 200 dias", "vende": False},
    {"id": "alg1", "n": "Algoritmo 1 mês", "vende": True, "p": "p1", "min": 12},
    {"id": "alg3", "n": "Algoritmo 3 meses", "vende": True, "p": "p3", "min": 12, "lucro": True},
    {"id": "tendencia", "n": "Tendência", "vende": True, "min": 4, "lucro": True},
    {"id": "hibrido", "n": "Híbrido adaptativo", "vende": False, "frac": True},
    {"id": "barsi", "n": "Método Barsi", "vende": False, "lucro": True},
]
# referências fora das empresas: mesmo dinheiro, mesmos aportes e retiradas; entram nas tabelas pelo rendimento e nos Pontos ficam
# sempre com as últimas colocações (ranking)
REF = [
    {"id": "cdb", "n": "CDB", "vende": False, "ref": True,
     "nota": "sem resgate no período: no resgate paga IR de 15% sobre o rendimento (aplicação acima de 2 anos)"},
    {"id": "ouro", "n": "Ouro", "vende": False, "ref": True, "nota": "ouro em reais, custo de 0,3% em cada compra; nunca vende"},
]
MOD = {m["id"]: m for m in MODELOS + REF}
# Método Barsi: só setores perenes (fonte única; o chat e o painel ⓘ leem daqui): subsetor do site ou segmento oficial da B3
PERENE_RX = r"^(Bancos|Energia Elétrica|Água e Saneamento|Seguradoras|Resseguradoras|Corretoras de Seguros|Telecomunicações|Papel e Celulose|Químicos)"
PERENE_TXT = "bancos, energia elétrica, saneamento, seguros, telecomunicações, papel e celulose e químicos"
# teto = média dos proventos por ação dos 5 anos completos anteriores ÷ 6% (pagou em pelo menos 4 deles); aporte do mês e proventos
# entram na ação até 20% acima do teto, guardando 10% no CDB; a reserva entra quando o preço está no teto ou abaixo; acima de 20%, espera
BARSI_DY, BARSI_ANOS, BARSI_ACIMA, BARSI_RES = .06, 5, 1.20, .10


def perene(r, cad=None):
    """A empresa (linha de /api/data) é de setor perene do Método Barsi? cad: cadastro da B3 {raiz: [nome, segmento]}."""
    import re
    sub = r.get("subsetor") or ""; seg = ((cad or {}).get(r["ticker"][:4]) or [None, ""])[1] or ""
    if any(re.search(PERENE_RX, x) for x in (sub, r.get("setor") or "", seg)): return True
    return r.get("setor") == "Utilities" and not sub and seg in ("", "Não Classificados", "Não Classificado")


besst = perene  # nome antigo


def set_setores(D, rows, cad=None):
    """Marca as empresas de setor perene nas matrizes (fora delas o Método Barsi fica "fora do método")."""
    bs = {r["ticker"] for r in rows if perene(r, cad)}
    if D.get("_bs") != bs: D["BS"] = np.array([t in bs for t in D["tick"]]); D["_bs"] = bs; _C.clear()
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
FORTE_R12 = 100   # Tendência: entrada no rodízio só com alta de pelo menos 10% em 12 meses (×1000)
# "lucro": só compra se o último balanço anual publicado teve lucro (fund.json); no teste 2006–2026 ajudou só estes dois modelos
MARGEM = {"alg1": 20, "alg3": 20, "tendencia": 100}  # rodízio: vantagem mínima para trocar (chance ×1000; alta 12 m ×1000)

_D = {"at": 0, "key": None, "d": None}
_lock = threading.Lock()
_C = OrderedDict()


def build(snap, cdi, gold=None):
    """snapshot `modelos` + CDI diário {d, v (% ao dia)} + ouro em reais {d, v} (history.gold) -> matrizes ações × semanas (numpy)."""
    W = snap["w"]; T = len(W); tick = sorted(snap["a"]); N = len(tick)
    arr = lambda dt=np.float64: np.full((N, T), np.nan, dtype=dt)
    # preço e proventos em float64 (dinheiro); sinais em float32 (só comparações): metade da memória
    C, DV = arr(), arr()
    SI, M2, R12, P1, P3 = (arr(np.float32) for _ in range(5))
    LP = np.ones((N, T), bool)
    for k, t in enumerate(tick):
        a = snap["a"][t]; i0 = a["i0"]
        for M, key in ((C, "c"), (SI, "si"), (M2, "m2"), (R12, "r12"), (P1, "p1"), (P3, "p3")):
            v = a.get(key) or []
            M[k, i0:i0 + len(v)] = [np.nan if x is None else x for x in v]
        DV[k, i0:] = 0
        lp = a.get("lp")
        if lp: LP[k, i0:i0 + len(lp)] = [x != 0 for x in lp]  # 0 = prejuízo no último balanço; sem balanço = liberado
        for j, v in (a.get("dv") or {}).items(): DV[k, i0 + int(j)] = v
    import pandas as pd
    fav, MED = {}, {}
    for key, P in (("p1", P1), ("p3", P3)):
        med = pd.DataFrame(P.T).rolling(MED_SEM, min_periods=MED_SEM // 2).median().to_numpy(dtype=np.float32).T
        fav[key] = (P >= med) & ~np.isnan(P); MED[key] = med
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
    del X, lr, cs, perf, wt, rs  # temporários grandes (4 × ações × semanas): libera antes de seguir
    G = np.full(T, np.nan)  # ouro (R$) no último dia com preço de cada semana
    if gold and gold.get("d"):
        gs = pd.Series(gold["v"], index=pd.to_datetime(gold["d"]), dtype="float64")
        G = gs.reindex(gs.index.union(wk)).ffill(limit=10).reindex(wk).to_numpy()
    # Método Barsi: preço teto = média dos proventos por ação dos últimos 5 anos completos ÷ 6% (só com proventos em 4 dos 5 anos:
    # pagamento regular)
    Y = wk.year.to_numpy(); yrs = sorted(set(Y)); DVn = np.nan_to_num(DV); DPA = np.full((N, len(yrs)), np.nan)
    for j, y in enumerate(yrs):
        m = Y == y; DPA[:, j] = np.where((~np.isnan(C[:, m])).mean(axis=1) > .95, DVn[:, m].sum(axis=1), np.nan)
    TETO = np.full((N, T), np.nan); yi = {y: j for j, y in enumerate(yrs)}
    for y in yrs:
        j = yi[y]; a = DPA[:, max(0, j - BARSI_ANOS):j]
        ok5 = ((~np.isnan(a)).sum(axis=1) >= 4) & ((np.nan_to_num(a) > 0).sum(axis=1) >= 4)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore"); med = np.nanmean(a, axis=1) if a.shape[1] else np.full(N, np.nan)
        TETO[:, Y == y] = np.where(ok5, med / BARSI_DY, np.nan)[:, None]
    ym = [w[:7] for w in W]
    first = next((i for i in range(T) if ok[i]), 0)  # modelos começam no 1º mês com CDB
    return {"w": W, "ym": ym, "tick": tick, "ix": {t: k for k, t in enumerate(tick)}, "C": C, "DV": DV, "SI": SI, "M2": M2, "R12": R12,
            "P": {"p1": P1, "p3": P3}, "FAV": fav, "MED": MED, "HX": HX, "LP": LP, "HW": HW, "MI": np.array([np.nan if x is None else x for x in snap["mi"]], dtype=float), "cdb": cdb, "G": G, "TETO": TETO, "Cf": Cf, "BS": np.zeros(N, bool),
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
            try: gold = history.gold()
            except Exception: gold = None  # sem ouro: a referência Ouro mostra "—"
            with snapshots.HEAVY:  # não monta junto com o histórico de todas as ações (history.all_closes)
                _D["d"] = None; _C.clear(); gc.collect()  # solta as tabelas antigas antes de montar as novas (pico menor no plano gratuito)
                _D["d"] = build(snap, history.bcb("cdi"), gold); _D["key"] = snap.get("fetched_at")
        snapshots.drop("modelos"); del snap; gc.collect()  # o snapshot bruto (listas JSON) não fica na memória
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
    return {"modelos": [{"id": m["id"], "n": m["n"], "vende": m["vende"], **({"ref": True, "nota": m["nota"]} if m.get("ref") else {})} for m in MODELOS + REF], "ini": D["ini"], "fim": D["fim"], "at": D["at"], "tick": D["tick"]}


def _span(D, di, df):
    """Semanas de fim de mês entre di e df (AAAA-MM): mês 1 = fim de di."""
    di = max(di, D["ini"]); ym = D["ym"]
    me = [i for i in range(len(ym)) if D["me"][i] and di <= ym[i] <= df]
    return me


def _signals(D, mid, idx, i):
    """(fica comprado?, pode aplicar?) de cada ação em idx com os dados da semana i (sinal sem estado)."""
    s = _signal(D, mid, idx, i)
    return s & D["LP"][idx, i] if MOD[mid].get("lucro") else s


def _signal(D, mid, idx, i):
    n = len(idx)
    if mid == "hold": return np.ones(n, bool)
    if mid == "medo_mercado": return np.full(n, bool(D["MI"][i] < MEDO))
    if mid == "medo_acao": return D["SI"][idx, i] < MEDO
    if mid in ("media200", "tendencia"): return D["M2"][idx, i] > 0
    if mid == "hibrido": return D["HX"][idx, i] > 0  # (só para o 1º sinal; a simulação usa a exposição HX)
    if mid == "barsi":  # pode aplicar até 20% acima do teto (a simulação guarda a reserva); sem teto: espera no CDB (nunca vende)
        with np.errstate(invalid="ignore"): return D["Cf"][idx, i] <= D["TETO"][idx, i] * BARSI_ACIMA
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
        elif mid == "barsi":  # no teto ou abaixo: todo o caixa; até 20% acima: guarda 10% do total no CDB
            with np.errstate(invalid="ignore"): baixo = D["Cf"][idx, i - 1 if i > 0 else i] <= D["TETO"][idx, i - 1 if i > 0 else i]
            V = A.sh * P + A.cash
            A.buy(buy & ok, P, np.where(baixo, A.cash, np.maximum(0, A.cash - BARSI_RES * V)))
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


def simulate_ref(D, rid, me, ap, wd, rec=False):
    """Referência (CDB ou Ouro) com os mesmos aportes e retiradas dos modelos. -> valor final (nan sem dado) e as linhas mensais."""
    s, e = me[0], me[-1]; meset = {w: j for j, w in enumerate(me)}; G = D["G"]
    g0 = next((i for i in range(s, e + 1) if not np.isnan(G[i])), None) if rid == "ouro" else s
    if g0 is None: return {"v": float("nan"), "rows": [] if rec else None}
    # ouro sem cotação no início do período: os aportes esperam (sem rendimento) e compram na 1ª semana com preço (nota em _refs)
    cash, q, c, n, rows, lastg, pend = 0.0, 0.0, 0, 0, [], G[g0] if rid == "ouro" else G[s], 0.0
    for i in range(s, e + 1):
        if rid == "cdb" and i > s: cash *= D["cdb"][i]
        if not np.isnan(G[i]): lastg = G[i]
        if rid == "ouro" and i == g0 and pend > 0: q += pend * (1 - CUSTO) / lastg; c += 1; pend = 0.0
        j = meset.get(i)
        if j is None: continue
        a, w = (ap[j] if j < len(ap) else 0), (wd[j] if j < len(wd) else 0)
        if rid == "cdb": cash = max(0.0, cash - w) + a
        elif i < g0: pend = max(0.0, pend - w) + a
        else:
            if w > 0 and q > 0: sv = min(q, w / (lastg * (1 - CUSTO))); q -= sv; n += 1
            if a > 0: q += a * (1 - CUSTO) / lastg; c += 1
        v = cash if rid == "cdb" else q * lastg + pend
        if rec: rows.append({"ym": D["ym"][i], "v": float(v), "div": 0.0, "tax": 0.0, "pos": MOD[rid]["n"], "c": c, "s": n})
    return {"v": float(cash if rid == "cdb" else q * lastg + pend), "rows": rows if rec else None, "g0": g0}


def _refs(D, me, ap, wd, apT):
    """Linhas das referências (uma vez, fora das empresas)."""
    out = []
    for m in REF:
        r = simulate_ref(D, m["id"], me, ap, wd); v = r["v"]
        ok = v == v
        nota = m["nota"] + (f"; cotação do ouro só desde {D['ym'][r['g0']][5:7]}/{D['ym'][r['g0']][:4]}: os aportes anteriores compram no primeiro preço"
                            if m["id"] == "ouro" and ok and r.get("g0", me[0]) > me[0] else "")
        out.append({"k": "r", "m": m["id"], "t": m["n"], "v": round(v, 2) if ok else None,
                    "pct": round((v - apT) / apT * 100, 2) if ok and apT > 0 else None, "ir": 0.0, "c": None, "s": None, "nota": nota})
    return out


def rotate(D, mid, gidx, me, ap, wd, tx=None):
    """Rodízio: um modelo que vende, uma empresa do grupo por vez (a de melhor sinal), CDB quando nenhuma está favorável.
    -> valor final, IR e o histórico (por empresa e cada troca com o motivo)."""
    gidx = list(gidx); s, e = me[0], me[-1]; mod = MOD[mid]; nm = D["tick"]
    C, DV = D["C"], D["DV"]
    alg = mid != "tendencia"
    A = Conta(1); cur, k, pdiv, pend = -1, 0, 0.0, None; lastp = {g: C[g, s] for g in gidx}
    per = {g: {"t": nm[g], "c": 0, "sem": 0, "n": 0, "res": 0.0, "ir": 0.0} for g in gidx}
    moves, cdbw, tot = [], 0, 0; nav, navpk, dd, vprev = 1.0, 1.0, 0.0, None
    meset = {w: j for j, w in enumerate(me)}; A.cash += ap[0]; mg = {}  # resultado das vendas do mês por empresa (para dividir o IR)
    pct = lambda x: f"{x / 10:.1f}%".replace(".", ",")

    def score(g, i):  # (força do sinal, favorável?); modelos com "lucro": só com lucro no último balanço publicado
        ok = bool(D["LP"][g, i]) or not mod.get("lucro")
        if alg: return D["P"][mod["p"]][g, i], bool(D["FAV"][mod["p"]][g, i]) and ok
        return D["R12"][g, i], bool(D["M2"][g, i] > 0) and ok

    def strong(g, i):  # bom momento para comprar: chance bem acima da mediana do ano (algoritmos) ou alta forte em 12 meses (Tendência)
        if alg: return D["P"][mod["p"]][g, i] - D["MED"][mod["p"]][g, i] >= MARGEM[mid]
        return D["M2"][g, i] > 0 and D["R12"][g, i] >= FORTE_R12

    def why(g, i):
        sc, _ = score(g, i)
        return f"chance de alta {pct(sc)}" if alg else f"alta de {pct(sc)} em 12 meses e acima da média de 200 dias"

    def sell_cur(P, i, motivo):
        nonlocal cur, pdiv
        b0 = A.basis[0]; g = A.sell(np.array([True]), np.array([P]))[0]
        per[cur]["res"] += g; mg[cur] = mg.get(cur, 0) + g; per[cur]["n"] += 1
        moves.append({"d": D["w"][i], "de": nm[cur], "para": None, "m": motivo, "vv": round(b0 + g, 2),
                      "pct": round((g + pdiv) / b0 * 100, 2) if b0 > 0 else None}); cur = -1; pdiv = 0.0  # resultado com proventos

    for i in range(s, e + 1):
        for g in gidx:
            if not np.isnan(C[g, i]): lastp[g] = C[g, i]
        if i > s:
            A.cash *= D["cdb"][i]
            if cur >= 0:
                d = A.sh[0] * np.nan_to_num(DV[cur, i]); A.cash += d; A.mdiv += d; A.divT += d; per[cur]["res"] += d; pdiv += d
        if i > 0:
            # só entra numa empresa em bom momento (sinal forte); senão o dinheiro espera no CDB
            cand = [(score(g, i - 1)[0], g) for g in gidx if not np.isnan(C[g, i]) and score(g, i - 1)[1] and not np.isnan(score(g, i - 1)[0]) and strong(g, i - 1)]
            best = max(cand)[1] if cand else -1
            saiu = False
            if cur >= 0:
                k += 1
                sc, fav = score(cur, i - 1)
                if not fav and k >= mod["min"] and not np.isnan(C[cur, i]):
                    sell_cur(lastp[cur], i, "previsão desfavorável" if alg else "abaixo da média de 200 dias"); saiu = True  # espera ao menos 1 semana
                elif best >= 0 and best != cur and k >= TROCA_SEM and not np.isnan(C[cur, i]) and score(best, i - 1)[0] >= sc + MARGEM[mid]:
                    sell_cur(lastp[cur], i, f"{nm[best]} com sinal melhor")  # troca direta: a outra está em bom momento agora
            if cur < 0 and best >= 0 and not saiu:
                cur, k = best, 0; per[cur]["c"] += 1
                if moves and moves[-1]["para"] is None and moves[-1]["d"] == D["w"][i]: moves[-1]["para"] = nm[cur]; moves[-1]["m2"] = why(cur, i - 1)
                else: moves.append({"d": D["w"][i], "de": None, "para": nm[cur], "m": None, "m2": why(cur, i - 1)})
                pend = moves[-1]
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
        if cur >= 0:
            c0 = A.cash[0]; A.buy(np.array([True]), np.array([P]))
            if pend is not None: pend["vc"] = round(c0 - A.cash[0], 2); pend = None  # valor comprado na entrada
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
        if mid in MOD and MOD[mid].get("ref"):  # CDB / Ouro: não depende da empresa
            r = simulate_ref(D, mid, me, ap, wd, rec=True)["rows"]
            if not r: return {"error": f"{MOD[mid]['n']} sem dados em {D['ym'][me[0]]}."}
            out = dict(ini, tab=[dict(x, sem=x["v"], com=x.pop("v")) for x in r])
            _C[key] = out
            return out
        if t not in D["ix"] or mid not in MOD: return {"error": "Empresa ou modelo sem dados."}
        k = D["ix"][t]
        if not ok(k): return {"error": f"{t} ainda não negociava em {D['ym'][me[0]]}."}
        com = simulate(D, mid, [k], me, ap, wd, tx, True, True)["rows"][0]
        sem = simulate(D, mid, [k], me, ap, wd, tx, False, True)["rows"][0]
        out = dict(ini, tab=[dict(c, sem=x["v"], com=c.pop("v")) for c, x in zip(com, sem)])
    else:
        mids = [m["id"] for m in MODELOS] if req.get("modelo") == "*" else [req.get("modelo")]
        if any(m not in MOD for m in mids): return {"error": "Modelo desconhecido."}
        rows = _refs(D, me, ap, wd, apT)  # CDB e Ouro: uma vez, entre os modelos pelo rendimento
        mids = [m for m in mids if not MOD[m].get("ref")] or ["hold"]
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
                fo = fora_barsi(D, uni, me) if mid == "barsi" else np.zeros(len(uni), bool)
                best = sorted((q for q in range(len(uni)) if not fo[q]), key=lambda q: -r["v"][q])[:10]
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
                             "c": int(r["c"][0]), "s": int(r["s"][0]), **({"fora": True} if mid == "barsi" and fora_barsi(D, [k], me)[0] else {})})
        rows.sort(key=lambda x: (x["k"] != "g", -(x["pct"] if x["pct"] is not None else -1e9)))  # grupos; depois modelos e CDB/Ouro pelo rendimento
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


PONTOS = (21, 18, 15, 12, 10, 8, 6, 4, 2, 1)  # pontos por colocação em cada empresa (1º = 21 …; do 11º em diante, 0)


def _nmean(x):
    x = x[~np.isnan(x)]
    return float(x.mean()) if len(x) else float("-inf")


def ranking(V, nref=0):
    """V: (modelos + nref referências no fim) × empresas (valor final; nan = fora, ex.: Método Barsi fora do método).
    -> posição pelo rendimento (0 = 1º; -1 = fora), contagem por posição, ordem das Colocações (mais 1º lugares; empate -> mais 2º…;
    empate em tudo -> maior média) e pontos (PONTOS pela colocação; as referências ficam sempre com as últimas colocações)."""
    n = V.shape[0]; ok = ~np.isnan(V)
    def rank(K):
        r = (-np.where(ok, K, -np.inf)).argsort(axis=0, kind="stable").argsort(axis=0)
        return np.where(ok, r, -1)
    rk = rank(V)
    K = V.copy()
    if nref: K[n - nref:] -= 1e15  # referências abaixo de todos os modelos (entre elas, pelo rendimento)
    rp = rank(K); sc = np.array(PONTOS + (0,) * n)
    pts = np.where(ok, sc[np.maximum(rp, 0)], 0).sum(axis=1)
    cnt = np.array([[int((rk[i] == p).sum()) for p in range(n)] for i in range(n)])
    order = sorted(range(n), key=lambda i: tuple(-cnt[i]) + (-_nmean(V[i]),))
    return rk, cnt, order, pts


def fora_barsi(D, idx, me):
    """Empresas fora do Método Barsi no período: setor não perene ou sem proventos regulares (sem preço teto em nenhum mês)."""
    T = D["TETO"][np.asarray(idx)][:, me[0]:me[-1] + 1]
    return ~D["BS"][np.asarray(idx)] | np.isnan(T).all(axis=1)


def compare(D, tickers, di, df, aps, wd=None, tx=None, grupos=None):
    """Todos os modelos em cada empresa com os mesmos aportes (aps: aporte de cada mês, mês 1 = valor inicial) e retiradas (wd).
    Comparar → Modelos e Previsão com o card Modelos em Todos (grupos: rodízio dos modelos que trocam de empresa).
    -> empresas usadas (com preço no início), lucro %, valor final, IR, compras/vendas por modelo × empresa, posições e resumos."""
    me = _span(D, di, df)
    if len(me) < 2: return {"error": f"Período curto ou fora dos dados dos modelos ({D['ini']} a {D['fim']})."}
    aps = ([max(0.0, float(x or 0)) for x in aps] + [0.0] * len(me))[:len(me)]
    wd = ([max(0.0, float(x or 0)) for x in (wd or [])] + [0.0] * len(me))[:len(me)]
    key = repr(("cmp", D["at"], tuple(tickers), di, df, aps, wd, tx, repr(grupos)))
    if key in _C: _C.move_to_end(key); return _C[key]
    apT = sum(aps)
    idx = [D["ix"][t] for t in dict.fromkeys(tickers) if t in D["ix"] and not np.isnan(D["C"][D["ix"][t], me[0]])]
    if not idx: return {"error": f"Nenhuma das empresas tinha preço em {D['ym'][me[0]]}."}
    R = [simulate(D, m["id"], idx, me, aps, wd, tx) for m in MODELOS]
    fora = fora_barsi(D, idx, me) if len(idx) > 1 else np.zeros(len(idx), bool)  # uma empresa só: calcula mesmo fora do método
    ib = [m["id"] for m in MODELOS].index("barsi"); R[ib]["v"] = np.where(fora, np.nan, R[ib]["v"])
    refs = _refs(D, me, aps, wd, apT); z = np.zeros(len(idx))
    R += [{"v": np.full(len(idx), np.nan if r["v"] is None else r["v"]), "ir": z, "c": z, "s": z} for r in refs]
    M = MODELOS + REF; nm = len(M)
    V = np.array([r["v"] for r in R])
    P = (V / apT - 1) * 100 if apT > 0 else np.zeros_like(V)
    rk, cnt, order, pts = ranking(V, len(REF))
    hold = V[[m["id"] for m in M].index("hold")]
    J = lambda A: [[None if x != x else x for x in row] for row in np.round(A, 2).tolist()]  # nan -> null (JSON)
    def res(i, m):
        ok = ~np.isnan(V[i]); k = int(ok.sum())
        if not k: return {"m": m["id"], "media": None, "vmedio": None, "mediana": None, "ganha": None, "pior": None, "pos": cnt[i].tolist(), "pts": 0, "ptsm": 0, "n": 0}
        return {"m": m["id"], "media": round(float(P[i][ok].mean()), 2), "vmedio": round(float(V[i][ok].mean()), 2), "mediana": round(float(np.median(P[i][ok])), 2),
                "ganha": None if m["id"] == "hold" else round(float((V[i][ok] > hold[ok]).mean() * 100), 1), "pior": int(rk[i].max()) + 1, "pos": cnt[i].tolist(),
                "pts": int(pts[i]), "ptsm": round(float(pts[i]) / k, 2), "n": k, **({"ref": True} if m.get("ref") else {})}
    big = lambda i: -_nmean(P[i])  # ord_pts: pela média de pontos (o Método Barsi só conta nas empresas do método)
    out = {"ini": D["ym"][me[0]], "fim": D["ym"][me[-1]], "meses": len(me), "apT": apT, "pedidas": len(dict.fromkeys(tickers)),
           "t": [D["tick"][k] for k in idx], "m": [m["id"] for m in M], "p": J(P), "rk": rk.tolist(),
           "v": J(V), "ir": np.round(np.array([r["ir"] for r in R]), 2).tolist(),
           "c": np.array([r["c"] for r in R]).astype(int).tolist(), "s": np.array([r["s"] for r in R]).astype(int).tolist(),
           "res": [res(i, m) for i, m in enumerate(M)], "ord_media": sorted(range(nm), key=big), "ord_pos": order,
           "ord_pts": sorted(range(nm), key=lambda i: (-(pts[i] / max(1, (~np.isnan(V[i])).sum())), -pts[i], order.index(i))), "ref": refs, "fora": int(fora.sum()), "pontos": list(PONTOS)}
    if grupos is not None:  # rodízio nos grupos (Previsão com o card Modelos em Todos)
        pc = lambda v: round((v - apT) / apT * 100, 2) if apT > 0 else None
        out["g"] = []
        for m in MODELOS:
            if not m["vende"] or m.get("frac"): continue
            for g in grupos[:12]:
                gi = [D["ix"][t] for t in (g.get("t") or [])[:30] if t in D["ix"]]
                if len(gi) < 2: continue
                r = rotate(D, m["id"], gi, me, aps, wd, tx)
                out["g"].append({"m": m["id"], "n": str(g.get("n") or "")[:60], "t": [D["tick"][x] for x in gi], "v": round(r["v"], 2), "pct": pc(r["v"]),
                                 "ir": round(r["ir"], 2), "c": r["c"], "s": r["s"], "hist": r["hist"]})
        out["g"].sort(key=lambda x: -(x["pct"] or -1e9))
    _C[key] = out
    while len(_C) > 60: _C.popitem(last=False)
    return out
