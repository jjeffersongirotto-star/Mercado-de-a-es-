"""Previsão → card Modelos: regras dos modelos (fonte única: MODELOS) e simulação semanal com custos, IR e CDB.
Sinais semanais de cada ação: snapshot `modelos` (scripts/build_modelos.py). CDB: história do CDI do Banco Central (history.bcb).
Cada semana usa o sinal da semana anterior (decide com o fechamento de sexta e opera na semana seguinte).
Aportes e retiradas entram no último pregão de cada mês (mês 1 = valor inicial), como na tabela da Previsão.
Imposto: 15% do lucro líquido das vendas do mês quando as vendas passam de R$ 20 mil; prejuízo compensa os meses seguintes.
Proventos: mesma regra de imposto da tabela (automático = 10% no mês acima de R$ 50 mil, ou o % escolhido)."""
import gc, hashlib, json, math, os, threading, time, unicodedata, warnings, zlib
import valor_justo
from collections import OrderedDict
import numpy as np

# id, nome, vende? e regras (o painel ⓘ → Modelos explica cada um com estas regras)
MODELOS = [
    {"id": "hold", "n": "Buy and Hold", "vende": False},
    {"id": "medo_mercado", "n": "Aporta com medo do mercado", "vende": False},
    {"id": "medo_acao", "n": "Aporta com medo da ação", "vende": False},
    {"id": "media200", "n": "Aporta acima da média de 200 dias", "vende": False},
    {"id": "alg1", "n": "Algoritmo 1 mês", "vende": True, "p": "p1", "min": 12},
    {"id": "alg3", "n": "Algoritmo 3 meses", "vende": True, "p": "p3", "min": 12, "lucro": True},
    {"id": "tendencia", "n": "Análise técnica", "vende": True, "min": 4, "lucro": True},
    # métodos das matérias do painel ⓘ → Métodos de investimento → Para ler (regras em METODO; sinais em set_metodos)
    {"id": "value", "n": "Value (Graham)", "vende": True, "min": 4, "sig": "VAL", "sc": "VALS", "mg": .10},
    {"id": "growth", "n": "Growth (O'Neil)", "vende": True, "min": 4, "sig": "GRO", "sc": "GROS", "mg": .10},
    {"id": "garp", "n": "GARP (PEG)", "vende": True, "min": 4, "sig": "GARP", "sc": "GARPS", "mg": .20},
    {"id": "fatores", "n": "Fatores", "vende": True, "min": 4, "sig": "FAT", "sc": "FATS", "mg": .10},
    {"id": "hibrido", "n": "Híbrido adaptativo", "vende": False, "frac": True, "x": "HX"},
    {"id": "adapt", "n": "Adaptativo (aprende)", "vende": False, "frac": True, "x": "AX"},
    {"id": "barsi", "n": "Método Barsi", "vende": False, "lucro": True},
]
# referências fora das empresas: mesmo dinheiro, mesmos aportes e retiradas; entram nas tabelas pelo rendimento e nos Pontos ficam
# sempre com as últimas colocações (ranking)
REF = [
    {"id": "cdb", "n": "CDB", "vende": False, "ref": True,
     "nota": "100% do CDI por dia útil; nas retiradas paga IR regressivo sobre o rendimento (22,5% até 180 dias … 15% acima de 2 anos) e IOF antes de 30 dias; o valor final é o saldo antes do IR, como no extrato do banco"},
    {"id": "ouro", "n": "Ouro", "vende": False, "ref": True, "nota": "ouro em reais, custo de 0,3% em cada compra; nunca vende"},
    {"id": "ibov", "n": "Ibovespa", "vende": False, "ref": True, "nota": "pontos do índice (retorno total: os proventos ficam reinvestidos no índice, como num fundo que acompanha o Ibovespa), custo de 0,3% em cada compra; nunca vende"},
    {"id": "idiv", "n": "IDIV", "vende": False, "ref": True, "nota": "índice de dividendos da B3 (pontos do índice, retorno total: os proventos ficam reinvestidos; série histórica da B3 desde 2005), custo de 0,3% em cada compra; nunca vende"},
]
# ETFs (snapshot modelos → etf: tipo br/ext/rf/com): sem balanço nem proventos regulares -> só os modelos de preço; renda fixa: só Buy and Hold
# (comparado com o CDB, que já entra como referência). Sem nota de qualidade e sem venda por pontos (_venda)
ETF_MOD = {"acoes": ("hold", "medo_mercado", "medo_acao", "media200", "alg1", "alg3", "tendencia", "hibrido", "adapt"), "rf": ("hold",)}
REF_SERIE = {"ouro": "G", "ibov": "IB", "idiv": "IV"}  # série de preço de cada referência que compra cotas (CDB: rende o CDI)
# base dos modelos = empresas listadas hoje: as que saíram da bolsa ou faliram no período não estão -> resultados longos ficam otimistas
AVISO = "Base histórica: em Todas entram também as empresas que saíram da bolsa desde 1998 (vendidas pelo último preço); elas ficam sem proventos e, antes de 2010, sem balanços, o que pode deixar os resultados um pouco diferentes do real."
MOD = {m["id"]: m for m in MODELOS + REF}
# Método Barsi: só setores perenes (fonte única; o chat e o painel ⓘ leem daqui): subsetor do site ou segmento oficial da B3
PERENE_RX = r"^(Bancos|Energia Elétrica|Água e Saneamento|Seguradoras|Resseguradoras|Corretoras de Seguros|Telecomunicações|Papel e Celulose|Químicos)"
PERENE_TXT = "bancos, energia elétrica, saneamento, seguros, telecomunicações, papel e celulose e químicos"  # setores perenes do Método Barsi, em texto (ⓘ e chat); a regra é PERENE_RX
# teto = média dos proventos por ação dos 5 anos completos anteriores ÷ 6% (pagou em pelo menos 4 deles); compra com todo o caixa
# só com o preço no teto ou abaixo; acima, aporte e proventos esperam no CDB
BARSI_DY, BARSI_ANOS = .06, 5
# caixa máximo no CDB (fração do patrimônio): acima disso e sem empresa no teto ou abaixo, compra a menos esticada (menor prêmio sobre o
# teto); com empresa no teto, o excedente vai para elas (Método Barsi, simulação de uma empresa e modo Grupo)
BARSI_CAIXA = .10


def perene(r, cad=None):
    """A empresa (linha de /api/data) é de setor perene do Método Barsi? cad: cadastro da B3 {raiz: [nome, segmento]}."""
    import re
    sub = r.get("subsetor") or ""; seg = ((cad or {}).get(r["ticker"][:4]) or [None, ""])[1] or ""
    if any(re.search(PERENE_RX, x) for x in (sub, r.get("setor") or "", seg)): return True
    return r.get("setor") == "Utilities" and not sub and seg in ("", "Não Classificados", "Não Classificado")




def _hib(Cf, DV, cdb, X, JT=None, bloco=64):
    """Híbrido: exposição (0, 25, 50, 75 ou 100%) = média das exposições X dos especialistas (ordem de HIB), pesadas pelo retorno de cada
    um nas últimas HIB_SEM semanas (ação + proventos brutos quando dentro, CDB quando fora); decide com dados até a semana (opera na seguinte).
    -> (HX, HA = especialista de maior peso, HP = peso dele em %). Em blocos de `bloco` empresas: pico de memória pequeno no plano gratuito
    (o servidor caiu por memória com todas de uma vez)."""
    N, T = Cf.shape; K = len(X); c = (cdb[1:] - 1).astype(np.float32)
    HX = np.zeros((N, T), np.float32); HA = np.zeros((N, T), np.uint8); HP = np.zeros((N, T), np.uint8)
    for a in range(0, N, bloco):
        sl = slice(a, min(N, a + bloco)); cf = Cf[sl]; dv = np.nan_to_num(DV[sl]) + (np.nan_to_num(JT[sl]) if JT is not None else 0)
        rs = np.zeros(cf.shape, np.float32)
        with np.errstate(invalid="ignore", divide="ignore"): rs[:, 1:] = np.nan_to_num((cf[:, 1:] + dv[:, 1:]) / cf[:, :-1] - 1)
        wt = np.zeros((K,) + cf.shape, np.float32)
        for k in range(K):
            x = np.asarray(X[k][sl], np.float32); w = wt[k]
            w[:, 1:] = np.log1p(x[:, :-1] * rs[:, 1:] + (1 - x[:, :-1]) * c[None, :])
            np.cumsum(w, axis=1, out=w); w[:, HIB_SEM:] -= w[:, :-HIB_SEM].copy()
        wt -= wt.max(axis=0, keepdims=True); wt *= HIB_ETA; np.exp(wt, out=wt); wt /= wt.sum(axis=0, keepdims=True)
        hx = np.zeros(cf.shape, np.float32)
        for k in range(K): hx += wt[k] * np.asarray(X[k][sl], np.float32)
        wt *= 100; np.round(wt, out=wt)  # peso em % inteiro (empate = o primeiro de HIB, como antes)
        HX[sl] = np.round(hx * 4) / 4; HA[sl] = wt.argmax(axis=0); HP[sl] = wt.max(axis=0)
    return HX, HA, HP


def set_metodos(D, rows):
    """Sinais dos modelos de método (METODO); refaz o híbrido com eles. Valor de mercado da época = preço da época × ações em circulação do
    último balanço publicado (SHW, CVM) × fator da classe (UNIT/ON/PN: valor de mercado de hoje em /api/data ÷ preço de hoje × ações do
    último balanço; só converte a classe, não a base acionária; sem /api/data (saiu da bolsa) = 1, UNIT = sem sinal).
    Só recalcula quando muda a versão dos dados ou o conjunto de empresas com valor de mercado."""
    import pandas as pd
    vm = {r["ticker"]: (r.get("v") or {}).get("valmerc") for r in rows}
    vm = {t: v for t, v in vm.items() if v and v > 0 and t in D["ix"]}
    key = (D.get("at"), tuple(sorted(vm)))
    if D.get("_mk") == key or "FM" not in D or "SHW" not in D["FM"]: return
    FM, Cf, N, T = D["FM"], D["Cf"], *D["C"].shape
    # fator da classe e da escala: a CVM informa ações em unidades ou em milhares (varia por empresa) -> f perto de 1 ou de 1.000
    SH = FM["SHW"]; F = np.full(N, np.nan); lo, hi_ = METODO["classe"]
    for t, v in vm.items():
        k = D["ix"][t]; q = SH[k][~np.isnan(SH[k])]
        if len(q) and Cf[k, -1] > 0:
            f = v / (Cf[k, -1] * q[-1]); F[k] = f if lo <= f <= hi_ or lo <= f / 1000 <= hi_ else np.nan  # fora das faixas: dado suspeito
    # sem /api/data (saiu da bolsa): escala pelo giro (volume diário ÷ valor de mercado) mais perto do giro mediano das empresas de hoje
    with np.errstate(invalid="ignore", divide="ignore"):
        gk = lambda k, f: np.nanmedian(D["VL"][k] / (Cf[k] * SH[k] * f)) if np.isfinite(D["VL"][k] / (Cf[k] * SH[k])).any() else np.nan
        g0 = np.nanmedian([gk(k, F[k]) for k in np.flatnonzero(np.isfinite(F))] or [np.nan])
        for k in np.flatnonzero(~np.isfinite(F)):
            if D["tick"][k] in vm or D["tick"][k][-2:] == "11" or not np.isfinite(g0): continue  # UNIT sem /api/data: sem sinal
            d = {f: abs(np.log(gk(k, f) / g0)) for f in (1.0, 1000.0)}; f = min(d, key=lambda x: d[x] if np.isfinite(d[x]) else np.inf)
            if np.isfinite(d[f]) and d[f] < np.log(30): F[k] = f
    with np.errstate(invalid="ignore", divide="ignore"):
        C32 = Cf.astype(np.float32); MC = C32 * SH; MC *= F[:, None].astype(np.float32); NI, EQ, G1, G3 = FM["NIW"], FM["EQW"], FM["G1"], FM["G3"]
        PL = np.where((NI > 0) & (MC > 0), MC / NI, np.nan)
        VJ = np.sqrt(np.where((NI > 0) & (EQ > 0), 22.5 * NI * EQ, np.nan)); VALS = (1 - MC / VJ).astype(np.float32); del VJ  # margem sobre o justo
        PEG = np.where(G3 > 0, PL / (100 * G3), np.nan).astype(np.float32); del PL
        hi = pd.DataFrame(C32.T).rolling(52, min_periods=26).max().to_numpy(np.float32).T
        ib = pd.Series(D["IB"]); alta = (ib > ib.rolling(40, min_periods=20).mean()).to_numpy()
        Q = FM["Q"]; M = METODO
        ent = {"VAL": (VALS >= M["v_entra"]) & (Q >= M["v_nota"]), "GRO": (G1 >= M["g_ano"]) & (G3 >= M["g_3a"]) & (C32 >= (1 - M["g_max"]) * hi) & alta[None, :],
               "GARP": (PEG > 0) & (PEG < M["p_entra"]) & (G3 >= M["p_cres"])}
        sai = {"VAL": ~(VALS >= 0), "GRO": ~(G1 >= 0) | ~alta[None, :], "GARP": ~(PEG > 0) | (PEG > M["p_sai"]) | ~(G3 >= M["p_cres"] / 2)}
        del hi
        # fatores: posição (0–1) entre as empresas da semana em cada fator; média com pelo menos f_min fatores (somada um fator por vez)
        def rk(A):
            m = np.isnan(A); o = np.argsort(np.where(m, np.inf, A), axis=0, kind="stable").astype(np.int32)
            r = np.empty_like(o); np.put_along_axis(r, o, np.arange(N, dtype=np.int32)[:, None], axis=0); del o
            x = (r + 1).astype(np.float32); x /= np.maximum((~m).sum(axis=0), 1).astype(np.float32); x[m] = np.nan; return x
        rr = np.zeros((N, T), np.float32); rr[:, 1:] = C32[:, 1:] / C32[:, :-1] - 1
        vol = np.array(pd.DataFrame(rr.T).rolling(52, min_periods=26).std().to_numpy(np.float32).T); del rr
        vol[np.isnan(C32)] = np.nan; np.negative(vol, out=vol)
        S, nf = np.zeros((N, T), np.float32), np.zeros((N, T), np.int8)
        EE = D["EK"] != "" if "EK" in D else np.zeros(N, bool)  # ETFs fora da posição entre as empresas
        def sem_etf(a):
            if EE.any(): a = np.array(a, np.float32); a[EE] = np.nan
            return a
        for A in (lambda: np.where(MC > 0, NI / MC, np.nan).astype(np.float32), lambda: Q, lambda: D["R12"], lambda: vol):
            x = rk(sem_etf(np.asarray(A(), np.float32))); ok = ~np.isnan(x); S += np.where(ok, x, 0); nf += ok; del x, ok
        del vol; FATS = np.where(nf >= M["f_min"], S / np.maximum(nf, 1), np.nan).astype(np.float32); del S, nf
        ent["FAT"] = FATS >= M["f_entra"]; sai["FAT"] = ~(FATS >= M["f_sai"])
    out = {}
    for k in ent:  # estado com entrada e saída diferentes (não fica entrando e saindo na fronteira); Growth: stop sobre o preço de entrada
        st = np.zeros(N, bool); pe = np.full(N, np.nan); X = np.zeros((N, T), bool); E_, S_ = ent[k], sai[k]
        for i in range(T):
            c = C32[:, i]
            out_ = S_[:, i] | np.isnan(c)
            if k == "GRO": out_ |= c < (1 - M["g_stop"]) * pe
            new = ~st & E_[:, i]; st = np.where(st, ~out_, E_[:, i]); pe = np.where(new, c, np.where(st, pe, np.nan)); X[:, i] = st
        out[k] = X
    del MC, C32, ent, sai; np.negative(PEG, out=PEG)  # temporários soltos antes do híbrido (pico menor)
    D.update(out); D.update({"VALS": VALS, "GROS": G1, "GARPS": PEG, "FATS": FATS})
    hx = [np.ones((N, T), bool), D["FAV"]["p1"], D["FAV"]["p3"], np.nan_to_num(D["M2"]) > 0, out["VAL"], out["GRO"], out["GARP"], out["FAT"]]
    D["HX"], D["HA"], D["HP"] = _hib(Cf, D["DV"], D["cdb"], hx, D["JT"])
    e = np.flatnonzero(D["EK"] != "") if "EK" in D else []
    if len(e):  # ETF: sem balanço -> o híbrido usa só os 4 especialistas de preço (os de método ficariam sempre fora)
        D["HX"][e], D["HA"][e], D["HP"][e] = _hib(Cf[e], D["DV"][e], D["cdb"], [x[e] for x in hx[:4]], D["JT"][e])
    D["_mk"] = key; _cclear()


def _ord_ganho(D, k, compra):
    """Ganho (log) de uma ordem com preço limite a k volatilidades, decidida na semana d, sobre comprar/vender no fechamento da semana
    seguinte (como era antes): executa na 1ª semana d+1..d+ORD_SEM em que a mínima (compra) ou a máxima (venda) toca o limite, senão no
    fechamento da última. -> matriz N × T (coluna d; NaN sem dados ou sem as semanas seguintes ainda)."""
    C, Cf, LO, HI = D["C"], D["Cf"], D["LO"], D["HI"]; N, T = C.shape
    with np.errstate(invalid="ignore", divide="ignore"):
        f32 = np.float32; dd = np.clip(k * D["VW"], ORD_MIN, ORD_MAX).astype(f32)  # float32: pico de memória menor no plano gratuito
        lim = Cf.astype(f32) * ((1 - dd) if compra else (1 + dd)); del dd
        px = np.full((N, T), np.nan, f32); feito = np.zeros((N, T), bool)
        for j in range(1, ORD_SEM + 1):
            lo = LO[:, j:]; hi = HI[:, j:]; L = lim[:, :T - j]
            toc = ~feito[:, :T - j] & ((lo <= L * (1 - ORD_FILA)) if compra else (hi >= L * (1 + ORD_FILA)))
            px[:, :T - j] = np.where(toc, np.minimum(L, hi) if compra else np.maximum(L, lo), px[:, :T - j]); feito[:, :T - j] |= toc
        del lim
        px[:, :T - ORD_SEM] = np.where(feito[:, :T - ORD_SEM], px[:, :T - ORD_SEM], C[:, ORD_SEM:]); px[:, T - ORD_SEM:] = np.nan
        m1 = np.full((N, T), np.nan, f32); m1[:, :T - 1] = C[:, 1:]
        G = (np.log(m1 / px) if compra else np.log(px / m1)).astype(f32)
    return G


def _pl_rel(Cf, FM):
    """P/L de cada semana ÷ mediana do próprio P/L nas últimas CARO['anos'] (preço × ações do último balanço ÷ lucro anual; o fator
    da classe de ação se cancela na divisão) -> matriz N × T float32 (NaN: sem lucro ou sem histórico). > CARO['pl'] = cara agora."""
    import pandas as pd
    if "NIW" not in FM: return np.full(Cf.shape, np.nan, np.float32)
    # ações: as do balanço da época; antes do 1º balanço com composição do capital, as do 1º (sem nenhum: constante, se cancela)
    SH = pd.DataFrame(FM["SHW"].T).ffill().bfill().fillna(1.0).to_numpy(np.float32).T if "SHW" in FM else 1.0
    with np.errstate(invalid="ignore", divide="ignore"):
        NI = FM["NIW"]; pl = np.where(NI > 0, Cf.astype(np.float32) * SH / NI, np.nan).astype(np.float32); del SH
        med = pd.DataFrame(pl.T).rolling(52 * CARO["anos"], min_periods=52 * CARO["min_anos"]).median().to_numpy(np.float32).T
        pl /= med
    return pl


def _calma_mats(Cf, VW, LP, Q, NT):
    """Anti-emoção (CALMA): na semana d, a variação foi rápida (|var| > CALMA['vol'] volatilidades)? -> CV (venda espera: queda rápida
    com a empresa bem ou o mercado caindo junto) e CC (compra espera: alta rápida), matrizes N × T de bool (coluna = semana dos dados)."""
    import pandas as pd
    N, T = Cf.shape; CV = np.zeros((N, T), bool); CC = np.zeros((N, T), bool)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.full((N, T), np.nan, np.float32); r[:, 1:] = Cf[:, 1:] / Cf[:, :-1] - 1
        v0 = np.full((N, T), np.nan, np.float32); v0[:, 1:] = VW[:, :-1]  # volatilidade antes da semana
        with warnings.catch_warnings():
            warnings.simplefilter("ignore"); mk = np.nanmedian(r, axis=0) if N else np.zeros(T, np.float32)  # mercado: mediana das ações
        lim = CALMA["vol"] * v0
        nt = pd.DataFrame(NT.T).rolling(NOTICIA["semanas"], min_periods=1).sum().to_numpy(np.float32).T
        bem = LP & ~(np.nan_to_num(Q, nan=100) < CALMA["nota"]) & (nt > NOTICIA["ruim"])  # sem nota (ETF, sem balanço): conta como bem
        junto = mk[None, :] <= CALMA["mercado"] * r
        CV[:] = (r < -lim) & (bem | junto); CC[:] = r > lim
    return CV, CC


def _adp_x(D, i, NTc):
    """Exposição (0/1) de cada especialista de ADP na semana i, só com dados até a semana i -> matriz K × N."""
    N = D["C"].shape[0]; z = np.zeros(N, bool); g = lambda k: D[k][:, i] if k in D else z; LP = D["LP"][:, i]
    with np.errstate(invalid="ignore"):
        Q = D["FM"]["Q"][:, i] if "FM" in D and "Q" in D["FM"] else np.full(N, np.nan)
        nt = NTc[:, i] - (NTc[:, i - NOTICIA["semanas"]] if i >= NOTICIA["semanas"] else 0)
        X = [np.ones(N, bool), np.full(N, bool(D["MI"][i] < MEDO)), D["SI"][:, i] < MEDO, np.nan_to_num(D["M2"][:, i]) > 0,
             D["FAV"]["p1"][:, i], D["FAV"]["p3"][:, i] & LP, (np.nan_to_num(D["M2"][:, i]) > 0) & LP, g("VAL"), g("GRO"), g("GARP"), g("FAT"),
             D["HX"][:, i], (D["Cf"][:, i] <= D["TETO"][:, i]) & D["BS"] & LP, nt > NOTICIA["ruim"], np.nan_to_num(Q) >= ADP_NOTA]
    return np.array([np.asarray(x, np.float32) for x in X])


def _adapt(D):
    """Adaptativo (aprende): a cada semana mede o resultado de cada especialista (ação + proventos quando dentro, CDB quando fora) em
    todas as empresas de cada cenário (ADP_CTX) e soma com memória que decai (ADP_MEIA); o peso de cada especialista no cenário é
    exp(ADP_ETA × soma). Exposição da semana = média das exposições dos especialistas pesada pelos pesos aprendidos ATÉ a semana (vale
    na seguinte); ETF só com os especialistas de preço. -> D["AX"] (0–100% em passos de 25), "AA" (especialista de maior peso), "AP"
    (peso em %), "ADPS" (o que aprendeu: pesos por cenário e acerto das notícias ruins)."""
    import pandas as pd
    C, Cf, N, T = D["C"], D["Cf"], *D["C"].shape; K = len(ADP); dec = .5 ** (1 / ADP_MEIA)
    ib = pd.Series(D["IB"]); queda = ~(ib > ib.rolling(40, min_periods=20).mean()).to_numpy()
    sec = D.get("SEC3", np.full(N, 2)); EK = D["EK"] != "" if "EK" in D else np.zeros(N, bool)
    setor = np.where(D["BS"], 0, np.where(sec == 1, 1, 2))
    NTc = np.cumsum(D["NT"], axis=1, dtype=np.float32) if "NT" in D else np.zeros((N, T), np.float32)
    DVg = np.nan_to_num(D["DV"]) + np.nan_to_num(D["JT"])
    S = np.zeros((len(ADP_CTX), K)); AX = np.zeros((N, T), np.float32); AA = np.zeros((N, T), np.uint8); AP = np.zeros((N, T), np.uint8)
    tem_hl = "LO" in D and np.isfinite(D["LO"]).any()
    GB = [_ord_ganho(D, k, True) for k in ORD_KS] if tem_hl else None; GS = [_ord_ganho(D, k, False) for k in ORD_KS] if tem_hl else None
    SB, SS = np.zeros((len(ADP_CTX), len(ORD_KS))), np.zeros((len(ADP_CTX), len(ORD_KS))); dko = .5 ** (1 / ADP_MEIA)
    ODc, ODv = D["ODI"].copy(), D["ODI"].copy(); CX = np.zeros((N, T), np.uint8)  # distância escolhida por ação/semana; cenário de cada semana
    CVa, CCa = D["CV"].copy(), D["CC"].copy(); SC = np.zeros((len(ADP_CTX), 2))  # anti-emoção: esperar rende? (venda, compra) por cenário
    from collections import deque
    nb = nh = 0; Xp = None; pre = np.arange(K) < ADP_PRECO; kn = ADP.index("noticias"); hn = deque(maxlen=5)
    for i in range(T):
        mi = D["MI"][i]; m = 0 if mi < MEDO else 2 if mi > 55 else 1
        ctx = (m * 2 + int(bool(queda[i]))) * 3 + setor
        X = _adp_x(D, i, NTc); CX[:, i] = ctx
        if tem_hl and i >= ORD_SEM + 1:  # ordens decididas na semana d = i − ORD_SEM − 1 já venceram: aprende qual distância rendeu mais
            d = i - ORD_SEM - 1; v = ~EK & np.isfinite(GB[0][:, d]); cx = CX[v, d]
            if v.any():
                cnt = np.bincount(cx, minlength=len(ADP_CTX))[:, None]
                for M, G in ((SB, GB), (SS, GS)):
                    M *= dko; M += np.array([np.bincount(cx, weights=np.nan_to_num(g[v, d]), minlength=len(ADP_CTX)) for g in G]).T / np.maximum(cnt, 1)
            kb, ks = np.array(ORD_KS)[SB.argmax(axis=1)][ctx], np.array(ORD_KS)[SS.argmax(axis=1)][ctx]
            ODc[:, i] = np.clip(kb * D["VW"][:, i], ORD_MIN, ORD_MAX); ODv[:, i] = np.clip(ks * D["VW"][:, i], ORD_MIN, ORD_MAX)
        if i >= 2:  # anti-emoção: oscilação rápida na semana d = i − 2; esperar 1 semana (executar em d+2 e não em d+1) rendeu?
            d = i - 2
            with np.errstate(invalid="ignore", divide="ignore"): g = np.log(C[:, i] / C[:, i - 1])
            for j, M, sg in ((0, D["CV"], 1), (1, D["CC"], -1)):
                v = M[:, d] & np.isfinite(g) & ~EK
                if v.any():
                    cnt = np.bincount(CX[v, d], minlength=len(ADP_CTX))
                    SC[:, j] = SC[:, j] * dko + np.bincount(CX[v, d], weights=sg * g[v], minlength=len(ADP_CTX)) / np.maximum(cnt, 1)
            CVa[:, i] &= SC[ctx, 0] > 0; CCa[:, i] &= SC[ctx, 1] > 0
        if Xp is not None:  # aprende com a semana que acabou: exposições da semana anterior × resultado desta
            with np.errstate(invalid="ignore", divide="ignore"): r = (Cf[:, i] + DVg[:, i]) / Cf[:, i - 1] - 1
            ok = ~np.isnan(C[:, i]) & ~np.isnan(C[:, i - 1]) & np.isfinite(r) & ~EK; c = D["cdb"][i] - 1
            if ok.any():
                rr = np.clip(r[ok], -.5, 1.0); g = np.log1p(Xp[:, ok] * rr + (1 - Xp[:, ok]) * c); cx = ctxp[ok]
                cnt = np.bincount(cx, minlength=len(ADP_CTX)); G = np.array([np.bincount(cx, weights=g[k], minlength=len(ADP_CTX)) for k in range(K)]).T
                S *= dec; S += np.where(cnt[:, None] > 0, G / np.maximum(cnt, 1)[:, None], 0)
        W = np.exp(ADP_ETA * (S - S.max(axis=1, keepdims=True)))  # pesos aprendidos até agora (por cenário)
        Wq = W[ctx]; Wq = np.where(EK[:, None], Wq * pre[None, :], Wq)  # N × K (ETF: só os de preço)
        AX[:, i] = np.round(4 * (Wq * X.T).sum(axis=1) / Wq.sum(axis=1)) / 4
        AA[:, i] = Wq.argmax(axis=1); AP[:, i] = np.round(100 * Wq.max(axis=1) / Wq.sum(axis=1))
        Xp, ctxp = X, ctx
        hn.append(X[kn])  # acerto das notícias ruins: a ação foi pior que a mediana nas 4 semanas seguintes? (só o que já aconteceu)
        if len(hn) == 5:
            with np.errstate(invalid="ignore", divide="ignore"): f = Cf[:, i] / Cf[:, i - 4] - 1
            v = np.isfinite(f) & ~EK; b = (hn[0] == 0) & v
            if b.any(): nb += int(b.sum()); nh += int((f[b] < np.median(f[v])).sum())
    W = np.exp(ADP_ETA * (S - S.max(axis=1, keepdims=True))); W /= W.sum(axis=1, keepdims=True)
    D["AX"], D["AA"], D["AP"] = AX, AA, AP; D["ODc"], D["ODv"] = ODc, ODv; D["CVa"], D["CCa"] = CVa, CCa
    del GB, GS
    D["ADPS"] = {"ctx": [{"c": ADP_CTX[c], "top": [[_adp_nome(ADP[k]), round(100 * float(W[c, k]))] for k in np.argsort(-W[c])[:3]]} for c in range(len(ADP_CTX))],
                 "news": {"n": nb, "acerto": round(100 * nh / nb, 1) if nb else None},
                 "calma": [{"c": ADP_CTX[c], "venda": bool(SC[c, 0] > 0), "compra": bool(SC[c, 1] > 0)} for c in range(len(ADP_CTX))],
                 "ordem": [{"c": ADP_CTX[c], "compra": ORD_KS[int(SB[c].argmax())], "venda": ORD_KS[int(SS[c].argmax())]} for c in range(len(ADP_CTX))] if tem_hl else []}


def _adp_nome(k): return ADP_N.get(k) or MOD[k]["n"]


def _segue(D, mid, k, i):
    """(especialista de maior peso, peso %) de um modelo de exposição (Híbrido ou Adaptativo) na ação k, semana i."""
    if mid == "adapt": return _adp_nome(ADP[int(D["AA"][k, i])]), int(D["AP"][k, i])
    return MOD[HIB[int(D["HA"][k, i])]]["n"], int(D["HP"][k, i])


_slock = threading.Lock()  # set_setores: um pedido por vez (dois juntos montavam método/Adaptativo em dobro e estouravam os 512 MB)


def set_setores(D, rows, cad=None):
    """Marca as empresas de setor perene nas matrizes (fora delas o Método Barsi fica "fora do método")."""
    with _slock: _set_setores(D, rows, cad)


def _set_setores(D, rows, cad=None):
    bs = {r["ticker"] for r in rows if perene(r, cad)}
    if D.get("_bs") != bs: D["BS"] = np.array([t in bs for t in D["tick"]]); D["_bs"] = bs; _cclear()
    sec = {r["ticker"]: r.get("subsetor") or r.get("setor") or "" for r in rows}
    if D.get("_sec") != sec and "FM" in D:  # crise do setor: ≥ VENDA['setor_crise'] das empresas do setor com prejuízo no último balanço
        FM = D["FM"]; CRI = np.zeros_like(FM["PREJ"]); key = np.array([sec.get(t, "") for t in D["tick"]])
        for g in set(key) - {""}:
            m = key == g
            if m.sum() < 3: continue
            n = FM["TEM"][m].sum(axis=0); sh = np.where(n >= 3, FM["PREJ"][m].sum(axis=0) / np.maximum(n, 1), 0)
            CRI[m] = (sh >= VENDA["setor_crise"])[None, :]
        D["CRI"] = CRI; D["_sec"] = sec; _cclear()
        D["SEC3"] = np.array([1 if str(sec.get(t, "")).startswith("Bancos") else 2 for t in D["tick"]])  # Adaptativo: banco × outros
    set_metodos(D, rows)
    ak = (D.get("_mk"), D.get("at"), len(D.get("_bs") or ()))
    if D.get("_ak") != ak: _adapt(D); D["_ak"] = ak; _cclear(); gc.collect(); _trim()  # Adaptativo: aprende de novo só quando os dados ou os sinais mudam
JCP_IR = 0.15     # IR retido na fonte sobre JCP (os proventos da B3 com tipo JCP; antes da lista da B3 o Yahoo não separa)
ENGINE = 24       # versão das contas (24: 1º dia com ordens com preço limite, sem compra na criação; 23: 1º dia a mercado; 22: aporte primeiro nas empresas da carteira, Buy and Hold com dividendos + apostas de crescimento, confiança nas notícias; 21: saldo do CDB antes de cada aplicação/resgate; 20: CDB dia a dia com IR regressivo e IOF no resgate; 19: Grupo simulação do mês atual anda até hoje; 18: ordem só executa passando 0,2% do limite, nada antes da data inicial, histórico por data; 17: alvos caros no Value e Barsi, prejuízo só com empresa ruim nos de segurar; 16: ordens ligadas na semana da decisão + anti-emoção; 15: ordens com preço limite; 14: modelo Adaptativo (aprende); 13: ETFs nos modelos de preço; 12: caixa máximo do Método Barsi; 11: valor de mercado com as ações de cada balanço; 10: modelos de método e híbrido com eles; 9: empresas que saíram da bolsa em Todas): invalida resultados guardados
# Regras de carteira do modo Grupo (Comparar → Grupo, Grupo simulação, widget) — valem para todos os modelos, mesmo rendendo menos:
# ninguém acompanha 200 empresas de verdade. max: empresas na carteira; liq: volume médio diário mínimo (R$, 60 pregões, da época) para
# comprar; conc: o aporte do mês vai para até conc empresas (as mais abaixo da meta), compra mínima min_compra; venda: venda ocasional nos
# modelos de segurar (venda_motivo). Explicação no painel ⓘ → Modelos da Previsão.
REGRAS = {"max": 30, "liq": 1e6, "conc": 3, "min_compra": 100.0, "venda": True}
# venda ocasional dos modelos de segurar: prejuízo grande (fração do patrimônio), setor em crise (fração das empresas com prejuízo),
# histórico (anos, fração com lucro), posse mínima e sem recompra (semanas), queda sobre o preço médio, limite de pontos, crise do mercado
VENDA = {"pl_prej": .15, "setor_crise": .40, "hist_anos": 10, "hist_lucro": .8, "posse": 52, "sem_recompra": 52, "queda": .30,
         "limite": 1.5, "crise_dd": .25, "crise_anos": 3, "medo_extremo": 25}
# Venda por pontos (_venda): problemas somam, margem desconta; vende quando problemas − margem ≥ VENDA['limite']
VPROB = {"prej_grande": 2.0, "prej2": 1.0, "prej": .5, "sem_prov": 1.5, "corte": 1.5, "divida": 1.0}
VMARG = {"nota": 25.0, "porte": (0, 0, .5, 1.0), "forte": 1.0, "setor": 1.0, "mercado": 1.0}  # nota: (nota − 50) ÷ 25; porte: pequena…gigante
# Nota de qualidade 0–100 (_fund_mats + proventos em build): pesos das partes, referências que valem nota cheia, faixas de porte
NOTA = {"pesos": {"porte": .20, "roe": .20, "margem": .10, "constancia": .20, "cresc": .10, "proventos": .10, "divida": .10},
        "roe": .15, "margem": .10, "cresc": .20, "div_ok": 1.0, "porte": (.4, .7, .9), "porte_min": 10, "min_qw": .5, "min_compra": 30}
PORTE_N = ("pequena", "média", "grande", "gigante")
# Notícias (_news_mats): peso do fato oficial (Fato Relevante da CVM) e de jornal; suposição/previsão só como contexto (peso e limite
# por semana); janela de semanas lida pelos modelos (só as já publicadas); nota ≤ 'ruim' bloqueia compra e vira problema na venda
NOTICIA = {"oficial": 1.0, "jornal": .5, "suposicao": .25, "sup_max": .25, "semanas": 4, "ruim": -1.0, "prob_max": 2.0, "marg_max": 1.0}
CUSTO = 0.003      # corretagem + emolumentos + diferença de preço, por operação
IR, ISENTO = 0.15, 20000.0  # IR de 15% sobre o lucro das vendas do mês; isento se o total vendido no mês for até R$ 20 mil
MEDO = 45          # abaixo disso o índice está em Medo (faixas de fg.json)
MED_SEM = 52       # chance do algoritmo "favorável" = acima da mediana das últimas 52 semanas da própria ação
TROCA_SEM = 12     # rodízio: semanas mínimas na empresa antes de trocar por outra melhor
# rodízio: grupos prontos (nome, subsetor, quantas maiores por valor de mercado) + os grupos do usuário (aba Grupos)
GRUPOS = [("5 maiores bancos", r"^Bancos", 5), ("5 maiores de energia elétrica", r"^Energia Elétrica", 5), ("10 maiores da B3", None, 10)]
# Híbrido: especialistas (exposição de cada um) e peso pelo acerto recente na própria ação (painel ⓘ → Modelos da Previsão)
HIB = ("hold", "alg1", "alg3", "media200", "value", "growth", "garp", "fatores")  # os 4 últimos entram com set_metodos
# Modelos de método (matérias do ⓘ → Métodos de investimento → Para ler), com o valor de mercado da época = preço da época × ações em
# circulação do último balanço publicado (CVM, composição do capital) — inclusive das empresas que saíram da bolsa (set_metodos):
# value: compra com margem ≥ 'v_entra' sobre o valor justo de Graham √(22,5 × lucro × patrimônio) e nota ≥ 'v_nota'; vende acima do justo
# growth (CAN SLIM simplificado): lucro do ano ≥ +'g_ano' e média de 3 anos ≥ +'g_3a', preço até 'g_max' abaixo da máxima de 52 semanas
#   e Ibovespa acima da média de 40 semanas; vende com perda de 'g_stop' sobre o preço de entrada, lucro caindo ou mercado em baixa
# garp: PEG = P/L ÷ crescimento médio do lucro em 3 anos (%) abaixo de 'p_entra' (crescimento ≥ 'p_cres'); vende com PEG acima de 'p_sai'
# fatores: média das posições (0–1) em valor (lucro ÷ valor de mercado), qualidade (nota), momentum (alta em 12 meses) e baixa
#   volatilidade (52 semanas); compra a partir de 'f_entra', vende abaixo de 'f_sai'
METODO = {"v_entra": .25, "v_nota": 50, "g_ano": .20, "g_3a": .15, "g_max": .15, "g_stop": .08, "p_entra": 1.0, "p_cres": .10, "p_sai": 1.5,
          "f_entra": .70, "f_sai": .50, "f_min": 3, "classe": (.2, 2.0)}  # classe: faixa aceita do fator UNIT/ON/PN (set_metodos)
# Ajusta a parte na ação com aportes e proventos (compra só até a exposição alvo; o resto espera no CDB) e não vende:
# no teste com IR e custos, vender (mesmo em parte ou dentro da isenção) sempre rendeu menos que manter.
HIB_SEM, HIB_ETA = 52, 5  # janela do acerto recente (semanas) e o quanto o melhor recebe mais peso
# Adaptativo (aprende): especialistas = os modelos + notícias + qualidade; peso de cada um aprendido semana a semana desde a 1ª semana
# dos dados (antes da data inicial da simulação também), separado por cenário (mercado × tendência × tipo de setor); nunca usa o futuro
ADP = ("hold", "medo_mercado", "medo_acao", "media200", "alg1", "alg3", "tendencia", "value", "growth", "garp", "fatores", "hibrido", "barsi", "noticias", "qualidade")
ADP_N = {"noticias": "Notícias (sem fato ruim recente)", "qualidade": "Nota de qualidade alta"}  # especialistas que não são modelos
ADP_PRECO = 7     # os 7 primeiros especialistas só usam preço (os únicos para ETF)
ADP_MEIA = 104    # meia-vida da memória do aprendizado (semanas): acertos antigos pesam menos, mas nunca somem
ADP_ETA = 200.0   # o quanto o especialista que mais acertou no cenário ganha peso sobre os outros (testado: 8, 30, 80, 200; 200 rendeu mais)
ADP_NOTA = 60     # especialista Qualidade: fica na ação com nota de qualidade a partir disto
ADP_CTX = [f"{m} · {t} · {s}" for m in ("medo", "neutro", "ganância") for t in ("Ibovespa em alta", "Ibovespa em queda") for s in ("setor perene", "banco", "outros setores")]
# Ordens com preço limite (como um investidor): a compra fica um pouco abaixo e a venda um pouco acima do preço do dia da decisão, a
# distância = ORD_K × volatilidade semanal da ação (26 semanas, só dados até a decisão), entre ORD_MIN e ORD_MAX; executa no dia em que a
# mínima (compra) ou a máxima (venda) do dia toca o limite; sem tocar em ORD_SEM semanas, executa no fechamento; o modelo mudou de
# ideia: cancela. Não aumenta o número de compras e vendas (são as mesmas decisões, só o dia e o preço mudam)
ORD_ON = True     # ordens com preço limite ligadas (desligadas: tudo no fechamento da semana)
ORD_SEM = 1       # prazo da ordem (semanas): vale só na semana da decisão; sem tocar o limite, executa no fechamento dela
ORD_K = 0.5       # distância do limite em volatilidades semanais da ação
ORD_MIN = .01     # distância mínima do limite (1%)
ORD_MAX = .08     # distância máxima do limite (8%)
ORD_FILA = .002   # a mínima (compra) ou a máxima (venda) precisa passar 0,2% do limite para contar como executada (só encostar: a fila pode não andar)
# Anti-emoção (Ordens com calma): sinal que nasce de uma oscilação rápida (variação da semana maior que 'vol' volatilidades semanais da
# ação) espera 1 semana para confirmar; queda rápida não vende se a empresa está bem (lucro no último balanço, nota ≥ 'nota', sem notícia
# ruim) ou se o mercado (mediana das ações) caiu junto (≥ 'mercado' da queda dela); alta rápida não compra no topo. Fora: modelos que
# reagem rápido por estratégia (CALMA_FORA); vendas por problema (_venda) e saída da bolsa não esperam
CALMA = {"vol": 2.0, "nota": 50, "mercado": .5}
# Alvos baratos × caros (modo Grupo): empresa do alvo está "cara agora" com P/L acima de 'pl' × a mediana do próprio P/L nas últimas
# 'anos' (mínimo 'min_anos' de histórico; sem lucro = não dá para dizer); o aporte vai só para as baratas; se todas as alvo estiverem
# caras, o dinheiro espera no CDB até 'espera' semanas e então compra a menos cara. Só nos modelos de 'modelos' (Value e Barsi): nos
# testes de 2011, 2016 e 2021 piorou os de tendência (compram o que sobe, de P/L alto) e não melhorou os outros de forma consistente
CARO = {"pl": 1.3, "anos": 5, "min_anos": 2, "espera": 13, "modelos": ("value", "barsi")}
# Prejuízo (_perda): os modelos em 'modelos' seguram a ação abaixo do preço médio (sem aporte) até 'espera' semanas esperando voltar,
# e só realizam o prejuízo antes disso com empresa ruim (_venda; no prejuízo, um balanço ruim isolado não conta). Só os modelos de
# segurar: nos testes de 2011, 2016 e 2021 segurar no prejuízo piorou muito os que vendem pelo sinal (cortam perdas por estratégia)
PERDA = {"espera": 26, "modelos": ("hold", "medo_mercado", "medo_acao", "media200", "hibrido", "adapt", "barsi")}
CALMA_FORA = ("tendencia", "alg1", "medo_mercado", "medo_acao")  # modelos que não esperam: reagir rápido é a estratégia deles
ORD_KS = (0.0, 0.25, 0.5, 1.0)  # Adaptativo: distâncias (em volatilidades) que ele testa no histórico e escolhe por cenário
HIB_COMPRA = .125  # compra quando a parte na ação está pelo menos 12,5 pontos abaixo do alvo (no teste rendeu mais que comprar aos poucos)
FORTE_R12 = 100   # Análise técnica: entrada no rodízio só com alta de pelo menos 10% em 12 meses (×1000)
# "lucro": só compra se o último balanço anual publicado teve lucro (fund.json); no teste 2006–2026 ajudou só estes dois modelos
MARGEM = {"alg1": 20, "alg3": 20, "tendencia": 100}  # rodízio: vantagem mínima para trocar (chance ×1000; alta 12 m ×1000)

_D = {"at": 0, "key": None, "d": None, "tag": None}  # tag: versão do snapshot `modelos` (snapshots.version)
_lock = threading.Lock()
_C = OrderedDict()  # respostas prontas (run, compare, simgrupo): LRU de C_MAX; chave com _CG (geração das tabelas)
C_MAX = 20          # ~2,5 MB cada no pior caso (Comparar com todas as empresas)
_clock = threading.Lock()
_CG = [0]           # geração: sobe a cada _cclear (tabelas novas ou set_setores/set_metodos mudou algo); conta que começou antes não grava por cima


def _cclear():
    """Esquece as respostas prontas: as tabelas mudaram (a conta em andamento grava com a geração antiga e nunca é lida)."""
    with _clock: _CG[0] += 1; _C.clear()


def _ckey(*k):
    """Chave do cache _C com a geração atual das tabelas (pegue ANTES de calcular)."""
    return repr((_CG[0],) + k)


def _cget(key):
    with _clock:
        x = _C.get(key)
        if x is not None: _C.move_to_end(key)
        return x


def _cput(key, out):
    """Guarda uma resposta pronta (LRU de C_MAX) e a devolve."""
    with _clock:
        _C[key] = out; _C.move_to_end(key)
        while len(_C) > C_MAX: _C.popitem(last=False)
    return out


def _fund_mats(tick, wk, fund, spl=None):
    """Balanços anuais (fund.json, DFP da CVM) em cada semana, só os já publicados (ano Y vale a partir de 1º/maio de Y+1):
    PREJ2 = prejuízo nos 2 últimos balanços; GRANDE = os 2 prejuízos somam mais de VENDA['pl_prej'] do patrimônio de antes deles
    (ou patrimônio negativo); FORTE = lucro em ≥ VENDA['hist_lucro'] dos VENDA['hist_anos'] anos antes do último balanço
    (ou antes da sequência atual de prejuízos; mínimo 4 anos com balanço);
    PREJ = prejuízo no último balanço (base da crise do setor, em set_setores);
    QY = parte da nota de qualidade que vem dos balanços (NOTA; 0–1, soma ponderada) e QW = soma dos pesos usados — medida até antes
    da sequência atual de prejuízos (a empresa é julgada pelo que era antes da crise; os prejuízos entram como problema em _venda);
    PORTE = 0 pequena, 1 média, 2 grande, 3 gigante (receita entre as empresas do mesmo ano; -1 sem dado);
    DIV = dívida líquida ÷ EBITDA acima do alerta do card (valor_justo.FAIR['al_dlebitda']) e maior que no balanço anterior;
    DLX = essa razão no último balanço (texto do motivo; inf = EBITDA negativo com dívida). Bancos e seguradoras: sem dívida (fund sem dl).
    SHW = ações em circulação do último balanço publicado (fund → sh, composição do capital da CVM) na base dos preços de hoje
    (× fatores de desdobramento/grupamento posteriores ao balanço, spl = snapshot modelos → sp); sem o dado: NaN (sem valor de mercado)."""
    N, T = len(tick), len(wk); z = lambda: np.zeros((N, T), bool)
    PREJ2, GRANDE, FORTE, PREJ, TEM = z(), z(), z(), z(), z()
    QY = np.full((N, T), np.nan, np.float32); QW = np.zeros((N, T), np.float32); PORTE = np.full((N, T), -1, np.int8)
    DIV = z(); DLX = np.full((N, T), np.nan, np.float32); lim = valor_justo.FAIR["al_dlebitda"]  # limite do alerta ⚠️ do card
    fa = lambda v: np.array([np.nan if x is None else x for x in v or []], float)
    NIW, EQW, G1, G3, SHW = (np.full((N, T), np.nan, np.float32) for _ in range(5))  # lucro, patrimônio, crescimento do lucro, ações
    F, byy = {}, {}
    for k, t in enumerate(tick):
        f = (fund or {}).get(t)
        if not f or not f.get("y") or len(f.get("ni") or []) != len(f["y"]): continue
        F[k] = f
        for y, r in zip(f["y"], f.get("rev") or []):
            if r and r > 0: byy.setdefault(y, []).append(r)
    byy = {y: np.sort(v) for y, v in byy.items() if len(v) >= NOTA["porte_min"]}
    P_ = NOTA["pesos"]
    for k, f in F.items():
        av = np.array([np.datetime64(f"{y + 1}-05-01") for y in f["y"]]); jl = np.searchsorted(av, wk.values.astype("datetime64[D]"), side="right") - 1
        ni = np.array([np.nan if x in (None, 0) else x for x in f["ni"]], float); eq = fa(f.get("eq")); rev = fa(f.get("rev"))
        if len(eq) != len(ni): eq = np.full(len(ni), np.nan)
        if len(rev) != len(ni): rev = np.full(len(ni), np.nan)
        dl, eb = fa(f.get("dl")), fa(f.get("eb"))
        if len(dl) != len(ni): dl = np.full(len(ni), np.nan)
        if len(eb) != len(ni): eb = np.full(len(ni), np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):  # dívida líquida ÷ EBITDA (caixa líquido: ≤ 0; EBITDA ≤ 0 com dívida: inf)
            dx = np.where(dl <= 0, np.minimum(dl / np.where(eb > 0, eb, 1), 0), np.where(eb > 0, dl / eb, np.inf))
        dx[np.isnan(dl)] = np.nan
        per = {}  # por balanço j: (QY, QW, PORTE, FORTE, PREJ2, GRANDE, DIV, DLX)
        for j in range(len(ni)):
            e = j  # histórico antes da sequência atual de prejuízos (Petrobras 2014–15 é julgada pelos anos bons de antes)
            while e >= 0 and ni[e] < 0: e -= 1
            h = ni[max(0, e + 1 - VENDA["hist_anos"]):e + 1] if e < j else ni[max(0, j - VENDA["hist_anos"]):j]; h = h[~np.isnan(h)]
            fo = len(h) >= 4 and (h > 0).mean() >= VENDA["hist_lucro"]
            p2 = gr = False
            if j >= 1 and ni[j] < 0 and ni[j - 1] < 0:
                p2 = True; e0 = eq[j - 2] if j >= 2 else np.nan
                gr = bool((eq[j] <= 0) or (e0 > 0 and -(ni[j] + ni[j - 1]) > VENDA["pl_prej"] * e0))
            q, qw, po = 0.0, 0.0, -1
            if e < 0: q, qw = 0.0, 1.0  # só prejuízos: nota 0
            else:
                a = max(0, e + 1 - 5); n5, e5, r5 = ni[a:e + 1], eq[a:e + 1], rev[a:e + 1]
                def add(peso, v):
                    nonlocal q, qw
                    if v is not None and not np.isnan(v): q += peso * float(np.clip(v, 0, 1)); qw += peso
                y = f["y"][e]; r = rev[e]
                if y in byy and r > 0:
                    pc = np.searchsorted(byy[y], r, side="right") / len(byy[y]); add(P_["porte"], pc)
                    po = int(np.searchsorted(NOTA["porte"], pc, side="right"))
                m = (e5 > 0) & ~np.isnan(n5)
                if m.sum() >= 3: add(P_["roe"], np.mean(n5[m] / e5[m]) / NOTA["roe"])
                m = (r5 > 0) & ~np.isnan(n5)
                if m.sum() >= 3: add(P_["margem"], np.mean(n5[m] / r5[m]) / NOTA["margem"])
                h10 = ni[max(0, e + 1 - VENDA["hist_anos"]):e + 1]; h10 = h10[~np.isnan(h10)]
                if len(h10) >= 4: add(P_["constancia"], (h10 > 0).mean())
                ok = np.flatnonzero(r5 > 0)
                if len(ok) >= 3 and ok[-1] > ok[0]: add(P_["cresc"], .5 + ((r5[ok[-1]] / r5[ok[0]]) ** (1 / (ok[-1] - ok[0])) - 1) / NOTA["cresc"])
                if not np.isnan(dx[e]): add(P_["divida"], (lim - dx[e]) / (lim - NOTA["div_ok"]))  # até 1× nota cheia; no limite do alerta, zero
            dv = bool(dx[j] > lim and j >= 1 and (np.isnan(dx[j - 1]) or dx[j] > dx[j - 1]))  # dívida acima do alerta e subindo
            per[j] = (q, qw, po, fo, p2, gr, dv, dx[j])
        with np.errstate(invalid="ignore", divide="ignore"):  # crescimento do lucro: 1 ano e média de 3 anos (só com lucro nas duas pontas)
            g1 = np.full(len(ni), np.nan); g3 = np.full(len(ni), np.nan)
            g1[1:] = np.where((ni[1:] > 0) & (ni[:-1] > 0), ni[1:] / ni[:-1] - 1, np.nan)
            g3[3:] = np.where((ni[3:] > 0) & (ni[:-3] > 0), (ni[3:] / ni[:-3]) ** (1 / 3) - 1, np.nan)
        sh = fa(f.get("sh"))
        if len(sh) != len(ni): sh = np.full(len(ni), np.nan)
        sp = (spl or {}).get(tick[k]) or []
        sh = sh * np.array([np.prod([m for d, m in sp if d >= f"{y}-12-31"] or [1.0]) for y in f["y"]])  # base dos preços (ajustados até hoje)
        for j in range(len(sh) - 2, -1, -1):  # entrega antiga em milhares de ações: salto de ~1000× sem evento de desdobramento
            r = sh[j + 1] / sh[j] if sh[j] > 0 and sh[j + 1] > 0 else 1
            if 500 < r < 2000: sh[j] *= 1000
            elif 1 / 2000 < r < 1 / 500: sh[j] /= 1000
        for i in np.flatnonzero(jl >= 0):
            j = jl[i]; TEM[k, i] = not np.isnan(ni[j]); PREJ[k, i] = ni[j] < 0
            NIW[k, i], EQW[k, i], G1[k, i], G3[k, i], SHW[k, i] = ni[j], eq[j], g1[j], g3[j], sh[j]
            QY[k, i], QW[k, i], PORTE[k, i], FORTE[k, i], PREJ2[k, i], GRANDE[k, i], DIV[k, i], DLX[k, i] = per[j]
    return {"PREJ2": PREJ2, "GRANDE": GRANDE, "FORTE": FORTE, "PREJ": PREJ, "TEM": TEM, "QY": QY, "QW": QW, "PORTE": PORTE, "DIV": DIV, "DLX": DLX,
            "NIW": NIW, "EQW": EQW, "G1": G1, "G3": G3, "SHW": SHW}


_VOCN = None
def tom_noticia(texto, frase=False):
    """Tom de uma notícia pelo vocabulário (vocabulario.json → noticias) -> (tom de -2 a +2, suposição?[, assunto: frase de maior peso]).
    Frases mais longas primeiro (uma frase usada não conta de novo nas mais curtas: "saída da recuperação judicial" não vira negativo)."""
    global _VOCN
    if _VOCN is None:
        v = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocabulario.json"), encoding="utf-8"))["noticias"]
        _VOCN = (sorted({**v["negativo"], **v["positivo"]}.items(), key=lambda x: -len(x[0])), v["suposicao"])
    t = " " + unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower() + " "
    tom = 0.0; fr = ("", 0)
    for w, p in _VOCN[0]:
        if w in t:
            tom += p; t = t.replace(w, " ")
            if abs(p) > abs(fr[1]): fr = (w, p)
    r = (float(np.clip(tom, -2, 2)), any(w in t for w in _VOCN[1]))
    return r + (fr[0],) if frase else r


# Confiança nas notícias (todos os modelos): o que a ação fez (contra a mediana das outras) nas NCONF['h'] semanas depois de cada notícia;
# acertou = notícia ruim antes de queda / boa antes de alta (média das janelas). Por tipo (CVM × jornal, fato × suposição, boa × ruim) e
# por assunto (frase do vocabulário); só casos já conhecidos na semana (sem olhar o futuro); casos antigos pesam metade a cada 'meia'
# semanas; com pelo menos 'min' casos o peso da notícia = acerto de 'lo' (ou menos) → 0 até 'hi' (ou mais) → 1 (só perde peso o tipo que
# erra mais do que acerta); antes disso, 1
NCONF = {"on": True, "h": (4, 12), "meia": 104, "min": 30, "lo": .30, "hi": .50}  # testado: .40–.60 e .45–.55 tiravam peso de tipos que só empatavam e rendiam menos


def _ncat(o, sup, tom, fr=None):
    """Tipo da notícia (rótulo de 'Ver o que ele aprendeu')."""
    t = f"{'CVM' if o else 'jornal'} · {'suposição' if sup else 'fato'} · {'boa' if tom > 0 else 'ruim'}"
    return t + f" · {fr}" if fr else t


def _news_mats(tick, wk, news, Cf=None):
    """Notícias por empresa e semana: NT = soma do tom (fato oficial NOTICIA['oficial'], de jornal NOTICIA['jornal']; suposição ou
    previsão só como contexto: NOTICIA['suposicao'] no total, limitado a ±NOTICIA['sup_max'] na semana) × confiança do tipo (NCONF,
    com os preços Cf); NX = texto da mais forte; NCF = o que aprendeu na última semana (tipo, casos, acerto, peso)."""
    ix = {t: k for k, t in enumerate(tick)}; N, T = len(tick), len(wk)
    NT = np.zeros((N, T), np.float32); SP = np.zeros((N, T), np.float32); NX = {}
    wd = wk.values.astype("datetime64[D]"); E = []
    for it in news or []:
        ks = [ix[t] for t in it.get("t") or () if t in ix]
        if not ks or not it.get("d"): continue
        i = int(np.searchsorted(wd, np.datetime64(it["d"][:10]), side="left"))
        if i >= T: continue
        tom, sup, fr = tom_noticia(it.get("x"), True)
        if tom: E.append((ks, i, tom, sup, bool(it.get("o")), fr, it.get("x")))
    conf, NCF = _nconf(E, Cf, T)
    for ks, i, tom, sup, o, fr, x in E:
        for k in ks:
            c = conf(k, i, o, sup, tom, fr)
            if sup: SP[k, i] += tom * NOTICIA["suposicao"] * c
            else:
                v = tom * NOTICIA["oficial" if o else "jornal"] * c; NT[k, i] += v
                if abs(v) >= abs(NX.get((k, i), ("", 0))[1]) and v: NX[(k, i)] = ((x or "")[:120], v)
    return NT + np.clip(SP, -NOTICIA["sup_max"], NOTICIA["sup_max"]), {k: v[0] for k, v in NX.items()}, NCF


def _nconf(E, Cf, T):
    """Confiança aprendida (NCONF) -> (função peso(k, i, oficial, suposição, tom, assunto), resumo da última semana)."""
    if Cf is None or not E or not NCONF["on"]: return (lambda *a: 1.0), []
    import pandas as pd
    with np.errstate(invalid="ignore", divide="ignore"):
        L = np.log(Cf.astype(np.float32)); r = np.diff(L, axis=1); r[~np.isfinite(r)] = np.nan
        mk = np.concatenate([[0.0], np.nancumsum(np.nan_to_num(np.nanmedian(r, axis=0)))]); del r  # mediana das ações (float32: memória)
    H = NCONF["h"]; hm = max(H); acc = {}  # tipo -> [semana resolvida, acertou (0–1), peso pela data]
    for ks, i, tom, sup, o, fr, _ in E:
        if i + hm >= T: continue
        for k in ks:
            a = [L[k, i + h] - L[k, i] - (mk[i + h] - mk[i]) for h in H]
            if not all(np.isfinite(a)): continue
            hit = float(np.mean([np.sign(tom) * x > 0 for x in a]))
            for c in (_ncat(o, sup, tom), _ncat(o, sup, tom, fr)): acc.setdefault(c, []).append((i + hm, hit, i))
    S = {}  # tipo -> (acerto ponderado até cada semana, casos até cada semana)
    for c, v in acc.items():
        a = np.array(v); hs = np.zeros(T); ws = np.zeros(T); ns = np.zeros(T); pw = 2.0 ** (a[:, 2] / NCONF["meia"])
        np.add.at(hs, a[:, 0].astype(int), a[:, 1] * pw); np.add.at(ws, a[:, 0].astype(int), pw); np.add.at(ns, a[:, 0].astype(int), 1)
        hs, ws, ns = np.cumsum(hs), np.cumsum(ws), np.cumsum(ns)
        S[c] = (np.where(ws > 0, hs / np.where(ws > 0, ws, 1), np.nan), ns)
    pk = lambda x: float(np.clip((x - NCONF["lo"]) / (NCONF["hi"] - NCONF["lo"]), 0, 1))
    def conf(k, i, o, sup, tom, fr):
        for c in (_ncat(o, sup, tom, fr), _ncat(o, sup, tom)):
            if c in S and S[c][1][i] >= NCONF["min"]: return pk(S[c][0][i])
        return 1.0
    res = [{"t": c, "n": int(S[c][1][-1]), "a": round(float(S[c][0][-1]) * 100, 1), "p": round(pk(S[c][0][-1]) * 100), "ok": bool(S[c][1][-1] >= NCONF["min"])}
           for c in S if S[c][1][-1] >= (1 if c.count(" · ") == 2 else NCONF["min"])]
    res.sort(key=lambda x: (x["t"].count(" · "), -x["n"]))
    return conf, res


def noticias_itens(fatos=None, noticias=None, arquivo=None):
    """Itens dos snapshots no formato dos modelos {d, t, x, o}: Fatos Relevantes da CVM (snapshot `fatos`, oficiais) e notícias
    da coleta diária (snapshot `noticias`, itens com a lista de tickers da B3 `t` e do mercado "br" em `m`; os outros ficam de fora)."""
    out = []
    f = fatos or {}; tc = {}
    for t, c in (f.get("t") or {}).items(): tc.setdefault(c, []).append(t)  # todas as classes da mesma companhia
    for c, L in (f.get("c") or {}).items():
        for d, x in L: out.append({"d": d, "t": tc.get(c, []), "x": x, "o": True})
    vistas = set()
    for it in (noticias or {}).get("itens") or []:  # só as do mercado brasileiro (B3); as de fora ("m" sem "br") ficam para modelos de lá
        if it.get("t") and "br" in (it.get("m") or ["br"]): out.append({"d": it.get("data"), "t": it["t"], "x": f"{it.get('titulo') or ''}. {it.get('resumo') or ''}", "o": bool(it.get("oficial"))}); vistas.add(it.get("url"))
    for it in (arquivo or {}).get("itens") or []:  # arquivo que só cresce (scripts/fetch_noticias.py → noticias_arq): as antigas também
        if it.get("t") and "br" in (it.get("m") or ["br"]) and it.get("u") not in vistas: out.append({"d": it["d"], "t": it["t"], "x": it["x"], "o": False})
    return out


def build(snap, cdi, gold=None, ibov=None, fund=None, news=None, saida=None, idiv=None, consome=False):
    """snapshot `modelos` + CDI diário {d, v (% ao dia)} + ouro em reais {d, v} (history.gold) -> matrizes ações × semanas (numpy)."""
    W = snap["w"]; T = len(W); tick = sorted(snap["a"]); N = len(tick)
    arr = lambda dt=np.float64: np.full((N, T), np.nan, dtype=dt)
    # preço e proventos em float64 (dinheiro); sinais em float32 (só comparações): metade da memória
    C, DV = arr(), arr()
    SI, M2, R12, P1, P3, VL = (arr(np.float32) for _ in range(6))  # VL: volume médio diário de 60 pregões (R$ mil; build_modelos → vl)
    LO, HI = arr(np.float32), arr(np.float32); OL, OH = np.full((N, T), 255, np.uint8), np.full((N, T), 255, np.uint8)  # mín./máx. da semana
    LP = np.ones((N, T), bool); JC = np.zeros((N, T)); DT = {}  # JC: JCP por ação na semana; DT: tipos (J, D, R, K) dos proventos da B3
    DD = list(snap.get("dd") or []); DC = np.full((N, len(DD)), np.nan, np.float32)  # fechamento de cada dia dos últimos pregões (1º dia: _dia0)
    SPL = {}  # desdobramentos/grupamentos de cada ação (snapshot modelos → sp): número de ações dos balanços na base dos preços
    for k, t in enumerate(tick):
        a = snap["a"].pop(t) if consome else snap["a"][t]; i0 = a["i0"]
        if a.get("dc") and DD: v = a["dc"][-len(DD):]; DC[k, -len(v):] = [np.nan if x is None else x for x in v]
        if a.get("sp"): SPL[t] = a["sp"]  # consome: solta as listas do JSON enquanto monta (data())
        for M, key in ((C, "c"), (SI, "si"), (M2, "m2"), (R12, "r12"), (P1, "p1"), (P3, "p3"), (VL, "vl")):
            v = a.get(key) or []
            M[k, i0:i0 + len(v)] = [np.nan if x is None else x for x in v]
        for M, key, dt in ((LO, "lo", 0), (HI, "hi", 0), (OL, "ol", 1), (OH, "oh", 1)):
            v = a.get(key) or []
            M[k, i0:i0 + len(v)] = [(255 if x is None else min(254, x)) if dt else (np.nan if x is None else x) for x in v]
        DV[k, i0:] = 0
        lp = a.get("lp")
        if lp: LP[k, i0:i0 + len(lp)] = [x != 0 for x in lp]  # 0 = prejuízo no último balanço; sem balanço = liberado
        for j, v in (a.get("dv") or {}).items(): DV[k, i0 + int(j)] = v
        for j, v in (a.get("jc") or {}).items(): JC[k, i0 + int(j)] = v
        for j, v in (a.get("tp") or {}).items(): DT[(k, i0 + int(j))] = v
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
    CID, CIC = cs.index.values.astype("datetime64[D]"), cs.to_numpy()  # CDB dia a dia (Caixa): índice acumulado do CDI por dia útil
    # híbrido: exposição (0, 25, 50, 75 ou 100%) = média das exposições dos especialistas, pesadas pelo retorno de cada um nas últimas
    # HIB_SEM semanas (ação + proventos quando dentro, CDB quando fora); decide com dados até a semana (opera na seguinte)
    Cf = pd.DataFrame(C.T).ffill().to_numpy().T
    with np.errstate(invalid="ignore", divide="ignore"):  # mín./máx. da semana em R$ (vinham em ‰ do fechamento); distância das ordens com preço limite
        LO = (C * (1 + LO / 1000)).astype(np.float32); HI = (C * (1 + HI / 1000)).astype(np.float32)
        lr = np.log(pd.DataFrame(Cf.T)).diff()
        VW = lr.rolling(26, min_periods=8).std().to_numpy(np.float32).T; del lr
        ODI = np.clip(ORD_K * VW, ORD_MIN, ORD_MAX).astype(np.float32)
    HX, HA, HP = _hib(Cf, DV, cdb, [np.ones((N, T), bool), fav["p1"], fav["p3"], np.nan_to_num(M2) > 0])
    G = np.full(T, np.nan)  # ouro (R$) no último dia com preço de cada semana
    if gold and gold.get("d"):
        gs = pd.Series(gold["v"], index=pd.to_datetime(gold["d"]), dtype="float64")
        G = gs.reindex(gs.index.union(wk)).ffill(limit=10).reindex(wk).to_numpy()
    IB = np.full(T, np.nan)  # Ibovespa (pontos, fechamento mensal) em cada semana: referência com os mesmos aportes
    if ibov and ibov.get("t"):
        bs = pd.Series(ibov["c"], index=pd.to_datetime(ibov["t"], unit="s").normalize(), dtype="float64"); bs = bs[~bs.index.duplicated(keep="last")]
        IB = bs.reindex(bs.index.union(wk)).ffill(limit=6).reindex(wk).to_numpy()
    IV = np.full(T, np.nan)  # IDIV (pontos, fechamento diário da B3) no último pregão de cada semana
    if idiv and idiv.get("d"):
        vs = pd.Series(idiv["v"], index=pd.to_datetime(idiv["d"]), dtype="float64"); vs = vs[~vs.index.duplicated(keep="last")].sort_index()
        IV = vs.reindex(vs.index.union(wk)).ffill(limit=10).reindex(wk).to_numpy()
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
    # nota de qualidade 0–100: partes dos balanços (_fund_mats) + proventos pagos nos últimos 5 anos completos; sem dados suficientes = NaN
    FM = _fund_mats(tick, wk, fund, SPL); wp = NOTA["pesos"]["proventos"]; PAG = np.full((N, T), np.nan)
    for y in yrs:
        a = DPA[:, max(0, yi[y] - BARSI_ANOS):yi[y]]; nn = (~np.isnan(a)).sum(axis=1)
        PAG[:, Y == y] = np.where(nn >= 3, (np.nan_to_num(a) > 0).sum(axis=1) / np.maximum(nn, 1), np.nan)[:, None]
    qw = FM["QW"] + np.where(np.isnan(PAG), 0, wp)
    with np.errstate(invalid="ignore", divide="ignore"):
        FM["Q"] = np.where(FM["QW"] >= NOTA["min_qw"], 100 * (FM["QY"] + np.nan_to_num(PAG) * wp) / qw, np.nan).astype(np.float32)
    del FM["QY"], FM["QW"]
    NT, NX, NCF = _news_mats(tick, wk, news, Cf)
    CV, CC = _calma_mats(Cf, VW, LP, FM.get("Q"), NT)
    PLR = _pl_rel(Cf, FM)
    ET = snap.get("etf") or {}; EK = np.array([ET.get(t, "") for t in tick])  # tipo do ETF ("" = ação)
    # empresas que saíram da bolsa (snapshot modelos → saiu: último pregão): SAI = semana do último preço (-1 = negociada hoje)
    sa = {t: d for t, d in (snap.get("saiu") or {}).items() if t in tick}; SAI = np.full(N, -1)
    for t, d in sa.items():
        k = tick.index(t); SAI[k] = min(T - 1, int(np.searchsorted(wk.values.astype("datetime64[D]"), np.datetime64(d), side="left")))
        C[k, SAI[k] + 1:] = np.nan
    # crise no mercado: Ibovespa ≥ VENDA['crise_dd'] abaixo do maior valor dos últimos VENDA['crise_anos'] anos, ou Medo extremo na média de 8 semanas
    MI = np.array([np.nan if x is None else x for x in snap["mi"]], dtype=float)
    ibm = pd.Series(IB).rolling(52 * VENDA["crise_anos"], min_periods=1).max().to_numpy()
    with np.errstate(invalid="ignore"):
        CG = (IB <= (1 - VENDA["crise_dd"]) * ibm) | (pd.Series(MI).rolling(8, min_periods=4).mean().to_numpy() < VENDA["medo_extremo"])
    ym = [w[:7] for w in W]
    first = next((i for i in range(T) if ok[i]), 0)  # modelos começam no 1º mês com CDB
    JT = np.minimum(JC * JCP_IR, np.nan_to_num(DV)); del JC  # IR retido na fonte do JCP (por ação)
    # DV = provento líquido por ação (o que cai no caixa); sinais e preço teto acima usam o bruto
    return {"w": W, "ym": ym, "tick": tick, "ix": {t: k for k, t in enumerate(tick)}, "C": C, "DV": DV - JT, "JT": JT, "DT": DT, "SI": SI, "M2": M2, "R12": R12,
            "P": {"p1": P1, "p3": P3}, "FAV": fav, "MED": MED, "HX": HX, "LP": LP, "HA": HA, "HP": HP, "LO": LO, "HI": HI, "OL": OL, "OH": OH, "ODI": ODI, "VW": VW, "ODc": ODI, "ODv": ODI, "AX": HX, "AA": np.zeros((N, T), np.uint8), "AP": np.full((N, T), 100, np.uint8), "MI": MI, "CG": CG, "cdb": cdb, "CID": CID, "CIC": CIC, "CDI1": float(cdi["v"][-1]) if cdi.get("v") else None, "G": G, "IB": IB, "IV": IV, "TETO": TETO, "Cf": Cf, "DD": DD, "DC": DC, "BS": np.zeros(N, bool), "VL": VL * 1000.0, "FM": FM, "NT": NT, "NX": NX, "NCF": NCF, "CV": CV, "CC": CC, "CVa": CV, "CCa": CC, "PLR": PLR, "CRI": np.zeros((N, T), bool),
            "EK": EK, "SAI": SAI, "SAIX": {k: (saida or {}).get(t) or "" for t, k in ((t, tick.index(t)) for t in sa)}, "saiu": sorted(sa),
            "me": np.array([i == T - 1 or ym[i + 1] != ym[i] for i in range(T)]), "ini": ym[first], "fim": ym[-1],
            "acerto": snap.get("acerto") or {}, "at": snap.get("fetched_at"),
            "fp": hashlib.sha1(repr((snap.get("fetched_at"), len(fund or {}), len(news or []), sorted(saida or {}))).encode() + cdb.tobytes()
                               + np.nan_to_num(G, nan=-1.0).tobytes() + np.nan_to_num(IB, nan=-1.0).tobytes() + np.nan_to_num(IV, nan=-1.0).tobytes()).hexdigest()[:16]}


def entradas():
    """Tudo o que build usa além do snapshot `modelos` e do CDI (servidor e pré-cálculo do Comparar montam igual)."""
    import snapshots, history
    try: gold = history.gold()
    except Exception: gold = None  # sem ouro: a referência Ouro mostra "—"
    try: ibov = history.get("IBOV", "m")
    except Exception: ibov = None  # sem Ibovespa: a referência mostra "—"
    fj = (snapshots.load("fund")[0]) or {}  # balanços anuais: venda ocasional (REGRAS); saida: motivo da saída da bolsa
    idiv = (((snapshots.load("b3_idx_hist")[0]) or {}).get("s") or {}).get("IDIV")  # referência IDIV (série da B3)
    news = noticias_itens(snapshots.load("fatos")[0], snapshots.load("noticias")[0], snapshots.load("noticias_arq")[0])  # Fatos Relevantes da CVM + notícias com tickers (+ arquivo)
    return {"gold": gold, "ibov": ibov, "fund": fj.get("a") or {}, "news": news, "saida": fj.get("saida"), "idiv": idiv}


def _trim():
    """Devolve ao sistema a memória já solta pelo Python (glibc malloc_trim): sem isso o pico de montar as matrizes (snapshot JSON,
    temporários) fica preso no processo e o plano gratuito (512 MB) estoura na próxima conta pesada."""
    try:
        import ctypes; ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception: pass


DATA_TTL, DATA_RETRY = 6 * 3600, 600  # confere a versão do snapshot `modelos` a cada 6 h; GitHub fora: segue com as tabelas e tenta em 10 min


def data():
    """Matrizes prontas. A cada DATA_TTL confere só a versão do snapshot `modelos` (snapshots.version, sem baixar os ~27 MB); baixa e
    monta de novo só quando ela muda, soltando as tabelas antigas ANTES (pico menor no plano gratuito). GitHub fora: segue com as atuais."""
    import snapshots, history
    with _lock:
        if _D["d"] is not None and time.time() - _D["at"] < DATA_TTL: return _D["d"]
        tag = snapshots.version("modelos")
        if _D["d"] is not None:
            if tag is None:  # GitHub não respondeu: continua com as tabelas atuais e confere de novo daqui a DATA_RETRY
                _D["at"] = time.time() - DATA_TTL + DATA_RETRY; return _D["d"]
            if tag == _D["tag"]: _D["at"] = time.time(); return _D["d"]
            _D["d"] = None; _cclear(); gc.collect(); _trim()  # versão nova: solta as tabelas antigas antes de baixar o snapshot
        snap = snapshots.load("modelos", max_mem_age=DATA_TTL)[0]
        if not snap or not snap.get("a"):
            snapshots.drop("modelos"); raise RuntimeError("sinais dos modelos ainda não calculados")
        if _D["key"] != snap.get("fetched_at") or _D["d"] is None:
            E = entradas()
            with snapshots.HEAVY:  # não monta junto com o histórico de todas as ações (history.all_closes)
                _D["d"] = None; _cclear(); gc.collect()
                _D["d"] = build(snap, history.bcb("cdi"), **E, consome=True); _D["key"] = snap.get("fetched_at")
            del E
        snapshots.drop("modelos"); del snap; gc.collect(); _trim()  # o snapshot bruto (listas JSON) não fica na memória
        _D["at"], _D["tag"] = time.time(), tag
        return _D["d"]


def todas(D, rows):
    """Universo "Todas" dos modelos: as empresas de hoje (1 ticker por empresa) + as que saíram da bolsa (só entram nas datas em que eram
    negociadas: sem preço no início, ficam de fora). Fonte única para Comparar → Todas, Grupo simulação, widget e o pré-cálculo."""
    return [r["ticker"] for r in rows] + [t for t in D.get("saiu", []) if t not in {r["ticker"] for r in rows}]


def _saiu(D, idx, i):
    """empresas que saíram da bolsa antes da semana i (a posição é vendida pelo último preço)."""
    if "SAI" not in D: return np.zeros(len(idx), bool)
    a = D["SAI"][idx]; return (a >= 0) & (i > a)


SAIDA_TXT = (("FAL", "falência"), ("INCORPOR", "incorporada por outra empresa"), ("VOLUNT", "fechou o capital (OPA)"),
             ("OFÍCIO", "registro cancelado pela CVM"), ("OFICIO", "registro cancelado pela CVM"), ("EXTIN", "empresa extinta"))  # motivo da CVM -> texto


def _saiu_txt(D, k):
    m = (D.get("SAIX", {}).get(k) or "").upper()
    if not m: return "deixou de ser negociada (sem motivo registrado na CVM)"
    return "saiu da bolsa: " + next((t for x, t in SAIDA_TXT if x in m), m.lower())


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


def _span(D, di, df, mesmo=False):
    """Semanas de aporte entre di e df. AAAA-MM: fins de mês (mês 1 = fim de di). AAAA-MM-DD: 1ª semana dos dados a partir do dia
    (valor inicial) + fins dos meses seguintes; df com dia termina na última semana até ele. Vazio: nenhuma semana a partir de di."""
    ym, W, ME = D["ym"], D["w"], D["me"]
    if len(di) > 7:
        di = max(di, D["ini"] + "-01")
        s = next((i for i in range(len(W)) if W[i] >= di), None)
        if s is None: return []
        me = [s] + [i for i in range(s + 1, len(ym)) if ME[i] and (ym[i] > ym[s] or mesmo) and ym[i] <= df[:7]]  # mesmo: + fim do 1º mês
    else:
        di = max(di, D["ini"])
        me = [i for i in range(len(ym)) if ME[i] and di <= ym[i] <= df[:7]]
    if len(df) > 7 and me:
        e = max((i for i in range(me[0], len(W)) if W[i] <= df), default=me[0])
        me = [i for i in me if i <= e]
        if e > me[-1]: me.append(e)
    return _Me(me, di if len(di) > 7 else None)


class _Me(list):
    """Semanas de _span com a data inicial com dia (d0): o valor inicial entra nela e nada da 1ª semana antes dela conta (Ordens)."""
    def __init__(s, me, d0=None): super().__init__(me); s.d0 = d0


def _curto(D, di):
    """Mensagem quando não há semana para simular: começo depois dos dados (espera a próxima atualização) ou fora dos dados."""
    if len(di) > 7 and di > D["w"][-1]:
        return f"Começa a operar na primeira semana a partir de {di[8:10]}/{di[5:7]}/{di[:4]} (os dados dos modelos vão até {D['w'][-1][8:10]}/{D['w'][-1][5:7]}/{D['w'][-1][:4]}); o valor fica no CDB até lá."
    return f"Período fora dos dados dos modelos ({D['ini']} a {D['fim']})."


def pode(D, mid, idx):
    """O modelo vale para cada ticker de idx? Ações: todos; ETF: só os de ETF_MOD (renda fixa: só Buy and Hold)."""
    ek = D["EK"][np.asarray(idx, int)] if "EK" in D else np.full(len(idx), "")
    return (ek == "") | np.where(ek == "rf", mid in ETF_MOD["rf"], mid in ETF_MOD["acoes"])


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
    if MOD[mid].get("sig"): M = D.get(MOD[mid]["sig"]); return M[idx, i] if M is not None else np.zeros(n, bool)  # sem set_metodos: fora
    if MOD[mid].get("frac"): return D[MOD[mid]["x"]][idx, i] > 0  # Híbrido/Adaptativo (só o 1º sinal; a simulação usa a exposição)
    if mid == "barsi":  # compra só no teto ou abaixo; acima ou sem teto: espera no CDB (nunca vende)
        with np.errstate(invalid="ignore"): return D["Cf"][idx, i] <= D["TETO"][idx, i]
    return D["FAV"][MOD[mid]["p"]][idx, i]


# Arquivo do modelo (⬇ → Modelo (regras e código) na Previsão): parâmetros e funções de cada modelo; o texto vem do próprio código
# (valor atual e comentário de cada parâmetro, fonte de cada função) e do painel ⓘ → Modelos da Previsão (server.api_modelos_ficha)
FICHA_COMUM = (("APORTE", "NCONF", "CONV", "ORD_ON", "ORD_SEM", "ORD_K", "ORD_MIN", "ORD_MAX", "ORD_FILA", "CALMA", "CALMA_FORA", "CARO", "PERDA", "CUSTO", "IR", "ISENTO", "JCP_IR", "REGRAS", "VENDA", "VPROB", "VMARG", "NOTA", "NOTICIA", "GRUPO_K", "TROCA_SEM"),
               ("_signals", "_signal", "motivo", "simulate", "Conta", "Ordens", "_calma", "_calma_mats", "_pl_rel", "_perda", "_gtargets", "_conviccao", "_regras_w", "_aporte", "_nota", "_noticia", "_news_mats", "_nconf", "_venda", "grupo", "rotate"))
FICHA = {"hold": (("HOLD", "BARSI_DY"), ("_hold_nucleo", "_hold_apostas")), "medo_mercado": (("MEDO",), ()), "medo_acao": (("MEDO",), ()), "media200": ((), ()),
         "alg1": (("MED_SEM", "MARGEM"), ()), "alg3": (("MED_SEM", "MARGEM"), ()), "tendencia": (("FORTE_R12", "MARGEM"), ()),
         "hibrido": (("HIB", "HIB_SEM", "HIB_ETA", "HIB_COMPRA"), ("_hib", "set_metodos")),
         "adapt": (("ADP", "ADP_N", "ADP_PRECO", "ADP_MEIA", "ADP_ETA", "ADP_NOTA", "ORD_KS", "HIB_COMPRA"), ("_adp_x", "_ord_ganho", "_adapt")), "barsi": (("BARSI_DY", "BARSI_ANOS", "BARSI_CAIXA", "PERENE_TXT"), ("perene", "build", "_barsi_caixa")),
         **{m: (("METODO",), ("set_metodos", "_fund_mats")) for m in ("value", "growth", "garp", "fatores")}}


def ficha(mid, guia=""):
    """Arquivo do modelo em Markdown: como funciona (guia = texto do ⓘ), parâmetros que dá para alterar, código das funções que decidem."""
    import inspect, re
    src = open(__file__, encoding="utf-8").read().split("\n")
    def doc(nome):  # comentários junto da definição do parâmetro no código (acima e na mesma linha)
        j = next((k for k, l in enumerate(src) if re.match(rf"(\w+\s*,\s*)*{nome}\s*(,[^=]*)?=", l)), None)
        if j is None: return ""
        c = []; k = j - 1
        while k >= 0 and src[k].startswith("#"): c.insert(0, src[k][1:].strip()); k -= 1
        if "#" in src[j]: c.append(src[j].split("#", 1)[1].strip())
        return " ".join(c)
    ms = [m["id"] for m in MODELOS] if mid == "*" else [mid]
    pars, funcs = list(FICHA_COMUM[0]), list(FICHA_COMUM[1])
    for m in ms:
        pars += [x for x in FICHA[m][0] if x not in pars]; funcs += [x for x in FICHA[m][1] if x not in funcs]
    nome = "Todos os modelos" if mid == "*" else MOD[mid]["n"]
    L = [f"# Modelo: {nome}", "", f"Gerado do código do site (versão das contas {ENGINE}). Para estudo, não é recomendação de investimento.", "",
         "## Como funciona", "", guia.strip() or "(explicação no painel ⓘ → Modelos da Previsão)", "",
         "## Ficha", "", *[f"- {MOD[m]['n']} (id `{m}`): vende = {'sim' if MOD[m]['vende'] else 'não (nunca vende por regra; só compra)'}"
                         + (f"; tempo mínimo em cada posição: {MOD[m]['min']} semanas" if MOD[m].get("min") else "")
                         + ("; só compra com lucro no último balanço anual publicado" if MOD[m].get("lucro") else "") for m in ms], "",
         "## Parâmetros que você pode alterar", "", "Mude o valor na coluna Valor e me mande o arquivo.", "",
         "| Parâmetro | Valor | O que faz |", "|---|---|---|"]
    for x in pars:
        v = globals().get(x)
        L.append(f"| {x} | `{json.dumps(v, ensure_ascii=False) if not isinstance(v, (set, frozenset)) else sorted(v)}` | {doc(x).replace('|', '/')} |")
    L += ["", "## Código que decide (modelos.py)", ""]
    for f in funcs:
        try: L += [f"### {f}", "", "```python", inspect.getsource(globals()[f]).rstrip(), "```", ""]
        except Exception: pass
    L += ["## Minhas mudanças", "", "Escreva aqui, em português, o que quer mudar no modelo (ex.: \"vender quando cair 15%\", \"comprar só bancos\").", "", ""]
    return "\n".join(L)


def motivo(D, mid, k, i):
    """Texto do sinal do modelo na empresa k com os dados da semana i (o que fez comprar ou vender): planilha da Previsão."""
    br = lambda x, d=1: f"{x:.{d}f}".replace(".", ",")
    lucro = "" if not MOD[mid].get("lucro") or D["LP"][k, i] else " · prejuízo no último balanço (não compra)"
    if mid == "hold": return "compra sempre (aporte e proventos)"
    if mid == "medo_mercado": return f"Medo e Ganância do mercado {br(D['MI'][i], 0)} (entra abaixo de {MEDO})"
    if mid == "medo_acao": return f"Medo e Ganância da ação {br(D['SI'][k, i], 0)} (entra abaixo de {MEDO})"
    if mid in ("media200", "tendencia"): return ("preço acima" if D["M2"][k, i] > 0 else "preço abaixo") + f" da média de 200 dias · alta em 12 meses {br(D['R12'][k, i] / 10)}%" + lucro
    if MOD[mid].get("p"): pk = MOD[mid]["p"]; return f"chance de alta {br(D['P'][pk][k, i] / 10)}% (mediana do último ano {br(D['MED'][pk][k, i] / 10)}%)" + lucro
    if mid == "barsi": return f"preço R$ {br(D['Cf'][k, i], 2)} · preço teto R$ {br(D['TETO'][k, i], 2)}" + lucro
    if MOD[mid].get("frac"):
        sn, sp = _segue(D, mid, k, i)
        nt = " · notícia ruim recente pesou contra" if mid == "adapt" and "NT" in D and D["NT"][k, max(0, i - NOTICIA["semanas"] + 1):i + 1].sum() <= NOTICIA["ruim"] else ""
        return f"exposição-alvo {br(100 * D[MOD[mid]['x']][k, i], 0)}% · segue {sn} (peso {sp}%{' neste cenário' if mid == 'adapt' else ''})" + nt
    sc = MOD[mid].get("sc")
    if sc in D:
        v = float(D[sc][k, i]); FM = D["FM"]
        if mid == "value": return f"margem sobre o valor justo de Graham {br(100 * v, 0)}%"
        if mid == "growth": return f"lucro {br(100 * v, 0)}% no ano · {br(100 * float(FM['G3'][k, i]), 0)}% ao ano em 3 anos"
        if mid == "garp": return f"PEG {br(-v, 2)}"
        return f"nota dos fatores {br(v, 2)}"
    return "sem sinal do método (sem valor de mercado)"


CALMA_TXT = " · esperou 1 semana para confirmar (oscilação rápida)"


def _perda(D, mid, idx, i, cand, sh, basis, P, ok, hw=None):
    """Venda pelo sinal no prejuízo (preço abaixo do preço médio com custos): só se a análise (_venda, sem posse mínima) achar empresa
    ruim. -> por empresa: "" = venda normal (no lucro), "-" = segura (sem aporte até recuperar ou o sinal voltar), texto = realiza o
    prejuízo com o motivo."""
    n = len(idx); mo = np.full(n, "", dtype=object)
    if mid not in PERDA["modelos"]: return mo
    pm = np.where(sh > 0, basis / np.where(sh > 0, sh, 1), 0); perda = cand & (P < pm)
    if not perda.any(): return mo
    an = _venda(D, mid, idx, i, np.where(perda, sh, 0), basis, P, ok, None, posse=False)
    for q in np.flatnonzero(perda): mo[q] = f"realizou prejuízo: {an[q]}" if an[q] else "-"
    if hw is not None:  # semanas segurando no prejuízo: sem voltar ao preço médio em PERDA['espera'], não deve retomar o patamar
        hw[:] = np.where(mo == "-", hw + 1, 0)
        for q in np.flatnonzero((mo == "-") & (hw > PERDA["espera"])): mo[q] = f"realizou prejuízo: não voltou ao preço médio em {PERDA['espera']} semanas"
    return mo


def _calma(mid, lado):
    """Matriz anti-emoção de cada modelo e lado (None = não espera): Adaptativo usa a que aprendeu por cenário (CVa/CCa)."""
    if mid in CALMA_FORA: return None
    return ("CCa" if lado == "c" else "CVa") if mid == "adapt" else ("CC" if lado == "c" else "CV")


def ord_exec(compra, lim, lo, hi):
    """Regra única de execução da ordem com preço limite (Ordens, 1º dia do grupo e a conferência ao vivo do servidor): a compra executa
    quando a mínima passa ORD_FILA abaixo do limite, pelo limite (ou pela máxima, se ela ficou abaixo dele); a venda é o espelho.
    Escalares ou matrizes; None/NaN na mínima/máxima = sem dado. -> (tocou, preço da execução)."""
    lo = np.nan if lo is None else lo; hi = np.nan if hi is None else hi
    with np.errstate(invalid="ignore"):
        if compra: return lo <= lim * (1 - ORD_FILA), np.fmin(lim, hi)
        return hi >= lim * (1 + ORD_FILA), np.fmax(lim, lo)


def compra_inteira(v, px):
    """Ações inteiras que o valor v compra ao preço px, com o custo CUSTO -> (quantidade, valor pago). Escalares ou matrizes."""
    with np.errstate(invalid="ignore", divide="ignore"):
        q = np.floor(v * (1 - CUSTO) / px + 1e-9); return q, q * px / (1 - CUSTO)


def venda_liq(q, px):
    """Valor recebido ao vender q ações a px (menos o custo CUSTO)."""
    return q * px * (1 - CUSTO)


class Ordens:
    """Ordens com preço limite de várias ações ao mesmo tempo (ORD_*): cada lado guarda o preço de referência do dia da decisão e há quantas
    semanas a ordem espera. lado(i, quer, P) -> (executa, preço, tocou): executa = tocou o limite na semana i ou venceu o prazo."""

    def __init__(s, D, idx, lado, dist="ODI", calma=None, d0=None):
        s.D, s.idx, s.c, s.dk, s.ck, s.d0 = D, np.asarray(idx, int), lado == "c", dist, calma, d0; n = len(s.idx)
        s.ref, s.sem = np.full(n, np.nan), np.zeros(n)
        s.esp, s.conf = np.zeros(n, bool), np.zeros(n, bool)  # anti-emoção: esperou nesta semana / executa depois de esperar

    def __call__(s, i, quer, P):
        D, k = s.D, s.idx
        if s.ck and i > 0 and s.ck in D:  # anti-emoção (CALMA): oscilação rápida na semana dos dados -> espera 1 semana para confirmar
            bl = quer & np.isnan(s.ref) & D[s.ck][k, i - 1] & ~s.esp
            s.conf = quer & s.esp; s.esp = bl; quer = quer & ~bl
        if i == 0 or "LO" not in D or not ORD_ON: return quer, P, np.zeros(len(k), bool)
        ref0 = D["Cf"][k, i - 1]; nova = quer & np.isnan(s.ref)
        s.ref = np.where(nova, ref0, np.where(quer, s.ref, np.nan))
        d = D[s.dk][k, i - 1]; lo, hi = D["LO"][k, i], D["HI"][k, i]
        with np.errstate(invalid="ignore"):
            lim = s.ref * (1 - d) if s.c else s.ref * (1 + d); toc, px = ord_exec(s.c, lim, lo, hi); toc = quer & toc; px = np.where(toc, px, P)
        if s.d0 and toc.any():  # 1ª semana: mínima/máxima de antes da data inicial não conta (o dinheiro ainda não existia)
            for q in np.flatnonzero(toc):
                if s.dia(i, q) < s.d0: toc[q] = False
            px = np.where(toc, px, P)
        sem_dado = quer & (np.isnan(lo) | np.isnan(d))  # semana sem mínima/máxima: executa no fechamento (como antes)
        vai = toc | sem_dado | (quer & (s.sem >= ORD_SEM - 1))
        s.sem = np.where(quer & ~vai, s.sem + 1, 0); s.ref = np.where(vai, np.nan, s.ref)
        return vai, np.where(toc, px, P), toc & ~sem_dado

    def dia(s, i, q):
        """data (AAAA-MM-DD) em que a ordem da ação q tocou o limite na semana i (dia da mínima/máxima)."""
        o = int((s.D["OL"] if s.c else s.D["OH"])[s.idx[q], i])
        if o >= 255: return s.D["w"][i]
        from datetime import date, timedelta
        return (date.fromisoformat(s.D["w"][i]) - timedelta(days=o)).isoformat()


def _dia0(D, idx, s, d0, p1=None, cr=None):
    """1º dia (data inicial com dia): nada de antes do início e nenhuma compra no momento da criação; o modelo deixa ordens com preço limite
    (ORD_*, distância de cada ação). cr (grupo criado no próprio dia de início, no pregão, 'HH:MM'): as ordens valem nesse dia, a partir do
    preço da hora da criação; executam as que o servidor viu tocar o limite (p1 {ticker: (preço, 'HH:MM', dia)}; só vale se o preço ficou entre
    a mínima e a máxima reais); as outras compram no fechamento do dia. Sem cr (data no passado ou criado fora do pregão): a referência é o
    fechamento do dia de início (DC: últimos pregões; antes deles, o da semana) e as ordens valem nos pregões seguintes até o fim da semana
    (w1); a que não tocar compra no fechamento da semana.
    -> (preços do dia de início, dia, execuções {posição em idx: (preço, dia, 'HH:MM')}, semana das ordens w1 (None com cr))."""
    W = D["w"]; P = D["C"][idx, s].astype(float); dia = W[s]; DD = D.get("DD") or []
    j = next((j for j, d in enumerate(DD) if d0 <= d <= W[s]), None)
    if j is not None: dc = D["DC"][idx, j]; P = np.where(np.isnan(dc), P, dc); dia = DD[j]
    if not cr: return P, dia, {}, (s if dia < W[s] else s + 1)
    F = {}
    for q, k in enumerate(idx):
        x = (p1 or {}).get(D["tick"][k])
        if not x or x[2] != dia: continue
        lo, hi = D["LO"][k, s], D["HI"][k, s]
        if np.isnan(lo) or np.isnan(hi) or lo * .999 <= x[0] <= hi * 1.001: F[q] = (x[0], x[2], x[1])
    return P, dia, F, None


# CDB dos modelos como na realidade: 100% do CDI por dia útil (taxa diária do Banco Central), liquidez diária e, no resgate, IR regressivo
# sobre o rendimento (até 180 dias, até 360, até 720, acima) e IOF nos primeiros 30 dias (% do rendimento, dia 1 a 29; 0 a partir do 30º)
CDB_IR = ((180, .225), (360, .20), (720, .175), (1e9, .15))
CDB_IOF = (96, 93, 90, 86, 83, 80, 76, 73, 70, 66, 63, 60, 56, 53, 50, 46, 43, 40, 36, 33, 30, 26, 23, 20, 16, 13, 10, 6, 3, 0)
_IOF = np.array(CDB_IOF, float)
CDB_TXT = "IR/IOF do resgate do CDB"


def _ci(D, d):
    """Índice acumulado do CDI no fim do dia d (AAAA-MM-DD; último dia útil até ele) e o número do dia (idade das aplicações)."""
    t = np.datetime64(d[:10], "D"); k = max(0, int(np.searchsorted(D["CID"], t, side="right")) - 1) if "CID" in D and len(D["CID"]) else -1
    return (float(D["CIC"][k]) if k >= 0 else 1.0), int(t.astype(int))


def _seg(w):
    """Segunda-feira da semana que termina em w (AAAA-MM-DD): o aporte do mês entra no início da semana, antes das compras dela."""
    from datetime import date, timedelta
    x = date.fromisoformat(w); return (x - timedelta(days=x.weekday())).isoformat()


def _cig(D, d, i):
    """Rendimento do CDB do fim do dia d até o fim da semana i (fator − 1): dinheiro que entrou/saiu no meio da semana."""
    a, _ = _ci(D, d); b, _ = _ci(D, D["w"][i]); return b / a - 1 if a > 0 else 0.0


class Caixa:
    """Aplicações no CDB de uma ou várias carteiras (vetores): cotas (valor = cotas × índice do CDI), valor aplicado e idade média das
    aplicações. resgate -> IR (+ IOF antes de 30 dias) sobre a parte do rendimento no valor resgatado."""

    def __init__(s, n):
        s.U, s.P, s.T = np.zeros(n), np.zeros(n), np.zeros(n)

    def aplica(s, v, ci, dia):
        v = np.maximum(0.0, v); m = v > 0
        s.T = np.where(m, (s.P * s.T + v * dia) / np.where(m, s.P + v, 1), s.T); s.U = s.U + v / ci; s.P = s.P + v

    def ajusta(s, saldo, ci):
        """Mantém as cotas iguais ao saldo do CDB na carteira (mesma proporção de rendimento)."""
        V = s.U * ci; k = np.where(V > 0, saldo / np.where(V > 0, V, 1), 0.0); s.U = s.U * k; s.P = s.P * k

    def resgate(s, liq, ci, dia):
        """Resgata `liq` líquido (o que a carteira precisa) -> imposto pago a mais (IR + IOF), já tirado das cotas."""
        liq = np.maximum(0.0, liq); V = s.U * ci
        with np.errstate(invalid="ignore", divide="ignore"):
            g = np.clip(np.where(V > 0, 1 - s.P / V, 0), 0, 1); age = np.maximum(0, dia - s.T)
            ir = np.select([age <= a for a, _ in CDB_IR], [r for _, r in CDB_IR])
            iof = np.where(age < 30, np.take(_IOF, np.clip(age.astype(int), 1, 30) - 1) / 100, 0.0)
            t = g * (iof + (1 - iof) * ir); gross = np.minimum(V, liq / np.maximum(1e-9, 1 - t)); f = np.where(V > 0, gross / V, 0)
        s.U = s.U * (1 - f); s.P = s.P * (1 - f)
        return np.maximum(0.0, gross - liq)  # resgate maior que o saldo (arredondamento): sem imposto a mais


class Conta:
    """Carteira de uma ou várias ações em paralelo (vetores): ações, caixa no CDB, custo, IR do mês e prejuízo a compensar."""

    def __init__(s, n):
        z = lambda: np.zeros(n)
        s.sh, s.cash, s.basis, s.carry, s.msales, s.mgain, s.mdiv = z(), z(), z(), z(), z(), z(), z()
        s.ir, s.dtax, s.divT, s.compras, s.vendas = z(), z(), z(), z(), z()
        s.cx, s.ctax = Caixa(n), z()  # CDB: aplicações (idade, rendimento) e IR/IOF pago nos resgates

    def cdb_ini(s, D, v, d, i):
        """Valor inicial aplicado no CDB na data inicial d (rende de d até o fim da 1ª semana i)."""
        ci, dia = _ci(D, d); s.cx.aplica(np.broadcast_to(np.asarray(v, float), s.cash.shape).copy(), ci, dia)
        s.cash = s.cash * (1 + _cig(D, d, i))

    def cdb_semana(s, D, i, c0, cr):
        """Fim da semana i (CDB dia a dia): o que entrou no CDB é aplicado e o que saiu é resgatado, pagando IR/IOF sobre o rendimento;
        cr = correção do rendimento das ordens executadas antes do fim da semana (dinheiro que entrou/saiu no meio dela). -> imposto."""
        F = s.cash - c0; s.cash = s.cash + cr; ci, dia = _ci(D, D["w"][i])
        s.cx.aplica(np.where(F > 0, F, 0.0), ci, dia)
        t = s.cx.resgate(np.where(F < 0, -F, 0.0), ci, dia); s.cash = s.cash - t; s.ctax = s.ctax + t
        return t

    def sell(s, mask, p, frac=None):
        """Vende (tudo ou a fração frac, arredondada para cima em ações inteiras) das ações marcadas;
        -> resultado (valor recebido − custo médio) de cada uma."""
        q = s.sh if frac is None else np.minimum(s.sh, np.ceil(s.sh * frac - 1e-9))
        q = np.where(mask, q, 0.0); f = np.where(s.sh > 0, q / np.where(s.sh > 0, s.sh, 1), 0.0)
        v = q * p * (1 - CUSTO); b = s.basis * f; g = np.where(mask, v - b, 0.0)
        s.msales += np.where(mask, q * p, 0); s.mgain += g; s.cash += np.where(mask, v, 0)
        s.sh -= q; s.basis -= b
        s.vendas += mask & (q > 0)  # cada venda conta (inclusive parcial, para retirada ou imposto)
        s.lq = q
        return g

    def buy(s, mask, p, amt=None):
        """Compra ações inteiras com o caixa (ou só `amt`) das ações marcadas; a sobra (menos que 1 ação) fica no caixa, no CDB,
        até dar para comprar pelo menos 1 ação. Custo de CUSTO sobre a compra."""
        a = s.cash if amt is None else np.minimum(s.cash, amt)
        q, c = compra_inteira(a, np.where(mask & (p > 0), p, np.inf)); q = np.where(mask, q, 0.0)
        m = q >= 1; cost = np.where(m, c, 0.0)
        s.compras += m  # cada compra conta (aportes e proventos reinvestidos também)
        s.sh += np.where(m, q, 0); s.basis += cost; s.cash = s.cash - cost
        s.lq, s.lc = np.where(m, q, 0), cost

    def raise_cash(s, need, p):
        """Vende só o necessário (ações inteiras) para ter `need` em caixa (retirada, imposto)."""
        falta = np.maximum(0, need - s.cash); val = s.sh * p * (1 - CUSTO)
        m = (falta > 0) & (val > 0)
        return s.sell(m, p, np.where(m, np.minimum(1, falta / np.where(val > 0, val, 1)), 0))

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


def anual(VM, ap, wd):
    """TIR anual (%): a taxa que faz os aportes e retiradas de cada mês (mês 1 = valor inicial) chegarem ao valor final
    (taxa interna de retorno, a mesma conta de um fundo com aportes). VM: valor no fim de cada mês (meses × empresas); usa só o último.
    Menos de 12 meses no período: sem valor (nan)."""
    VM = np.asarray(VM, dtype=float)
    if VM.ndim == 1: VM = VM[:, None]
    M = VM.shape[0]
    if M < 13: return np.full(VM.shape[1], np.nan)
    f = np.array([(ap[j] if j < len(ap) else 0) - (wd[j] if j < len(wd) else 0) for j in range(M)], dtype=float)
    V = VM[-1]; t = np.arange(M, dtype=float)
    npv = lambda r: V / (1 + r) ** (M - 1) - (f[:, None] / (1 + r)[None, :] ** t[:, None]).sum(axis=0)  # valor presente líquido
    lo, hi = np.full(V.shape, -0.99), np.full(V.shape, 1.0)  # taxa mensal entre −99% e +100%
    for _ in range(80):  # bisseção: o valor presente cai quando a taxa sobe
        mid = (lo + hi) / 2; up = npv(mid) > 0; lo = np.where(up, mid, lo); hi = np.where(up, hi, mid)
    r = (lo + hi) / 2; ok = (V > 0) & np.isfinite(V) & (np.abs(npv(r)) < np.maximum(1, np.abs(f).sum()) * 1e-6)
    return np.where(ok, ((1 + r) ** 12 - 1) * 100, np.nan)


def simulate(D, mid, idx, me, ap, wd, tx=None, divs=True, rec=False):
    """Um modelo em várias ações ao mesmo tempo (cada uma sozinha). me: semanas de fim de mês; ap/wd: aporte/retirada de cada mês.
    -> dict de vetores (valor final, aportado, IR, compras, vendas) e, com rec, as linhas mensais de cada ação."""
    idx = np.asarray(idx); n = len(idx); s, e = me[0], me[-1]
    A = Conta(n); C, DV = D["C"], D["DV"]; mod = MOD[mid]
    sig0 = _signals(D, mid, idx, s - 1) if s > 0 else np.zeros(n, bool)
    st, k = np.nan_to_num(sig0, nan=0).astype(bool), np.full(n, 10 ** 6)
    lastp = C[idx, s].copy(); mi = 0; rows = [[] for _ in range(n)] if rec else None; vm = []; cj = np.zeros(n)  # cj: rendimento do CDB no mês
    meset = {w: j for j, w in enumerate(me)}
    hw = np.zeros(n)  # semanas segurando no prejuízo (_perda)
    A.cash += ap[0]; dc, dv = ("ODc", "ODv") if mid == "adapt" else ("ODI", "ODI")  # Adaptativo: distância aprendida por cenário
    d0 = getattr(me, "d0", None)  # data inicial com dia: o valor inicial entra nela; ordens da 1ª semana só depois dela
    Oc, Ov = Ordens(D, idx, "c", dc, _calma(mid, "c"), d0), Ordens(D, idx, "v", dv, _calma(mid, "v"), d0)  # ordens com preço limite (compra e venda)
    A.cdb_ini(D, ap[0], d0 or D["w"][s], s)  # valor inicial no CDB desde a data inicial
    mov = [[{"d": getattr(me, "d0", None) or D["w"][s], "k": "aporte", "v": round(float(ap[0]), 2), "x": "valor inicial"}] for _ in range(n)] if rec else None

    def log(sh0, i, P, x, O=None, toc=None):  # rec: compras/vendas da semana (mudança no nº de ações), uma linha por empresa, com o motivo
        if not rec: return
        for q in np.flatnonzero(A.sh != sh0):
            dq = A.sh[q] - sh0[q]; v = A.sh[q] * P[q] + A.cash[q]; lim = O is not None and toc[q]
            mov[q].append({"d": O.dia(i, q) if lim else D["w"][i], "k": "compra" if dq > 0 else "venda", "t": D["tick"][idx[q]], "q": int(abs(dq)), "p": round(float(P[q]), 2),
                           "v": round(float(abs(dq) * P[q] / (1 - CUSTO) if dq > 0 else -dq * P[q] * (1 - CUSTO)), 2),
                           "x": (x if isinstance(x, str) else x(q)) + (CALMA_TXT if O is not None and O.conf[q] else "") + (f" · ordem com preço limite R$ {P[q]:.2f}".replace(".", ",") if lim else ""), "pm": round(float(A.basis[q] / A.sh[q]), 2) if A.sh[q] > 0 else None,
                           "pc": round(float(100 * A.sh[q] * P[q] / v), 1) if v > 0 else None})
    for i in range(s, e + 1):
        p = C[idx, i]; ok = ~np.isnan(p); lastp = np.where(ok, p, lastp); P = lastp
        if i > s: cj += A.cash * (D["cdb"][i] - 1); A.cash *= D["cdb"][i]
        c0, cr = A.cash.copy(), np.zeros(n)  # CDB: saldo depois do rendimento; correção das ordens executadas antes do fim da semana
        if i > s:
            if divs:
                d = A.sh * np.nan_to_num(DV[idx, i]); A.cash += d; A.mdiv += d; A.divT += d; A.dtax += A.sh * D["JT"][idx, i]
                if rec:
                    for q in np.flatnonzero(d >= 0.005):
                        mov[q].append({"d": D["w"][i], "k": "provento", "t": D["tick"][idx[q]], "q": int(A.sh[q]), "p": round(float(P[q]), 2), "v": round(float(d[q]), 2), "x": tipo(D, idx[q], i)})
        gone = _saiu(D, idx, i) & (A.sh > 0); sh0 = A.sh.copy()
        if gone.any(): A.sell(gone, P); log(sh0, i, P, "saiu da bolsa: vendida pelo último preço")  # o dinheiro fica no CDB
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
            e = D[mod["x"]][idx, i - 1] if i > 0 else np.ones(n)
        elif i > s:  # venda com preço limite (executa no dia em que a máxima toca o limite, ou no fim do prazo)
            cand = ~want & (A.sh > 0) & ok; mo = _perda(D, mid, idx, i, cand, A.sh, A.basis, P, ok, hw); cand &= mo != "-"  # no prejuízo: só empresa ruim
            vai, px, toc = Ov(i, cand, P)
            sh0 = A.sh.copy(); A.sell(vai, px); log(sh0, i, px, lambda q: mo[q] or "venda: " + motivo(D, mid, idx[q], i - 1), Ov, toc)
            for q in np.flatnonzero(toc & vai): cr[q] += A.lq[q] * px[q] * (1 - CUSTO) * _cig(D, Ov.dia(i, q), i)
        tax = 0
        j = meset.get(i)
        if j is not None and i > s:
            sh0 = A.sh.copy(); a_, w_ = (ap[j] if j < len(ap) else 0), (wd[j] if j < len(wd) else 0)
            tax = A.close_month(P, a_, w_, tx); log(sh0, i, P, "para retirada ou imposto")
            if rec:
                for q in range(n):
                    if w_ > 0: mov[q].append({"d": D["w"][i], "k": "retirada", "v": round(float(w_), 2)})
                    if tax[q] >= 0.005: mov[q].append({"d": D["w"][i], "k": "imposto", "v": round(float(tax[q]), 2)})
                    if a_ > 0: mov[q].append({"d": D["w"][i], "k": "aporte", "v": round(float(a_), 2), "x": "aporte do mês"})
        sh0 = A.sh.copy()
        if mod.get("frac"):
            V = A.sh * P + A.cash; falta = e * V - A.sh * P
            vai, px, toc = Oc(i, ok & (falta > np.maximum(HIB_COMPRA * V, 100)), P)  # só compra quando a diferença para o alvo é relevante
            A.buy(vai, px, falta)
        else:  # compra com preço limite: o dinheiro espera no CDB até a mínima do dia tocar o limite (ou o fim do prazo)
            vai, px, toc = Oc(i, buy & ok & (A.cash * (1 - CUSTO) >= P), P)
            A.buy(vai, px)
            for q in np.flatnonzero(toc & (A.lc > 0)): cr[q] -= A.lc[q] * _cig(D, Oc.dia(i, q), i)
            if mid == "barsi" and i > 0:  # caixa acima de BARSI_CAIXA: compra mesmo acima do teto (a empresa tem teto e lucro)
                ex = A.cash - BARSI_CAIXA * (A.sh * P + A.cash)
                with np.errstate(invalid="ignore"): A.buy(ok & ~buy & np.isfinite(D["TETO"][idx, i - 1]) & D["LP"][idx, i - 1] & (ex > np.maximum(P, 100)), P, ex)
        log(sh0, i, px, lambda q: "compra: " + motivo(D, mid, idx[q], i - 1), Oc, toc)
        ct = A.cdb_semana(D, i, c0, cr)  # CDB dia a dia: aplica o que entrou, resgata o que saiu (IR/IOF)
        if rec:
            for q in np.flatnonzero(ct >= 0.005): mov[q].append({"d": D["w"][i], "k": "imposto", "v": round(float(ct[q]), 2), "x": CDB_TXT})
        if j is not None: vm.append(A.sh * P + A.cash)
        if rec and j is not None:
            v = A.sh * P + A.cash
            for q in range(n):
                rows[q].append({"ym": D["ym"][i], "v": float(v[q]), "div": float(A.divT[q]), "tax": float(A.ir[q] + A.dtax[q] + A.ctax[q]),
                                "pos": (f"{F0(100 * A.sh[q] * P[q] / v[q])}% na ação · segue {_segue(D, mid, idx[q], i - 1)[0]}"
                                        if mod.get("frac") and v[q] > 0 else
                                        "Ação" if A.sh[q] > 0 and A.cash[q] < max(1, P[q]) else "CDB" if A.sh[q] <= 0 else "Ação + CDB"),
                                "c": int(A.compras[q]), "s": int(A.vendas[q]), "cdb": float(A.cash[q]), "cj": float(cj[q])})
            cj = np.zeros(n)
        mi += 1
    v = A.sh * lastp + A.cash
    return {"v": v, "ir": A.ir + A.dtax + A.ctax, "irv": A.ir, "c": A.compras, "s": A.vendas, "rows": rows, "ra": anual(vm, ap, wd),
            **({"mov": [_por_data(m) for m in mov], "sh": A.sh, "pm": np.where(A.sh > 0, A.basis / np.where(A.sh > 0, A.sh, 1), np.nan), "div": A.divT} if rec else {})}


def simulate_ref(D, rid, me, ap, wd, rec=False):
    """Referência (CDB ou Ouro) com os mesmos aportes e retiradas dos modelos. -> valor final (nan sem dado) e as linhas mensais."""
    s, e = me[0], me[-1]; meset = {w: j for j, w in enumerate(me)}; px = rid in REF_SERIE; G = D[REF_SERIE[rid]] if px else D["G"]  # ouro/índices: compra cotas
    g0 = next((i for i in range(s, e + 1) if not np.isnan(G[i])), None) if px else s
    if g0 is None: return {"v": float("nan"), "rows": [] if rec else None}
    # ouro sem cotação no início do período: os aportes esperam (sem rendimento) e compram na 1ª semana com preço (nota em _refs)
    cash, q, c, n, rows, lastg, pend = 0.0, 0.0, 0, 0, [], G[g0] if px else G[s], 0.0; vm = []; cj = 0.0; cx = Caixa(1); d0 = getattr(me, "d0", None)
    for i in range(s, e + 1):
        if rid == "cdb" and i > s: cj += cash * (D["cdb"][i] - 1); cash *= D["cdb"][i]
        if not np.isnan(G[i]): lastg = G[i]
        if px and i == g0 and pend > 0: q += pend * (1 - CUSTO) / lastg; c += 1; pend = 0.0
        j = meset.get(i)
        if j is None: continue
        a, w = (ap[j] if j < len(ap) else 0), (wd[j] if j < len(wd) else 0)
        if rid == "cdb":  # CDB como na realidade: aplicação no dia, retirada paga IR/IOF sobre o rendimento
            dd = d0 if i == s and d0 else D["w"][i]; ci, dia = _ci(D, dd)
            if w > 0: wv = min(w, cash); t = float(cx.resgate(np.array([wv]), ci, dia)[0]); cash = max(0.0, cash - wv - t)
            if a > 0: cx.aplica(np.array([a]), ci, dia); cash += a * (1 + (_cig(D, dd, i) if dd < D["w"][i] else 0))
        elif i < g0: pend = max(0.0, pend - w) + a
        else:
            if w > 0 and q > 0: sv = min(q, w / (lastg * (1 - CUSTO))); q -= sv; n += 1
            if a > 0: q += a * (1 - CUSTO) / lastg; c += 1
        v = q * lastg + pend if px else cash; vm.append(v)
        if rec: rows.append({"ym": D["ym"][i], "v": float(v), "div": 0.0, "tax": 0.0, "pos": MOD[rid]["n"], "c": c, "s": n, "cdb": float(cash), "cj": float(cj)})
        cj = 0.0
    return {"v": float(q * lastg + pend if px else cash), "rows": rows if rec else None, "g0": g0, "ra": float(anual(vm, ap, wd)[0])}


def _refs(D, me, ap, wd, apT):
    """Linhas das referências (uma vez, fora das empresas)."""
    out = []
    for m in REF:
        r = simulate_ref(D, m["id"], me, ap, wd); v = r["v"]
        ok = v == v
        nota = m["nota"] + (f"; cotação do ouro só desde {D['ym'][r['g0']][5:7]}/{D['ym'][r['g0']][:4]}: os aportes anteriores compram no primeiro preço"
                            if m["id"] == "ouro" and ok and r.get("g0", me[0]) > me[0] else "")
        ra = r.get("ra", float("nan"))
        out.append({"k": "r", "m": m["id"], "t": m["n"], "v": round(v, 2) if ok else None, "ra": round(ra, 2) if ok and ra == ra else None,
                    "pct": round((v - apT) / apT * 100, 2) if ok and apT > 0 else None, "ir": 0.0, "c": None, "s": None, "nota": nota})
    return out


TIPO_N = {"J": "JCP", "D": "dividendo", "R": "rendimento", "K": "restituição de capital"}


def tipo(D, k, i):
    """Tipo do provento da ação k na semana i (lista da B3; vazio = histórico do Yahoo, sem tipo)."""
    c = D["DT"].get((k, i)) or ""
    return " + ".join(TIPO_N[x] for x in c if x in TIPO_N) + (" (líquido de 15% de IR)" if "J" in c else "")


MOV_MAX = 400  # movimentações mandadas ao site (as mais recentes; nmov = total)


_EV_ORD = {"cdi_ap": 0, "cdi_res": 0, "imposto": 1, "retirada": 1, "provento": 2, "compra": 3, "venda": 3, "aporte": 4}


def _por_data(ev):
    """Movimentações em ordem de data (a ordem com preço limite tem o dia em que tocou, antes do fim da semana). Mesmo dia: CDI, imposto e
    retirada, proventos, compras/vendas, aporte — a tela mostra do mais novo ao mais antigo, então no dia aparece aporte, compras/vendas, CDI."""
    ev.sort(key=lambda e: (e.get("d", ""), -1 if e.get("x") == "valor inicial" else _EV_ORD.get(e.get("k"), 3)))  # valor inicial: sempre o 1º
    return ev


def _ult(ev):
    """As MOV_MAX movimentações mais recentes (o aporte inicial sempre vai junto)."""
    return ev if len(ev) <= MOV_MAX else ev[:1] + ev[-(MOV_MAX - 1):]


def _brl(v):
    """R$ 1.234,56 (texto das movimentações)."""
    return "R$ " + f"{v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _cdi(ev, d, x, s0=None):
    """Linha de aplicação (entrou) ou resgate (saiu) do CDB, sem o rendimento; s0 = saldo no CDB antes dela."""
    xt = {"x": f"havia {_brl(max(0.0, s0))} no CDB"} if s0 is not None else {}
    if x >= 0.01: ev.append({"d": d, "k": "cdi_ap", "v": round(x, 2), **xt})
    elif x <= -0.01: ev.append({"d": d, "k": "cdi_res", "v": round(-x, 2), **xt})


def rotate(D, mid, gidx, me, ap, wd, tx=None):
    """Rodízio: um modelo que vende, uma empresa do grupo por vez (a de melhor sinal), CDB quando nenhuma está favorável.
    Ações inteiras: a sobra fica no CDB. -> valor final, IR e o histórico (por empresa e cada movimentação, uma por linha)."""
    gidx = list(gidx); s, e = me[0], me[-1]; mod = MOD[mid]; nm = D["tick"]
    C, DV = D["C"], D["DV"]
    alg = "p" in mod; met = bool(mod.get("sig"))  # algoritmos · métodos (sinal e força prontos em set_metodos) · Análise técnica
    A = Conta(1); cur, k, pdiv, why_in = -1, 0, 0.0, None; lastp = {g: C[g, s] for g in gidx}
    per = {g: {"t": nm[g], "c": 0, "sem": 0, "n": 0, "res": 0.0, "ir": 0.0} for g in gidx}
    trocas, cdbw, tot, vm, ev = 0, 0, 0, [], []; nav, navpk, dd, vprev = 1.0, 1.0, 0.0, None
    meset = {w: j for j, w in enumerate(me)}; A.cash += ap[0]; mg = {}; mdc = {}  # resultado das vendas do mês por empresa (para dividir o IR)
    ev.append({"d": getattr(me, "d0", None) or D["w"][s], "k": "aporte", "v": round(float(ap[0]), 2), "x": "valor inicial"})
    pct = lambda x: f"{x / 10:.1f}%".replace(".", ",")

    def score(g, i):  # (força do sinal, favorável?); modelos com "lucro": só com lucro no último balanço publicado
        ok = bool(D["LP"][g, i]) or not mod.get("lucro")
        if alg: return D["P"][mod["p"]][g, i], bool(D["FAV"][mod["p"]][g, i]) and ok
        if met: return (D[mod["sc"]][g, i], bool(D[mod["sig"]][g, i])) if mod["sig"] in D else (np.nan, False)
        return D["R12"][g, i], bool(D["M2"][g, i] > 0) and ok

    def strong(g, i):  # bom momento para comprar: chance bem acima da mediana do ano (algoritmos) ou alta forte em 12 meses (Análise técnica)
        if alg: return D["P"][mod["p"]][g, i] - D["MED"][mod["p"]][g, i] >= MARGEM[mid]
        if met: return True  # o sinal do método já é a entrada
        return D["M2"][g, i] > 0 and D["R12"][g, i] >= FORTE_R12

    def why(g, i):
        sc, _ = score(g, i)
        if met: return f"sinal do método {mod['n']}"
        return f"chance de alta {pct(sc)}" if alg else f"alta de {pct(sc)} em 12 meses e acima da média de 200 dias"

    def sell_cur(P, i, motivo):
        nonlocal cur, pdiv
        b0 = A.basis[0]; g = A.sell(np.array([True]), np.array([P]))[0]
        per[cur]["res"] += g; mg[cur] = mg.get(cur, 0) + g; per[cur]["n"] += 1
        ev.append({"d": D["w"][i], "k": "venda", "t": nm[cur], "q": int(A.lq[0]), "p": round(float(P), 2), "v": round(b0 + g, 2), "x": motivo,
                   "pct": round((g + pdiv) / b0 * 100, 2) if b0 > 0 else None}); cur = -1; pdiv = 0.0  # resultado com proventos

    for i in range(s, e + 1):
        for g in gidx:
            if not np.isnan(C[g, i]): lastp[g] = C[g, i]
        if i > s:
            A.cash *= D["cdb"][i]
        c0 = A.cash[0] - (ap[0] if i == s else 0)  # saldo no CDB depois do rendimento (base da linha de aplicação/resgate)
        cc0 = A.cash - (ap[0] if i == s else 0)
        if i > s and cur >= 0:
            d = A.sh[0] * np.nan_to_num(DV[cur, i]); A.cash += d; A.mdiv += d; A.divT += d; per[cur]["res"] += d; pdiv += d; mdc[cur] = mdc.get(cur, 0) + d
            A.dtax += A.sh[0] * D["JT"][cur, i]
            if d >= 0.005: ev.append({"d": D["w"][i], "k": "provento", "t": nm[cur], "q": int(A.sh[0]), "p": round(float(lastp[cur]), 2), "v": round(float(d), 2), "x": tipo(D, cur, i)})
        if i > 0:
            # só entra numa empresa em bom momento (sinal forte); senão o dinheiro espera no CDB
            cand = [(score(g, i - 1)[0], g) for g in gidx if not np.isnan(C[g, i]) and score(g, i - 1)[1] and not np.isnan(score(g, i - 1)[0]) and strong(g, i - 1)]
            best = max(cand)[1] if cand else -1
            saiu = False
            if cur >= 0:
                k += 1
                sc, fav = score(cur, i - 1)
                if not fav and k >= mod["min"] and not np.isnan(C[cur, i]):
                    sell_cur(lastp[cur], i, "previsão desfavorável" if alg else f"saiu do critério do método {mod['n']}" if met else "abaixo da média de 200 dias"); saiu = True  # espera ao menos 1 semana
                elif best >= 0 and best != cur and k >= TROCA_SEM and not np.isnan(C[cur, i]) and score(best, i - 1)[0] >= sc + MARGEM.get(mid, mod.get("mg", 0)):
                    sell_cur(lastp[cur], i, f"troca: {nm[best]} com sinal melhor"); trocas += 1  # troca direta: a outra está em bom momento agora
            if cur < 0 and best >= 0 and not saiu:
                cur, k = best, 0; per[cur]["c"] += 1; why_in = why(cur, i - 1)
        P = lastp[cur] if cur >= 0 else 0.0
        j = meset.get(i)
        flow = 0.0
        if j is not None and i > s:
            a, w = (ap[j] if j < len(ap) else 0), (wd[j] if j < len(wd) else 0)
            ir0, mgain, t0, sh0 = A.ir[0], dict(mg), A.ir[0] + A.dtax[0], A.sh[0]
            if tx is None: A.mdiv[:] = sum(x for x in mdc.values() if x > 50000)  # 10% só sobre a empresa pagadora acima de R$ 50 mil
            mdc.clear(); A.close_month(np.array([P]), np.array([a]), np.array([w]), tx)
            ir = A.ir[0] - ir0; t1 = A.ir[0] + A.dtax[0] - t0
            pos = {g: x for g, x in mgain.items() if x > 0}
            for g, x in pos.items(): per[g]["ir"] += ir * x / sum(pos.values())
            mg.clear(); flow = a - w; dw = D["w"][i]
            if sh0 > A.sh[0] and cur >= 0:
                ev.append({"d": dw, "k": "venda", "t": nm[cur], "q": int(sh0 - A.sh[0]), "p": round(float(P), 2), "v": round(float((sh0 - A.sh[0]) * P * (1 - CUSTO)), 2), "x": "para retirada ou imposto"})
            if w > 0: ev.append({"d": dw, "k": "retirada", "v": round(float(w), 2)})
            if t1 >= 0.005: ev.append({"d": dw, "k": "imposto", "v": round(float(t1), 2)})
            if a > 0: ev.append({"d": dw, "k": "aporte", "v": round(float(a), 2), "x": "aporte do mês"})
        if cur >= 0:
            A.buy(np.array([True]), np.array([P]))
            if A.lq[0] >= 1:
                ev.append({"d": D["w"][i], "k": "compra", "t": nm[cur], "q": int(A.lq[0]), "p": round(float(P), 2), "v": round(float(A.lc[0]), 2), **({"x": why_in} if why_in else {})})
                why_in = None
        if not cur >= 0 or A.sh[0] <= 0: cdbw += 1
        _cdi(ev, D["w"][i], A.cash[0] - c0, c0)
        ct = A.cdb_semana(D, i, cc0, np.zeros(1))[0]  # CDB: aplica/resgata na semana, IR/IOF no resgate
        if ct >= 0.005: ev.append({"d": D["w"][i], "k": "imposto", "v": round(float(ct), 2), "x": CDB_TXT})
        tot += 1
        if cur >= 0: per[cur]["sem"] += 1
        v = A.sh[0] * P + A.cash[0]
        if vprev: nav *= (v - flow) / vprev if vprev > 0 else 1
        vprev = v; navpk = max(navpk, nav); dd = min(dd, nav / navpk - 1)
        if j is not None: vm.append(v)
    v = A.sh[0] * (lastp[cur] if cur >= 0 else 0) + A.cash[0]
    if cur >= 0:
        per[cur]["res"] += A.sh[0] * lastp[cur] - A.basis[0]; per[cur]["n"] += 1
    emp = [dict(x, sem=round(x["sem"] / max(1, x["n"]), 1), res=round(x["res"], 2), ir=round(x["ir"], 2)) for x in per.values() if x["c"]]
    emp.sort(key=lambda x: -x["res"])
    return {"v": float(v), "ir": float(A.ir[0] + A.dtax[0] + A.ctax[0]), "irv": float(A.ir[0]), "c": int(A.compras[0]), "s": int(A.vendas[0]), "ra": float(anual(vm, ap, wd)[0]),
            "hist": {"emp": emp, "trocas": trocas, "cdb": round(cdbw / max(1, tot) * 100, 1), "dd": round(dd * 100, 1), "mov": _ult(_por_data(ev)), "nmov": len(ev),
                     "cash": round(float(A.cash[0]), 2), "sh": int(A.sh[0]), "t": nm[cur] if cur >= 0 else None}}


def run(D, req):
    """Pedido da aba Previsão -> linhas do Desempenho (grupos primeiro) e, com tab, as linhas mensais de uma simulação."""
    di, df = str(req.get("di") or ""), str(req.get("df") or "")
    me = _span(D, di, df)
    if not me: return {"error": _curto(D, di)}
    ap = [max(0.0, float(x or 0)) for x in (req.get("ap") or [])][:len(me)]
    wd = [max(0.0, float(x or 0)) for x in (req.get("w") or [])][:len(me)]
    ap += [0.0] * (len(me) - len(ap)); wd += [0.0] * (len(me) - len(wd))
    tx = req.get("tx"); tx = None if tx is None else max(0.0, min(100.0, float(tx)))
    key = _ckey(D["at"], di, df, ap, wd, tx, req.get("ticker"), req.get("modelo"), req.get("grupos"), req.get("tab"))
    hit = _cget(key)
    if hit is not None: return hit
    apT = sum(ap)
    ini = {"ini": D["ym"][me[0]], "fim": D["ym"][me[-1]], "meses": len(me), "apT": apT}
    ok = lambda k: not np.isnan(D["C"][k, me[0]])
    if req.get("tab"):  # tabela mês a mês de uma empresa com um modelo (com e sem proventos)
        t, mid = req["tab"].get("t"), req["tab"].get("m")
        if mid in MOD and MOD[mid].get("ref"):  # CDB / Ouro: não depende da empresa
            r = simulate_ref(D, mid, me, ap, wd, rec=True)["rows"]
            if not r: return {"error": f"{MOD[mid]['n']} sem dados em {D['ym'][me[0]]}."}
            return _cput(key, dict(ini, tab=[dict(x, sem=x["v"], com=x.pop("v")) for x in r]))
        if t not in D["ix"] or mid not in MOD: return {"error": "Empresa ou modelo sem dados."}
        k = D["ix"][t]
        if not ok(k): return {"error": f"{t} ainda não negociava em {D['ym'][me[0]]}."}
        if not pode(D, mid, [k])[0]: return {"error": f"{t} é ETF: o modelo {MOD[mid]['n']} não se aplica."}
        rc = simulate(D, mid, [k], me, ap, wd, tx, True, True); com = rc["rows"][0]
        sem = simulate(D, mid, [k], me, ap, wd, tx, False, True)["rows"][0]
        pm = float(rc["pm"][0])
        out = dict(ini, tab=[dict(c, sem=x["v"], com=c.pop("v")) for c, x in zip(com, sem)], mov=rc["mov"][0],  # planilha: movimentações e resumo
                   res={"sh": int(rc["sh"][0]), "pm": None if pm != pm else round(pm, 2), "div": round(float(rc["div"][0]), 2), "vende": MOD[mid]["vende"]})
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
                        gi = [k for k, o in zip(gi, pode(D, mid, gi)) if o]  # ETF só nos modelos de preço
                        if len(gi) < 2: continue  # empresa listada depois do início entra no rodízio quando passa a ter preço
                        r = rotate(D, mid, gi, me, ap, wd, tx)
                        rows.append({"k": "g", "m": mid, "n": str(g.get("n") or "")[:60], "t": [D["tick"][x] for x in gi], "v": round(r["v"], 2),
                                     "pct": pc(r["v"]), "ra": None if r["ra"] != r["ra"] else round(r["ra"], 2), "ir": round(r["ir"], 2), "irv": round(r["irv"], 2), "c": r["c"], "s": r["s"], "hist": r["hist"]})
                un = [k for k, o in zip(uni, pode(D, mid, uni)) if o]
                if not un: continue
                r = simulate(D, mid, un, me, ap, wd, tx)
                fo = fora_barsi(D, un, me) if mid == "barsi" else np.zeros(len(un), bool)
                best = sorted((q for q in range(len(un)) if not fo[q]), key=lambda q: -r["v"][q])[:10]
                rows += [{"k": "a", "m": mid, "t": D["tick"][un[q]], "v": round(float(r["v"][q]), 2), "pct": pc(r["v"][q]), "ra": None if np.isnan(r["ra"][q]) else round(float(r["ra"][q]), 2),
                          "ir": round(float(r["ir"][q]), 2), "irv": round(float(r["irv"][q]), 2), "c": int(r["c"][q]), "s": int(r["s"][q])} for q in best]
        else:
            t = req.get("ticker")
            if t not in D["ix"]: return {"error": f"{t} sem dados para os modelos."}
            k = D["ix"][t]
            if not ok(k): return {"error": f"{t} ainda não negociava em {D['ym'][me[0]]}."}
            if len(mids) == 1 and mids[0] != "hold": mids = mids + ["hold"]  # referência: comprar e segurar
            if not pode(D, mids[0], [k])[0] and len(mids) == 2:
                return {"error": f"{t} é ETF: {'renda fixa só entra no Buy and Hold' if D['EK'][k] == 'rf' else 'só entra nos modelos de preço'} (sem balanço)."}
            mids = [m for m in mids if pode(D, m, [k])[0]]
            for mid in mids:
                r = simulate(D, mid, [k], me, ap, wd, tx)
                rows.append({"k": "a", "m": mid, "t": t, "v": round(float(r["v"][0]), 2), "pct": pc(r["v"][0]), "ra": None if np.isnan(r["ra"][0]) else round(float(r["ra"][0]), 2), "ir": round(float(r["ir"][0]), 2), "irv": round(float(r["irv"][0]), 2),
                             "c": int(r["c"][0]), "s": int(r["s"][0]), **({"fora": True} if mid == "barsi" and fora_barsi(D, [k], me)[0] else {})})
        rows.sort(key=lambda x: (x["k"] != "g", -(x["pct"] if x["pct"] is not None else -1e9)))  # grupos; depois modelos e CDB/Ouro pelo rendimento
        out = dict(ini, rows=rows, aviso=AVISO)
    return _cput(key, out)


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


# ---------------------------------------------------------------------------
# Pré-cálculo (rotina diária -> snapshot modelos_pre): Comparar → Modelos com os valores padrão, Todas e 5 maiores de cada setor,
# 5/10/15/20 anos e todo o período. Só é usado quando TODA a entrada bate (sinais, CDB, ouro, empresas, setores perenes, período e aportes).
PRE_INI, PRE_AP, PRE_ANOS = 20000.0, 500.0, (5, 10, 15, 20, None)  # valores padrão do Comparar (comparar.js); None = todo o período
_PRE = {"at": None, "e": {}}
PRE_VER = 13  # 13: aporte, Buy and Hold e confiança nas notícias; 12: CDB com IR/IOF; 11: ordens com fila; 10: alvos caros; 9: ordens ligadas + anti-emoção; 8: ordens com preço limite; 7: modelo Adaptativo; 6: colocações só entre os modelos; muda quando a resposta do compare ganha campos (respostas antigas deixam de valer)


def pre_key(D, tickers, idx, me, aps):
    h = hashlib.sha1(repr((PRE_VER, ENGINE, D["fp"], tuple(dict.fromkeys(tickers)), tuple(idx), tuple(np.flatnonzero(D["BS"][idx]).tolist()),
                           me[0], me[-1], [round(x, 2) for x in aps])).encode())
    return h.hexdigest()[:24]


def set_pre(snap):
    """Carrega o snapshot modelos_pre (chave -> resposta pronta do compare)."""
    at = (snap or {}).get("fetched_at")
    if at != _PRE["at"]: _PRE["at"] = at; _PRE["e"] = dict((snap or {}).get("e") or {})


def ranking(V, nref=0):
    """V: (modelos + nref referências no fim) × empresas (valor final; nan = fora, ex.: Método Barsi fora do método).
    -> posição pelo rendimento SÓ entre os modelos (0 = 1º; -1 = fora; referências sempre -1: não são modelos), contagem por posição
    (colunas 1º…nº de modelos; referências zeradas), ordem das Colocações (mais 1º lugares; empate -> mais 2º…; empate em tudo -> maior
    média; referências no fim) e pontos (PONTOS pela colocação entre os modelos; referências 0)."""
    n = V.shape[0]; nm = n - nref; ok = ~np.isnan(V); ok[nm:] = False
    r = (-np.where(ok, V, -np.inf)).argsort(axis=0, kind="stable").argsort(axis=0)
    rk = np.where(ok, r, -1)
    sc = np.array(PONTOS + (0,) * n)
    pts = np.where(ok, sc[np.maximum(rk, 0)], 0).sum(axis=1)
    cnt = np.array([[int((rk[i] == p).sum()) for p in range(nm)] for i in range(n)])
    order = sorted(range(n), key=lambda i: (i >= nm,) + tuple(-cnt[i]) + (-_nmean(V[i]),))
    return rk, cnt, order, pts


# ---------- Modo Grupo (Comparar → Modelos → Grupo): uma carteira por modelo ----------
# Nunca vendem: dividem aporte e proventos entre as empresas que o sinal permite (Barsi: no teto ou abaixo, mais peso para o maior
# rendimento; Híbrido: pela exposição alvo); sem sinal, esperam no CDB. Algoritmos e Análise técnica: até GRUPO_K empresas de melhor sinal,
# vendem quando o sinal fica desfavorável (respeitando o tempo mínimo). Custos e IR da carteira (isenção de R$ 20 mil no mês).
GRUPO_K = 5  # modelos que vendem: até K empresas de melhor sinal (0 = sem limite fixo: o peso por convicção decide quantas, CONV)
# Peso por convicção (modo Grupo; desligado: nos testes de 2011, 2016 e 2021 rendeu menos e não concentrou o bastante): nota 0–1 de cada empresa que passa no critério = metade a força do sinal do próprio modelo (posição
# entre as candidatas) e metade a nota de qualidade (só a nota nos modelos sem sinal por empresa); abaixo de 'min' não recebe aporte;
# empresa nova só entra com convicção perto da melhor do momento (até 'faixa' abaixo dela); quem já está fica enquanto a convicção não cai
# abaixo de 'min' (os modelos que vendem vendem aí); peso ∝ convicção^p (as melhores pesam bem mais); 'nucleo' ou mais = núcleo, abaixo =
# aposta (peso até 'aposta'); empresa nova só entra se a fatia der pelo menos 'wmin' da carteira. O número de empresas sai da convicção e
# do tamanho da carteira (REGRAS['max'] só protege)
CONV = {"on": False, "min": .35, "faixa": .15, "p": 3, "nucleo": .7, "aposta": .05, "wmin": .05}


def _conviccao(D, mid, idx, j, w, held):
    """Pesos alvo por convicção (CONV) a partir dos alvos do modelo w (> 0 = passa no critério); held = já na carteira.
    -> (pesos, convicção, fica: quem está na carteira e continua com convicção mínima)."""
    n = len(idx); c = w > 0
    if not c.any(): return w, np.zeros(n), np.zeros(n, bool)
    sig = None
    if mid in ("alg1", "alg3"): sig = D["P"][MOD[mid]["p"]][idx, j]
    elif mid == "tendencia": sig = D["R12"][idx, j]
    elif MOD[mid].get("sc") and MOD[mid]["sc"] in D: sig = D[MOD[mid]["sc"]][idx, j]
    elif mid == "medo_acao": sig = -D["SI"][idx, j]
    elif mid in ("barsi", "hibrido", "adapt"): sig = w
    q, _ = _nota(D, idx, j); q = np.nan_to_num(q, nan=50.0) / 100
    if sig is not None:
        sg = np.where(c, np.nan_to_num(np.asarray(sig, float), nan=-1e9), -np.inf); k = np.flatnonzero(c)
        r = np.empty(len(k)); r[np.argsort(sg[k], kind="stable")] = np.arange(len(k)); pct = np.zeros(n)
        pct[k] = r / max(1, len(k) - 1) if len(k) > 1 else 1.0
        cv = np.where(c, .5 * pct + .5 * q, 0.0)
    else: cv = np.where(c, q, 0.0)
    fica = held & c & (cv >= CONV["min"]); entra = c & (cv >= max(CONV["min"], cv.max() - CONV["faixa"]))
    x = np.where(fica | entra, cv ** CONV["p"], 0.0)
    if not x.any(): x = np.where(cv == cv.max(), 1.0, 0.0) * c  # nenhuma com convicção mínima: só a melhor
    for _ in range(3):  # aposta com peso limitado
        t = x.sum(); x = x / t if t > 0 else x
        x = np.where((cv < CONV["nucleo"]) & (x > CONV["aposta"]), CONV["aposta"], x)
    while True:  # empresa nova só se a fatia fizer diferença: tira a nova de menor peso até todas terem pelo menos 'wmin'
        t = x.sum(); nov = np.flatnonzero(~held & (x > 0))
        if t <= 0 or not len(nov): break
        k = nov[np.argmin(x[nov])]
        if x[k] / t >= CONV["wmin"]: break
        x[k] = 0.0
    t = x.sum(); return (x / t if t > 0 else x), cv, fica
def _gtargets(D, mid, idx, i):
    """pesos alvo (soma 1, ou 0 = espera no CDB) e 'quer manter' de cada empresa, com dados da semana i."""
    n=len(idx); ok=~np.isnan(D['C'][idx,i])
    if mid=='hold': w=_hold_nucleo(D,idx,i) if HOLD['on'] else ok.astype(float)
    elif MOD[mid].get('frac'): w=np.nan_to_num(D[MOD[mid]['x']][idx,i])*ok  # Híbrido/Adaptativo: exposição alvo
    elif mid=='barsi':
        T=D['TETO'][idx,i]; P=D['Cf'][idx,i]
        with np.errstate(invalid='ignore'): z=ok&D['BS'][idx]&(P<=T)&D['LP'][idx,i]
        w=np.where(z,np.nan_to_num(T/P),0)  # mais peso para o maior rendimento de dividendos
    elif MOD[mid].get('sc') and MOD[mid]['sc'] not in D: w=np.zeros(n)  # sem set_metodos (sem valor de mercado): fica no CDB
    elif mid in('alg1','alg3','tendencia') or MOD[mid].get('sc'):
        sig=_signals(D,mid,idx,i)&ok
        sc=(D[MOD[mid]['sc']][idx,i] if MOD[mid].get('sc') else D['P'][MOD[mid]['p']][idx,i] if mid!='tendencia' else D['R12'][idx,i]).astype(float)
        sc=np.where(sig,np.nan_to_num(sc,nan=-1e9),-np.inf)
        top=np.argsort(-sc)[:GRUPO_K] if GRUPO_K else np.argsort(-sc); w=np.zeros(n); w[top[np.isfinite(sc[top])]]=1
    else: w=(_signals(D,mid,idx,i)&ok).astype(float)
    s=w.sum(); return (w/s if s>0 else w)
def _regras_w(D, mid, idx, i, w, sh, pend, RG, ban):
    """Alvos do modelo com as regras de carteira (REGRAS): sem liquidez da época não compra; recém-vendida fica de fora;
    nota de qualidade abaixo de NOTA['min_compra'] não entra; no máximo RG['max'] empresas — quem já está na carteira mantém a vaga,
    as novas pelo sinal do modelo × nota (pesos diferentes: Barsi, Híbrido) ou pela nota (modelos de peso igual), empate pelo volume."""
    vol = D["VL"][idx, max(0, i - 1)] if "VL" in D else np.full(len(idx), np.nan)
    if RG.get("liq"): w = np.where(np.isnan(vol) | (vol >= RG["liq"]), w, 0)  # sem volume no snapshot antigo: regra não se aplica
    w = np.where(ban > 0, 0, w)
    q, _ = _nota(D, idx, max(0, i - 1)); held = (sh > 0) | (pend > 0)
    w = np.where(held | np.isnan(q) | (q >= NOTA["min_compra"]), w, 0)  # nota baixa não entra (quem já está fica; a venda decide)
    nv, _ = _noticia(D, idx, max(0, i - 1)); w = np.where(held | (nv > NOTICIA["ruim"]), w, 0)  # fato negativo recente: não entra
    if RG.get("max"):
        held = (sh > 0) | (pend > 0); cand = (w > 0) & ~held; room = max(0, RG["max"] - int(held.sum()))
        keep = held.copy()
        if room and cand.any():
            c = np.flatnonzero(cand); qn = np.nan_to_num(q[c], nan=50.0)
            crit = w[c] * (.5 + qn / 100) if np.ptp(w[c]) > 1e-12 else qn  # sinal do modelo pesado pela nota; peso igual: pela nota
            keep[c[np.lexsort((-np.nan_to_num(vol[c]), -crit))[:room]]] = True  # empate: maior volume
        w = np.where(keep, w, 0)
    t = w.sum(); return w / t if t > 0 else w


def _nota(D, idx, j):
    """nota de qualidade (0–100, NaN sem dados) e porte (-1 sem dado … 3 gigante) das empresas na semana j."""
    FM = D.get("FM")
    if not FM or "Q" not in FM: n = len(idx); return np.full(n, np.nan), np.full(n, -1)
    return FM["Q"][idx, j].astype(float), FM["PORTE"][idx, j].astype(int)


def _noticia(D, idx, j):
    """soma do tom das notícias das últimas NOTICIA['semanas'] semanas até j (só as já publicadas) e o texto da mais forte."""
    if "NT" not in D: return np.zeros(len(idx)), [""] * len(idx)
    a = max(0, j - NOTICIA["semanas"] + 1); v = D["NT"][idx, a:j + 1].sum(axis=1).astype(float); NX = D["NX"]; tx = []
    for k in idx:
        c = [(NX[(k, i)], i) for i in range(j, a - 1, -1) if (k, i) in NX]; tx.append(c[0][0] if c else "")
    return v, tx


def _desc(q, po):
    """'nota 62, grande' (texto curto das movimentações)."""
    t = [f"nota {q:.0f}"] if q == q else []
    if po >= 0: t.append(PORTE_N[po])
    return ", ".join(t)


def _venda(D, mid, idx, i, sh, basis, P, ok, age, posse=True):
    """Venda ocasional dos modelos de segurar (REGRAS['venda']) por pontos -> motivo por empresa ('' = mantém). Só com ≥ VENDA['posse'] semanas.
    Problemas (VPROB): prejuízo nos 2 últimos balanços (grande: GRANDE), prejuízo no último; sem proventos há 2 anos e 30% abaixo do
    preço médio; Método Barsi: corte forte de dividendos (mediana de 2 anos < metade da de 5) com rendimento sobre o custo
    (12 meses ÷ preço médio) < 6%. Margem (VMARG): nota de qualidade de antes da crise, porte, histórico forte de lucro, crise do setor,
    crise no mercado. Vende quando há problema e problemas − margem ≥ VENDA['limite']. No prejuízo (preço abaixo do preço médio) um
    balanço ruim isolado não conta: só problema que indica empresa ruim, que não deve voltar ao patamar (posse=False: análise do
    prejuízo dos modelos que vendem, sem posse mínima)."""
    n = len(idx); out = np.full(n, "", dtype=object); FM = D.get("FM")
    held = (sh > 0) & ok & ((age >= VENDA["posse"]) if posse else True)
    if "EK" in D: held &= D["EK"][np.asarray(idx, int)] == ""  # ETF: sem venda por pontos (não tem balanço)
    if not held.any(): return out
    j = max(0, i - 1); DVn = np.nan_to_num(D["DV"][idx, max(0, i - 104):i]); pm = np.where(sh > 0, basis / np.where(sh > 0, sh, 1), 0)
    z = np.zeros(n, bool); g = (lambda k: FM[k][idx, j]) if FM else (lambda k: z)
    pr = np.zeros(n); txt = [[] for _ in range(n)]
    def prob(m, pts, t):
        for q in np.flatnonzero(m & held): pr[q] += pts; txt[q].append(t)
    p2, gr = g("PREJ2"), g("GRANDE")
    prob(p2 & gr, VPROB["prej_grande"], "prejuízo grande em 2 balanços seguidos")
    prob(p2 & ~gr, VPROB["prej2"], "prejuízo em 2 balanços seguidos")
    perda = P < pm
    prob(g("PREJ") & ~p2 & ~(perda & (mid in PERDA["modelos"])), VPROB["prej"], "prejuízo no último balanço")
    qn, po = _nota(D, idx, j)
    prob((DVn.sum(axis=1) <= 0) & (P < (1 - VENDA["queda"]) * pm), VPROB["sem_prov"], "sem proventos há 2 anos e 30% abaixo do preço médio")
    if FM and "DIV" in FM:
        dx = FM["DLX"][idx, j]
        for q in np.flatnonzero(FM["DIV"][idx, j] & held):
            pr[q] += VPROB["divida"]; txt[q].append("dívida com EBITDA negativo e subindo" if np.isinf(dx[q]) else f"dívida {dx[q]:.1f}× o EBITDA e subindo".replace(".", ","))
    if mid == "barsi":
        med5 = D["TETO"][idx, j] * BARSI_DY
        corte = (np.nan_to_num(DVn.sum(axis=1) / 2) < 0.5 * np.nan_to_num(med5, nan=0)) & ~np.isnan(med5)
        yoc = np.where(pm > 0, DVn[:, -52:].sum(axis=1) / np.where(pm > 0, pm, 1), 0)
        prob(corte & (yoc < .06), VPROB["corte"], "corte de dividendos (rendimento sobre o custo abaixo de 6%)")
    nv, ntx = _noticia(D, idx, j)
    for k in np.flatnonzero(held & (nv <= NOTICIA["ruim"])):
        pr[k] += min(NOTICIA["prob_max"], -nv[k]); txt[k].append(f"notícia: {ntx[k]}" if ntx[k] else "notícia negativa")
    if not pr.any(): return out
    cri = D["CRI"][idx, j]; cg = bool(D["CG"][j]) if "CG" in D else False
    mg = np.where(np.isnan(qn), 0, (qn - 50) / VMARG["nota"]) + np.array([VMARG["porte"][x] if x >= 0 else 0 for x in po])
    mg += VMARG["forte"] * g("FORTE") + VMARG["setor"] * cri + VMARG["mercado"] * cg + np.clip(nv, 0, NOTICIA["marg_max"])
    for k in np.flatnonzero((pr > 0) & (pr - mg >= VENDA["limite"])):
        ctx = [_desc(qn[k], po[k])] + (["sem histórico forte de lucro"] if not g("FORTE")[k] else []) + ["sem crise no setor nem no mercado"]
        out[k] = "; ".join(txt[k]) + " — " + ", ".join(c for c in ctx if c)
    return out


def _barsi_caixa(D, idx, i, w, sh, P, ok, cash, pend, RG, ban):
    """Método Barsi no modo Grupo: caixa acima de BARSI_CAIXA do patrimônio -> o excedente vai para as empresas no teto ou abaixo (pelos pesos
    do alvo) ou, sem nenhuma, para a menos esticada (menor prêmio sobre o teto) entre as do método que passam nas regras de carteira."""
    tv = (sh * P).sum() + pend.sum() + cash; ex = cash - BARSI_CAIXA * tv
    if ex < max(RG.get("min_compra", 0) if RG else 0, 1): return cash, pend
    if w.sum() > 0: pend = pend + ex * w / w.sum(); return cash - ex, pend
    T = D["TETO"][idx, i - 1]
    with np.errstate(invalid="ignore", divide="ignore"):
        el = ok & D["BS"][idx] & D["LP"][idx, i - 1] & np.isfinite(T) & (P > 0); wc = np.where(el, T / np.where(P > 0, P, 1), 0)
    if RG and wc.sum() > 0: wc = _regras_w(D, "barsi", idx, i, wc / wc.sum(), sh, pend, RG, ban)
    if not (wc > 0).any(): return cash, pend
    k = int(np.argmax(wc)); pend = pend.copy(); pend[k] += ex  # maior teto ÷ preço = menor prêmio sobre o teto
    return cash - ex, pend


# Aporte (modo Grupo, todos os modelos): primeiro reforça as empresas da carteira que estão boas para isso (o modelo ainda quer, não está
# cara (P/L até CARO['pl'] × a mediana do próprio P/L de 5 anos), nota a partir de 'nota', sem fato ruim recente, abaixo do teto); concentra
# na mais atrativa (nota × quão barata está, pelo sinal do modelo) até 'teto' da carteira por empresa e só passa para a próxima quando ela
# enche; empresa nova só com menos de 'min_emp' na carteira, nenhuma boa para reforçar ou nota pelo menos 'nota_nova' acima da melhor delas
APORTE = {"on": True, "teto": .20, "min_emp": 5, "nota": 50, "nota_nova": 15, "segurar": True, "sobra": True}
# Buy and Hold no modo Grupo: núcleo de dividendos (proventos em 4 dos 5 últimos anos e nota a partir de 'nota'; peso ∝ rendimento médio
# dos proventos × nota) + até 'n_aposta' apostas de crescimento (Growth ou GARP com o preço acima da média de 200 dias) com até 'aposta'
# da carteira; aposta realiza o lucro com 'lucro' acima do preço médio (o dinheiro vai para as de dividendos), sai com 'stop' abaixo dele
# ou quando o lucro do último ano cai (parou de crescer)
HOLD = {"on": True, "nota": 50, "aposta": .15, "n_aposta": 3, "lucro": .30, "stop": .20}


def _hold_nucleo(D, idx, i):
    """Pesos do núcleo de dividendos do Buy and Hold (HOLD) na semana i; sem nenhuma pagadora regular: todas (ETFs, anos sem dados)."""
    ok = ~np.isnan(D["C"][idx, i]); T = D["TETO"][idx, i]; P = D["Cf"][idx, i]; q, _ = _nota(D, idx, i)
    with np.errstate(invalid="ignore", divide="ignore"):
        dy = np.where(ok & np.isfinite(T) & (P > 0), T * BARSI_DY / np.where(P > 0, P, 1), 0.0)  # rendimento médio dos proventos de 5 anos
    w = np.where((dy > 0) & (np.isnan(q) | (q >= HOLD["nota"])), dy * np.nan_to_num(q, nan=50.0) / 100, 0.0)
    return w if w.sum() > 0 else ok.astype(float)


def _hold_apostas(D, idx, i):
    """Candidatas a aposta de crescimento (Growth ou GARP, preço acima da média de 200 dias) e a força de cada uma (crescimento do lucro)."""
    n = len(idx)
    if "GRO" not in D: return np.zeros(n, bool), np.zeros(n)
    c = (D["GRO"][idx, i] | D["GARP"][idx, i]) & (np.nan_to_num(D["M2"][idx, i]) > 0) & ~np.isnan(D["C"][idx, i])
    return c, np.where(c, np.nan_to_num(D["GROS"][idx, i], nan=0.0), -np.inf)


def _aporte(D, mid, idx, j, wa, caro, sh, P, pend, cash, RG, so=None, ini=False):
    """Quanto do caixa vai para cada empresa no aporte (APORTE): até RG['conc'] empresas (valor inicial: até APORTE['min_emp']);
    so = só estas podem receber (Buy and Hold: núcleo de dividendos)."""
    n = len(idx); tv = (sh * P).sum() + pend.sum() + cash; held = (sh > 0) | (pend > 0); mc = RG.get("min_compra", 0) or 0
    alvo = (wa > 0) & ~caro & (True if so is None else so)
    if not alvo.any(): return np.zeros(n)
    q, _ = _nota(D, idx, j); qn = np.nan_to_num(q, nan=50.0)
    pr = D["PLR"][idx, j] if "PLR" in D else np.full(n, np.nan); nv, _ = _noticia(D, idx, j)
    with np.errstate(invalid="ignore", divide="ignore"):
        ok_pr = np.isfinite(pr) & (pr > 0); barata = np.where(ok_pr, np.clip(1 / np.where(ok_pr, pr, 1), .5, 2), 1.0); cara = ok_pr & (pr > CARO["pl"])
    sc = qn / 100 * barata * wa / wa[alvo].max()
    room = np.maximum(0.0, APORTE["teto"] * tv - sh * P - pend)
    boa = alvo & held & ~cara & (qn >= APORTE["nota"]) & (nv > NOTICIA["ruim"]) & (room >= mc)
    nova = alvo & ~held & (room >= mc); nh = int((held & (True if so is None else so)).sum()); kmax = RG["conc"]
    if ini: kmax = max(kmax, int(APORTE["min_emp"]))
    if nh < APORTE["min_emp"]: pass
    elif boa.any(): nova &= qn >= qn[boa].max() + APORTE["nota_nova"]
    cand = np.flatnonzero(boa | nova); al = np.zeros(n); r = cash
    for k in cand[np.argsort(-sc[cand], kind="stable")][:kmax]:
        a = min(room[k], r)
        if a >= mc: al[k] = a; r -= a
        if r < mc: break
    return al


def grupo(D, mid, idx, me, ap, rec=False, wd=None, RG=None, p1=None, ult=False, cr=None):
    """Modo Grupo (Comparar e Grupo simulação): o modelo cuida de UMA carteira com as empresas escolhidas, decide com a semana anterior.
    Ações inteiras: o dinheiro destinado a cada empresa fica numa reserva dela, rendendo CDB, até dar para comprar pelo menos 1 ação;
    se a empresa sai do alvo, a reserva volta ao caixa. ult: a 1ª semana decide com os dados dela mesma (começo hoje, numa semana nova
    depois do último dia dos dados: server._sim_hoje), como a semana seguinte faria. -> valor final, IR, compras, vendas (rec: + movimentações uma a uma e posição)."""
    idx=np.asarray(idx);n=len(idx);s,e=me[0],me[-1];mod=MOD[mid];sell=mod['vende'] and not mod.get('frac');RG=REGRAS if RG is None else RG;ban=np.zeros(n)
    sh=np.zeros(n);basis=np.zeros(n);pend=np.zeros(n);cash=float(ap[0]);age=np.zeros(n);carry=0;msales=0;mgain=0;mdq=np.zeros(n);ir=0;nb=0;ns=0
    lastp=D['C'][idx,s].copy();meset={w:j for j,w in enumerate(me)};C=D['C'];DV=D['DV'];JT=D['JT'];W=D['w']
    nm=D['tick'];motivo='previsão desfavorável' if mid in('alg1','alg3') else f"saiu do critério do método {MOD[mid]['n']}" if MOD[mid].get('sig') else 'abaixo da média de 200 dias'
    d0=getattr(me,"d0",None)  # data inicial com dia: valor inicial nela; ordens da 1ª semana só depois dela
    P0,dia0,F0,w1=_dia0(D,idx,s,d0,p1,cr) if d0 else (None,None,{},None)  # 1º dia: ordens com preço limite, nada antes do início (_dia0)
    fo=np.zeros(n,bool);r0=None;T_=len(W)  # ordens do 1º dia ainda abertas (sem cr) e o preço de referência delas
    ev=[{"d":d0 or W[s],"k":"aporte","v":round(float(ap[0]),2),"x":"valor inicial"}] if rec else None;dvt=np.zeros(n)  # proventos líquidos por empresa
    ho=mid=='hold' and HOLD['on'] and bool(RG);bet=np.zeros(n,bool)  # Buy and Hold: apostas de crescimento (HOLD)
    nc=0;skc=np.zeros(n);pc_=np.zeros(n,bool);hw=np.zeros(n);cj=ca=0.0;cx=Caixa(1)  # CDB: rendimento recebido e total aplicado no período, aplicações (Caixa: IR/IOF no resgate)  # alvos caros: semanas com todas caras; semanas que cada uma ficou sem aporte por estar cara; reserva de quem estava cara
    dc,dv=("ODc","ODv") if mid=="adapt" else ("ODI","ODI")  # Adaptativo: distância aprendida por cenário
    Oc,Ov,Ov2=Ordens(D,idx,"c",dc,_calma(mid,"c"),d0),Ordens(D,idx,"v",dv,_calma(mid,"v"),d0),Ordens(D,idx,"v",dv,None,d0)  # ordens com preço limite: compra, venda do modelo, venda ocasional (por problema: sem espera)
    olim=lambda O,i,q,px,t: (O.dia(i,q) if t[q] else W[i], (CALMA_TXT if O.conf[q] else "")+(f" · ordem com preço limite R$ {px[q]:.2f}".replace(".",",") if t[q] else ""))
    for i in range(s,e+1):
        p=P0 if i==s and P0 is not None else C[idx,i];ok=~np.isnan(p);lastp=np.where(ok,p,lastp);P=np.nan_to_num(lastp)
        fl={}  # dinheiro que entrou (+) ou saiu (−) do CDB em cada dia da semana: aplicação/resgate no dia (liquidez diária)
        def addf(d_,x):
            if x: fl[d_]=fl.get(d_,0.0)+float(x)
        if i>s:
            f=D['cdb'][i];cj+=(cash+pend.sum())*(f-1);cash*=f;pend*=f
        else: addf(d0 or W[s],ap[0])
        if i>s:
            dq=sh*np.nan_to_num(DV[idx,i]);d=dq.sum();cash+=d;mdq+=dq;ir+=(sh*JT[idx,i]).sum();dvt+=dq;addf(W[i],d)  # JCP já líquido; o retido conta no IR
            if rec:
                for q in np.flatnonzero(dq>=0.005): ev.append({"d":W[i],"k":"provento","t":nm[idx[q]],"q":int(sh[q]),"p":round(float(P[q]),2),"v":round(float(dq[q]),2),"x":tipo(D,idx[q],i)})
        gone=_saiu(D,idx,i)&(sh>0)
        if gone.any():  # saiu da bolsa: vende pelo último preço (OPA/incorporação ≈ valor pago; falência ≈ quase zero)
            v=sh*P*(1-CUSTO);g=np.where(gone,v-basis,0)
            if rec:
                for q in np.flatnonzero(gone): ev.append({"d":W[i],"k":"venda","t":nm[idx[q]],"q":int(sh[q]),"p":round(float(P[q]),2),"v":round(float(v[q]),2),"pct":round(float(g[q]/basis[q]*100),2) if basis[q]>0 else None,"x":_saiu_txt(D,idx[q])})
            cash+=(v*gone).sum();addf(W[i],(v*gone).sum());msales+=(sh*P*gone).sum();mgain+=g.sum();ns+=gone.sum()
            sh=np.where(gone,0,sh);basis=np.where(gone,0,basis)
        rel=_saiu(D,idx,i)&(pend>0)
        if rel.any(): cash+=pend[rel].sum();pend[rel]=0  # reserva de quem saiu volta ao caixa
        jd=i if ult and i==s else max(0,i-1)  # semana com os dados da decisão
        w=_gtargets(D,mid,idx,jd); age+=1; ban-=1
        if "SAI" in D: w=np.where(_saiu(D,idx,i+1),0,w);tw=w.sum();w=w/tw if tw>0 else w  # na semana do último pregão em diante: não recebe aporte
        if RG: w=_regras_w(D,mid,idx,jd+1,w,sh,pend,RG,ban)
        bet&=(sh>0)|(pend>0);rel=(w==0)&(pend>0)&~bet
        if rel.any(): cash+=pend[rel].sum();pend[rel]=0  # empresa fora do alvo: a reserva dela volta ao caixa (aposta do Buy and Hold: não)
        if CONV["on"]: fica=_conviccao(D,mid,idx,jd,w,(sh>0)|(pend>0))[2]; w=np.where((sh>0)&~fica,0,w)  # convicção baixa: o que vende, vende
        if sell and i>s:
            cand=(sh>0)&(w==0)&ok&(age>=mod['min']);mo=_perda(D,mid,idx,i,cand,sh,basis,P,ok,hw);cand&=mo!="-"  # no prejuízo: só empresa ruim
            out,px,tc=Ov(i,cand,P)  # venda com preço limite (máxima do dia) ou no fim do prazo
            v=venda_liq(sh,px);g=np.where(out,v-basis,0)
            if rec:
                for q in np.flatnonzero(out): d_,x_=olim(Ov,i,q,px,tc);ev.append({"d":d_,"k":"venda","t":nm[idx[q]],"q":int(sh[q]),"p":round(float(px[q]),2),"v":round(float(v[q]),2),"pct":round(float(g[q]/basis[q]*100),2) if basis[q]>0 else None,"x":(mo[q] or motivo)+x_})
            cash+=(v*out).sum();msales+=(sh*px*out).sum();mgain+=g.sum();ns+=out.sum()
            for q in np.flatnonzero(out): addf(olim(Ov,i,q,px,tc)[0],v[q])
            sh=np.where(out,0,sh);basis=np.where(out,0,basis)
        if RG.get('venda') and not sell and i>s:  # venda ocasional dos modelos de segurar
            mo=_venda(D,mid,idx,i,sh,basis,P,ok,age)
            if ho and bet.any():  # apostas de crescimento: realiza o lucro, stop, parou de crescer
                pm=np.where(sh>0,basis/np.where(sh>0,sh,1),0);g1=D['FM']['G1'][idx,jd] if 'FM' in D else np.full(n,np.nan);b_=bet&(sh>0)&ok
                with np.errstate(invalid='ignore'): bx=np.where(b_&(P>=(1+HOLD['lucro'])*pm),f"aposta de crescimento: realizou o lucro (+{HOLD['lucro']*100:.0f}%), dinheiro para as de dividendos",np.where(b_&(P<=(1-HOLD['stop'])*pm),f"aposta de crescimento: caiu {HOLD['stop']*100:.0f}% abaixo do preço médio",np.where(b_&(g1<0),"aposta de crescimento: o lucro parou de crescer","")))
                mo=np.where(bx!="",bx,mo)
            out,px,tc=Ov2(i,mo!="",P)
            if out.any():
                v=venda_liq(sh,px);g=np.where(out,v-basis,0)
                if rec:
                    for q in np.flatnonzero(out): d_,x_=olim(Ov2,i,q,px,tc);ev.append({"d":d_,"k":"venda","t":nm[idx[q]],"q":int(sh[q]),"p":round(float(px[q]),2),"v":round(float(v[q]),2),"pct":round(float(g[q]/basis[q]*100),2) if basis[q]>0 else None,"x":mo[q]+x_})
                cash+=(v*out).sum();msales+=(sh*px*out).sum();mgain+=g.sum();ns+=out.sum()
                for q in np.flatnonzero(out): addf(olim(Ov2,i,q,px,tc)[0],v[q])
                sh=np.where(out,0,sh);basis=np.where(out,0,basis);ban=np.where(out,VENDA["sem_recompra"],ban)
                w=np.where(out,0,w);tw=w.sum();w=w/tw if tw>0 else w  # vendida não recebe o aporte da mesma semana
                rel=out&(pend>0)
                if rel.any(): cash+=pend[rel].sum();pend[rel]=0
                if ho and (out&bet).any():  # dinheiro da aposta vendida vai já para as de dividendos
                    vb=float((v*(out&bet)).sum());bet&=~out;al=_aporte(D,mid,idx,jd,w,np.zeros(n,bool),sh,P,pend,min(vb,cash),RG,~bet)
                    pend+=al;cash-=al.sum()
        wa=_conviccao(D,mid,idx,jd,w,(sh>0)|(pend>0))[0] if CONV["on"] else w  # aporte pelo peso de convicção; venda pelo sinal (w)
        rel=(wa==0)&(pend>0)&~bet
        if rel.any(): cash+=pend[rel].sum();pend[rel]=0  # fora dos pesos de convicção: a reserva volta ao caixa
        j=meset.get(i)
        if j is not None and i>s:
            tax=max(0,mgain-carry)*IR if msales>ISENTO else 0
            carry=carry-mgain if mgain<0 else (max(0,carry-max(0,mgain)) if msales>ISENTO else carry)
            dt=float((mdq*(mdq>50000)).sum())*.10  # 10% só nos proventos de cada empresa pagadora acima de R$ 50 mil no mês
            cash-=tax+dt;ir+=tax+dt;msales=mgain=0;mdq[:]=0;addf(W[i],-(tax+dt))
            if cash<0 and pend.sum()>0:  # imposto maior que o caixa: sai das reservas
                tk=min(-cash,pend.sum());pend*=1-tk/pend.sum();cash+=tk
            wv=float(wd[j]) if wd is not None and j<len(wd) else 0.0
            if wv>0:  # retirada (Grupo simulação): caixa, depois as reservas, depois vende ações inteiras de todas na mesma proporção
                if cash<wv and pend.sum()>0: tk=min(wv-cash,pend.sum());pend*=1-tk/pend.sum();cash+=tk
                val=sh*P*(1-CUSTO);tv=val.sum()
                if cash<wv and tv>0:
                    q=np.minimum(sh,np.ceil(sh*min(1.0,(wv-cash)/tv)-1e-9));v=q*P*(1-CUSTO);f=np.where(sh>0,q/np.where(sh>0,sh,1),0);b=basis*f;g=v-b
                    if rec:
                        for k in np.flatnonzero(q>0): ev.append({"d":W[i],"k":"venda","t":nm[idx[k]],"q":int(q[k]),"p":round(float(P[k]),2),"v":round(float(v[k]),2),"pct":round(float(g[k]/b[k]*100),2) if b[k]>0 else None,"x":"para a retirada"})
                    cash+=v.sum();addf(W[i],v.sum());msales+=(q*P).sum();mgain+=g.sum();ns+=int((q>0).sum());sh=sh-q;basis=basis-b  # preço médio não muda
                wp=min(wv,max(0.0,cash));cash-=wp;addf(W[i],-wp)
                if rec and wp>=0.005: ev.append({"d":W[i],"k":"retirada","v":round(float(wp),2)})
            a=ap[j] if j<len(ap) else 0;cash+=a;addf(_seg(W[i]),a)  # aporte do mês: entra no início da semana (antes das compras dela)
            if rec and tax+dt>=0.005: ev.append({"d":W[i],"k":"imposto","v":round(float(tax+dt),2)})
            if rec and a>0: ev.append({"d":_seg(W[i]),"k":"aporte","v":round(float(a),2),"x":"aporte do mês"})
        if cash>0.005 and wa.sum()>0 and RG.get('conc'):
            if j is not None:  # aporte do mês para até RG['conc'] empresas mais abaixo da meta (compra mínima RG['min_compra']); a sobra fica no CDB
                tv=(sh*P).sum()+pend.sum()+cash;gap=np.where(wa>0,wa*tv-sh*P-pend,0)
                pr=D['PLR'][idx,jd] if 'PLR' in D and mid in CARO['modelos'] else np.full(n,np.nan)
                with np.errstate(invalid='ignore'): caro=(wa>0)&(pr>CARO['pl'])  # alvo boa mas cara agora: espera; o aporte vai para as baratas
                if caro.any() and not ((gap>0)&~caro).any():  # todas as alvo caras: espera no CDB até CARO['espera'] semanas, depois a menos cara
                    nc+=1
                    if nc>=CARO['espera']: caro=caro&(np.nan_to_num(pr,nan=0)>np.nanmin(np.where(caro,pr,np.inf)))
                else: nc=0
                skc=np.where(caro&(gap>0),skc+1,np.where(w>0,skc,0));gap=np.where(caro,0,gap)
                if ho:  # Buy and Hold: aposta de crescimento nova (uma por mês) até HOLD['aposta'] da carteira e HOLD['n_aposta'] apostas
                    tv=(sh*P).sum()+pend.sum()+cash;want=min(cash,HOLD['aposta']*tv-((sh*P+pend)*bet).sum(),HOLD['aposta']/HOLD['n_aposta']*tv)
                    if want>=RG.get('min_compra',0) and want>0 and bet.sum()<HOLD['n_aposta']:
                        c,sb=_hold_apostas(D,idx,jd);q_,_=_nota(D,idx,jd);nv_,_=_noticia(D,idx,jd);vl_=D['VL'][idx,jd] if 'VL' in D else np.full(n,np.nan)
                        c&=~((sh>0)|(pend>0))&(ban<=0)&(wa<=0)&(np.isnan(q_)|(q_>=NOTA['min_compra']))&(nv_>NOTICIA['ruim'])&(np.isnan(vl_)|(vl_>=RG.get('liq',0)))
                        if c.any(): k=int(np.argmax(np.where(c,sb,-np.inf)));pend[k]+=want;cash-=want;bet[k]=True
                al=_aporte(D,mid,idx,jd,wa,caro,sh,P,pend,cash,RG,~bet if ho else None,i==s) if APORTE['on'] and not (sell and APORTE['segurar']) else np.zeros(n)
                gap=np.where(bet,0,np.maximum(0,gap-al));c2=cash-al.sum()  # sobra (nenhuma boa com espaço): pela regra antiga, as mais abaixo da meta
                top=np.argsort(-gap,kind="stable")[:max(0,(max(RG['conc'],int(APORTE['min_emp'])) if i==s else RG['conc'])-int((al>0).sum()))];top=top[gap[top]>0]
                if len(top) and c2>=RG.get('min_compra',0) and (APORTE['sobra'] or not al.any()):
                    gs=gap[top].sum();a2=np.zeros(n);a2[top]=gap[top]*min(1.0,c2/gs);al=al+np.where(a2>=RG.get('min_compra',0),a2,0)
                if al.sum()>0: pend+=al;cash-=al.sum();pc_=np.where(al>0,skc>0,pc_);skc=np.where(al>0,0,skc)
        elif cash>0.005 and wa.sum()>0:
            pend+=cash*wa;cash=0.0
        if mid=='barsi' and j is not None and i>s: cash,pend=_barsi_caixa(D,idx,i,w,sh,P,ok,cash,pend,RG,ban)
        inf={}  # 1º dia: (dia, texto, hora) de cada compra
        if i==s and P0 is not None and w1 is None:  # criado no pregão do dia de início: as ordens que o servidor viu tocar o limite (F0) ou o fechamento
            m=ok&(P>0)&(pend*(1-CUSTO)>=P);tc=np.zeros(n,bool);px=np.array([F0[k][0] if k in F0 else P[k] for k in range(n)])
            for k in range(n): inf[k]=(F0[k][1],f" · 1º dia: ordem com preço limite R$ {F0[k][0]:.2f}".replace(".",","),F0[k][2]) if k in F0 else (dia0," · 1º dia: no fechamento (não tocou o limite)",None)
        else:
            if P0 is not None and i==s: fo=pend>0;r0=P.copy()  # sem cr: ordens a partir do fechamento do dia de início, nos pregões seguintes
            fo&=pend>0
            m,px,tc=Oc(i,ok&(P>0)&(pend*(1-CUSTO)>=P)&~fo,P);px=np.array(px,float)  # compra com preço limite: a reserva espera no CDB até a mínima do dia tocar o limite
            if fo.any() and i>=w1:
                k_=idx[fo];dd=D["ODI"][k_,max(0,s-1)];lim=r0[fo]*(1-dd);lo,hi,ol=D["LO"][k_,i],D["HI"][k_,i],D["OL"][k_,i]
                from datetime import date as _d,timedelta as _td
                dl_=[(_d.fromisoformat(W[i])-_td(days=int(o))).isoformat() if o<255 else "" for o in ol]
                toc,pxl=ord_exec(True,lim,lo,hi);toc=toc&np.array([d>dia0 for d in dl_])
                fim=i<T_-1 or _d.fromisoformat(W[i]).weekday()==4  # semana completa (a última dos dados pode estar em andamento)
                for a_,k in enumerate(np.flatnonzero(fo)):
                    if toc[a_]: px[k]=pxl[a_];inf[k]=(dl_[a_],f" · 1º dia: ordem com preço limite R$ {lim[a_]:.2f}".replace(".",","),None)
                    elif fim: px[k]=P[k];inf[k]=(W[i]," · 1º dia: no fechamento da semana (não tocou o limite)",None)
                    else: continue
                    m[k]=ok[k]&(P[k]>0)&(pend[k]*(1-CUSTO)>=px[k]);fo[k]=False
                if fim: fo[:]=False
        oc=lambda k:inf[k][:2] if k in inf else olim(Oc,i,k,px,tc)
        if m.any():
            q,c_=compra_inteira(pend,np.where(m,px,np.inf));q=np.where(m,q,0.0);m=q>=1
            if m.any():
                cost=np.where(m,c_,0.0);new=m&(sh<=0);age=np.where(new,0,age)
                if rec:
                    qn,po=_nota(D,idx,jd) if RG else (None,None)
                    for k in np.flatnonzero(m):
                        d_,x_=oc(k);e={"d":d_,"k":"compra","t":nm[idx[k]],"q":int(q[k]),"p":round(float(px[k]),2),"v":round(float(cost[k]),2)}
                        if k in inf and inf[k][2]: e["h"]=inf[k][2]
                        if RG and _desc(qn[k],po[k]): e["x"]=_desc(qn[k],po[k])
                        if pc_[k]: e["x"]=(e.get("x","")+" · estava cara, comprou depois da queda").lstrip(" ·")
                        if x_: e["x"]=(e.get("x","") + x_).lstrip(" ·")
                        ev.append(e)
                for k in np.flatnonzero(m): addf(oc(k)[0],-cost[k])
                sh+=np.where(m,q,0);basis+=cost;pend=np.maximum(0,pend-cost);nb+=m.sum();pc_=np.where(m,False,pc_)
        for d_ in sorted(fl):  # CDB dia a dia: aplica/resgata no dia; antes do fim da semana corrige o rendimento desses dias; resgate paga IR/IOF
            F=fl[d_]
            if abs(F)<0.005: continue
            ci_,dia_=_ci(D,d_)
            if d_<W[i]: cr=F*_cig(D,d_,i);cash+=cr;cj+=cr
            s0=float(cx.U[0]*ci_)  # saldo no CDB nesse dia, antes da movimentação
            if F>0:
                cx.aplica(np.array([F]),ci_,dia_);ca+=F
                if rec: _cdi(ev,d_,F,s0)
            else:
                t=float(cx.resgate(np.array([-F]),ci_,dia_)[0]);cash-=t;ir+=t
                if rec:
                    _cdi(ev,d_,F,s0)
                    if t>=0.005: ev.append({"d":d_,"k":"imposto","v":round(t,2),"x":CDB_TXT})
        cx.ajusta(cash+pend.sum(),_ci(D,W[i])[0])  # aplicações acompanham o saldo da carteira (arredondamentos, reservas)
    L=np.nan_to_num(lastp);res=cash+pend.sum();v=float((sh*L).sum()+res)
    if not rec: return v, float(ir), int(nb), int(ns)
    _por_data(ev)
    # preço médio = total pago (com custos) ÷ ações, ponderado pelas compras; vendas não mudam (como na corretora); resultado = preço de agora × preço médio
    pos=[{"t":nm[idx[q]],"q":int(sh[q]),"p":round(float(L[q]),2),"pm":round(float(basis[q]/sh[q]),2),"v":round(float(sh[q]*L[q]),2),"inv":round(float(basis[q]),2),
          "pct":round(float(sh[q]*L[q]/basis[q]*100-100),2) if basis[q]>0 else None,"dv":round(float(dvt[q]),2)} for q in np.flatnonzero(sh>0)]
    pos.sort(key=lambda x:-x["v"])
    # ordens abertas no fim (limite para a semana seguinte): o servidor confere ao vivo com a mínima/máxima de hoje (server._simw)
    oa=[]
    for O,ld in ((Oc,"c"),(Ov,"v"),(Ov2,"v")):
        for q in np.flatnonzero(~np.isnan(O.ref)):
            dd=float(D[O.dk][idx[q],me[-1]]);lim=O.ref[q]*((1-dd) if ld=="c" else (1+dd))
            if np.isfinite(lim): oa.append({"t":nm[idx[q]],"lado":ld,"lim":round(float(lim),2),"sem":int(O.sem[q]),**({"r":round(float(pend[q]),2)} if ld=="c" else {"q":int(sh[q])})})
    for q in np.flatnonzero(fo&(pend>0)):  # ordens do 1º dia ainda abertas (semana em andamento): o servidor confere ao vivo
        lim=r0[q]*(1-float(D["ODI"][idx[q],max(0,s-1)]))
        if np.isfinite(lim): oa.append({"t":nm[idx[q]],"lado":"c","lim":round(float(lim),2),"sem":0,"r":round(float(pend[q]),2),"d1":True})
    return v, float(ir), int(nb), int(ns), {"pos":pos,"cash":round(float(res),2),"cdb":{"ap":round(float(ca),2),"j":round(float(cj),2),"p":round(float(cx.P[0]),2),"d":round(float(res)*(D.get("CDI1") or 0)/100,2)},"mov":ev,"ord":oa,"dvt":{nm[idx[q]]:round(float(dvt[q]),2) for q in np.flatnonzero(dvt>=0.005)}}


def _rule(rows, m):
    """Regras das linhas extras da Previsão (previsao.js → apAt/wAt): 'm' mensal (vale do mês indicado até a próxima; 0 encerra),
    'u' única (no mês), 'p' por período (a cada n meses a partir do mês) -> (regular mensal ou None, extra do mês)."""
    reg, extra = None, 0.0
    for r in sorted(rows, key=lambda r: r["m"]):
        t = r.get("t") or "m"
        if t == "m" and r["m"] <= m: reg = r["v"]
        elif t == "u" and r["m"] == m: extra += r["v"]
        elif t == "p" and r.get("n", 0) >= 2 and m >= r["m"] and (m - r["m"]) % r["n"] == 0: extra += r["v"]
    return reg, extra


SIM_MAX = 1e12  # Grupo simulação: maior valor aceito (valor inicial, aporte, extra ou retirada); acima, ou inf/nan, é inválido


def _valor(x):
    """Valor em R$ vindo do site/app -> float entre 0 e SIM_MAX; inválido (texto, inf, nan, acima de SIM_MAX) -> None."""
    try: v = float(x or 0)
    except Exception: return None
    return max(0.0, v) if math.isfinite(v) and v <= SIM_MAX else None


def sim_def(b):
    """Definição de um Grupo simulação vinda do site/app -> (di, v0, ap mensal, extras, retiradas), validada.
    Grupos antigos (só di e v0) ficam como estavam: sem aporte mensal nem retiradas. Valor inválido (_valor): 0 (linha extra: ignorada)."""
    def rows(x):
        out = []
        for r in (x if isinstance(x, list) else [])[:60]:
            try:
                t = r.get("t") or "m"; m = int(r["m"]); v = _valor(r["v"]); n = int(r.get("n") or 0)
                if v is not None and t in ("m", "u", "p") and 1 <= m <= 1200 and r.get("ok", True) is not False: out.append({"t": t, "m": m, "v": v, "n": n})
            except Exception: continue
        return out
    b = b or {}
    ap, v0 = _valor(b.get("ap")) or 0.0, _valor(b.get("v0")) or 0.0
    import re
    di = str(b.get("di") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", di): di = di[:7]  # AAAA-MM (grupos antigos) ou AAAA-MM-DD
    return di, v0, ap, rows(b.get("ex")), rows(b.get("ret"))


def sim_flows(v0, ap, ex, ret, n):
    """Aportes e retiradas de cada mês (mês 1 = valor inicial), a mesma regra de previsao.js → flows: mês com retirada não tem aporte."""
    a1 = _rule(ex, 1)[1]; aps, wd = [v0 + a1], [0.0]
    for m in range(2, n + 1):
        wr, we = _rule(ret, m); W0 = (wr or 0.0) + we
        ar, ae = _rule(ex, m); A = (ap if ar is None else ar) + ae
        aps.append(0.0 if W0 > 0 else A); wd.append(W0)
    return aps, wd


def _simspan(D, di, v0, ap, ex, ret):
    """Semanas e fluxos do Grupo simulação: da data inicial até a última semana dos dados, incluindo as semanas do 1º mês (um grupo que
    começa no mês atual anda até hoje, não para na 1ª semana); aporte e retirada de cada mês na sua semana de fim de mês (o 1º mês só tem
    o valor inicial). -> (semanas, aportes, retiradas)."""
    me = _span(D, di, D["fim"], mesmo=True)
    mo = [D["ym"][i] for i in me]; meses = list(dict.fromkeys(mo))
    a, w = sim_flows(v0, ap, list(ex), list(ret), len(meses))
    aps, wd, vis = [], [], set()
    for x in mo:
        k = meses.index(x); um = x not in vis; vis.add(x)
        aps.append(a[k] if um else 0.0); wd.append(w[k] if um else 0.0)
    return me, aps, wd


def simgrupo(D, tickers, di, v0, ap=0.0, ex=(), ret=(), p1=None, ult=False, cr=None):
    """Grupo simulação (aba Grupos): uma carteira por modelo com as mesmas empresas e o mesmo valor inicial desde di até a última semana
    dos dados (a mesma conta de grupo(), igual ao Comparar/Previsão com data final = hoje). Recalcula do início a cada versão dos dados
    (os preços antigos são ajustados por proventos e desdobramentos) e guarda o resultado em _C."""
    v0 = max(0.0, float(v0 or 0)); me, aps, wd = _simspan(D, di, v0, ap, ex, ret)
    if not me: return {"error": _curto(D, di), "pend": len(di) > 7 and di > D["w"][-1]}
    if v0 <= 0: return {"error": "Valor inicial deve ser maior que zero."}
    p1, cr = sim_p1(p1), sim_cr(cr); key = _simkey(D, tickers, di, aps, wd, p1) + ("u" if ult else "") + (cr or "")
    hit = _cget(key)
    if hit is not None: return hit
    idx = _simidx(D, tickers, me)
    if not idx: return {"error": f"Nenhuma empresa tinha preço em {D['ym'][me[0]]}."}
    apT = sum(aps) - sum(wd)  # valor aportado: cresce com cada aporte, cai com cada retirada; rendimento sobre ele
    pc = lambda v: round((v / apT - 1) * 100, 2) if apT > 0 else None
    out = {"ini": D["ym"][me[0]], "fim": D["ym"][me[-1]], "d0": di if len(di) > 7 else D["w"][me[0]], "d1": D["w"][me[-1]], "v0": v0, "ap": ap, "apT": round(apT, 2), "aviso": AVISO,
           "apS": round(sum(aps), 2), "wS": round(sum(wd), 2), "at": D["at"], "n": len(idx), "eng": ENGINE, "cdi": D.get("CDI1"), "m": []}
    for m in MODELOS:
        v, ir, nb, ns, h = grupo(D, m["id"], idx, me, aps, rec=True, wd=wd, p1=p1, ult=ult, cr=cr)
        _mzput((key, m["id"]), h)  # todas as movimentações, comprimidas: páginas e histórico por empresa em simmov
        cu = sum((e["v"] - e["q"] * e["p"]) if e["k"] == "compra" else (e["q"] * e["p"] - e["v"]) for e in h["mov"]
                 if e.get("k") in ("compra", "venda") and e.get("q") and e.get("p"))  # custos pagos (CUSTO) em todas as compras e vendas
        out["m"].append({"m": m["id"], "n": m["n"], "v": round(v, 2), "pct": pc(v), "ir": round(ir, 2), "c": nb, "s": ns, "cu": round(max(0.0, cu), 2), "np": len(h["pos"]),
                         "cash": h["cash"], "cdb": h["cdb"], "pos": h["pos"], "mov": h["mov"][-MOV_SITE:], "nmov": len(h["mov"]), "ord": h.get("ord") or []})
    out["m"] += [{"m": r["m"], "n": MOD[r["m"]]["n"], "v": r["v"], "pct": pc(r["v"]) if r["v"] is not None else None, "ref": True} for r in _refs(D, me, aps, wd, apT)]
    out["m"].sort(key=lambda x: -(x["pct"] if x["pct"] is not None else -1e9))
    return _cput(key, out)


MOV_SITE = 50  # Grupo simulação: movimentações que vão junto com a simulação (as mais recentes); as outras vêm em páginas de simmov
_MZ = OrderedDict(); MZ_MAX = 2 * len(MODELOS)  # 2 simulações inteiras; (simulação, modelo) -> movimentações e posições em JSON comprimido (~70 KB por modelo em 20 anos)


def _simkey(D, tickers, di, aps, wd, p1=None): return _ckey("sim", ENGINE, D["at"], tuple(tickers), di, tuple(round(x, 2) for x in aps), tuple(round(x, 2) for x in wd), tuple(sorted((p1 or {}).items())))


def sim_cr(x):
    """Hora em que o grupo foi criado no próprio dia de início, no pregão ('HH:MM'; o aparelho guarda em sim.cr) ou None."""
    import re
    return str(x) if x and re.fullmatch(r"\d{2}:\d{2}", str(x)) else None


def sim_p1(x):
    """Ordens do 1º dia que o servidor viu tocar o limite, guardadas pelo aparelho {ticker: [preço, 'HH:MM', 'AAAA-MM-DD']} -> {ticker: (preço, 'HH:MM', dia)}.
    Só horários do pregão (10:00–18:30): uma "execução" vista fora dele usou a mínima/máxima de outro dia e é descartada."""
    import re
    out = {}
    for t, v in (x.items() if isinstance(x, dict) else ()):
        try:
            if re.fullmatch(r"[A-Z0-9.\-]{1,16}", str(t)) and float(v[0]) > 0 and re.fullmatch(r"\d{2}:\d{2}", str(v[1])) and "10:00" <= str(v[1]) <= "18:30" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v[2])): out[str(t)] = (round(float(v[0]), 4), str(v[1]), str(v[2]))
        except Exception: continue
        if len(out) >= 200: break
    return out


def _simidx(D, tickers, me): return [D["ix"][t] for t in dict.fromkeys(tickers) if t in D["ix"] and not np.isnan(D["C"][D["ix"][t], me[0]])]


def _mzput(k, h):
    z = zlib.compress(json.dumps(h, separators=(",", ":")).encode(), 6)
    with _clock:
        _MZ[k] = z; _MZ.move_to_end(k)
        while len(_MZ) > MZ_MAX: _MZ.popitem(last=False)
    return z


def sim_hist(D, tickers, di, v0, mid, ap=0.0, ex=(), ret=(), p1=None, cr=None):
    """Histórico completo de um modelo do Grupo simulação (movimentações das mais antigas às mais recentes, posições, proventos por
    empresa), do cache comprimido _MZ; se saiu da memória, refaz só esse modelo."""
    if mid not in MOD or mid not in {m["id"] for m in MODELOS}: return {"error": "Modelo desconhecido."}
    v0 = max(0.0, float(v0 or 0)); me, aps, wd = _simspan(D, di, v0, ap, ex, ret)
    if not me or v0 <= 0: return {"error": "Simulação inválida."}
    p1, cr = sim_p1(p1), sim_cr(cr); k = (_simkey(D, tickers, di, aps, wd, p1) + (cr or ""), mid)
    with _clock:
        z = _MZ.get(k)
        if z is not None: _MZ.move_to_end(k)
    if z is None:
        idx = _simidx(D, tickers, me)
        if not idx: return {"error": "Nenhuma empresa no período."}
        z = _mzput(k, grupo(D, mid, idx, me, aps, rec=True, wd=wd, p1=p1, cr=cr)[4])
    return json.loads(zlib.decompress(z))


def simmov(D, tickers, di, v0, mid, tk=None, off=0, n=50, ap=0.0, ex=(), ret=(), p1=None, cr=None):
    """Movimentações de um modelo do Grupo simulação (mesma conta de simgrupo), das mais recentes para as mais antigas.
    Sem tk: a página [off, off+n) e o total. Com tk: só essa empresa (todas as movimentações dela), a posição (preço médio…) e os
    proventos recebidos. Leve: guardado comprimido; se saiu da memória, refaz só esse modelo."""
    h = sim_hist(D, tickers, di, v0, mid, ap, ex, ret, p1, cr)
    if h.get("error"): return h
    ev = h["mov"][::-1]
    if tk:
        L = [x for x in ev if x.get("t") == tk]
        return {"t": tk, "pos": next((p for p in h["pos"] if p["t"] == tk), None), "dv": h.get("dvt", {}).get(tk, 0.0), "mov": L, "nmov": len(L)}
    off = max(0, int(off or 0)); n = min(200, max(1, int(n or 50)))
    return {"off": off, "mov": ev[off:off + n], "nmov": len(ev)}


def fora_barsi(D, idx, me):
    """Empresas fora do Método Barsi no período: setor não perene ou sem proventos regulares (sem preço teto em nenhum mês)."""
    T = D["TETO"][np.asarray(idx)][:, me[0]:me[-1] + 1]
    return ~D["BS"][np.asarray(idx)] | np.isnan(T).all(axis=1)


def compare(D, tickers, di, df, aps, wd=None, tx=None, grupos=None):
    """Todos os modelos em cada empresa com os mesmos aportes (aps: aporte de cada mês, mês 1 = valor inicial) e retiradas (wd).
    Comparar → Modelos e Previsão com o card Modelos em Todos (grupos: rodízio dos modelos que trocam de empresa).
    -> empresas usadas (com preço no início), lucro %, valor final, IR, compras/vendas por modelo × empresa, posições e resumos."""
    me = _span(D, di, df)
    if not me: return {"error": _curto(D, di)}
    aps = ([max(0.0, float(x or 0)) for x in aps] + [0.0] * len(me))[:len(me)]
    wd = ([max(0.0, float(x or 0)) for x in (wd or [])] + [0.0] * len(me))[:len(me)]
    key = _ckey("cmp", D["at"], tuple(tickers), di, df, aps, wd, tx, repr(grupos))
    hit = _cget(key)
    if hit is not None: return hit
    apT = sum(aps)
    idx = _simidx(D, tickers, me)
    if not idx: return {"error": f"Nenhuma das empresas tinha preço em {D['ym'][me[0]]}."}
    if not any(wd) and tx is None and grupos is None:  # casos mais comuns já calculados na rotina diária (modelos_pre)
        hit = _PRE["e"].get(pre_key(D, tickers, idx, me, aps))
        if hit is not None: return _cput(key, hit)
    R = [simulate(D, m["id"], idx, me, aps, wd, tx) for m in MODELOS]
    fora = fora_barsi(D, idx, me) if len(idx) > 1 else np.zeros(len(idx), bool)  # uma empresa só: calcula mesmo fora do método
    for r, m in zip(R, MODELOS):  # ETF: modelos que não se aplicam ficam sem valor (como o Barsi fora do método)
        po = pode(D, m["id"], idx)
        if not po.all(): r["v"] = np.where(po, r["v"], np.nan); r["ra"] = np.where(po, r["ra"], np.nan)
    ib = [m["id"] for m in MODELOS].index("barsi"); R[ib]["v"] = np.where(fora, np.nan, R[ib]["v"]); R[ib]["ra"] = np.where(fora, np.nan, R[ib]["ra"])
    refs = _refs(D, me, aps, wd, apT); z = np.zeros(len(idx))
    R += [{"v": np.full(len(idx), np.nan if r["v"] is None else r["v"]), "ra": np.full(len(idx), np.nan if r["ra"] is None else r["ra"]), "ir": z, "irv": z, "c": z, "s": z} for r in refs]
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
                "ganha": None if m["id"] == "hold" else round(float((V[i][ok] > hold[ok]).mean() * 100), 1), "pior": None if m.get("ref") else int(rk[i].max()) + 1, "pos": cnt[i].tolist(),
                "pts": int(pts[i]), "ptsm": round(float(pts[i]) / k, 2), "n": k, **({"ref": True} if m.get("ref") else {})}
    gi = {m["id"]: [k for k, o in zip(idx, pode(D, m["id"], idx)) if o] for m in MODELOS}  # ETF: só nos modelos que valem para ele
    G = [grupo(D, m["id"], gi[m["id"]], me, aps) if gi[m["id"]] else None for m in MODELOS]  # modo Grupo: uma carteira por modelo (mesmo aporte de uma empresa)
    cart = [{"m": m["id"], "v": round(g[0], 2), "pct": round((g[0] / apT - 1) * 100, 2) if apT > 0 else None, "ir": round(g[1], 2), "c": g[2], "s": g[3]}
            for m, g in zip(MODELOS, G) if g is not None] + [{"m": r["m"], "v": r["v"], "pct": r["pct"], "ir": 0.0, "c": None, "s": None, "ref": True} for r in refs]
    big = lambda i: -_nmean(P[i])  # ord_pts: pela média de pontos (o Método Barsi só conta nas empresas do método)
    out = {"ini": D["ym"][me[0]], "fim": D["ym"][me[-1]], "meses": len(me), "apT": apT, "pedidas": len(dict.fromkeys(tickers)), "aviso": AVISO,
           "t": [D["tick"][k] for k in idx], "m": [m["id"] for m in M], "p": J(P), "rk": rk.tolist(),
           "v": J(V), "ra": J(np.array([r["ra"] for r in R], dtype=float)), "ir": np.round(np.array([r["ir"] for r in R]), 2).tolist(), "irv": np.round(np.array([r["irv"] for r in R]), 2).tolist(),
           "c": np.array([r["c"] for r in R]).astype(int).tolist(), "s": np.array([r["s"] for r in R]).astype(int).tolist(),
           "res": [res(i, m) for i, m in enumerate(M)], "ord_media": sorted(range(nm), key=big), "ord_pos": order,
           "ord_pts": sorted(range(nm), key=lambda i: (-(pts[i] / max(1, (~np.isnan(V[i])).sum())), -pts[i], order.index(i))), "ref": refs, "fora": int(fora.sum()), "pontos": list(PONTOS), "cart": cart}
    if grupos is not None:  # rodízio nos grupos (Previsão com o card Modelos em Todos)
        pc = lambda v: round((v - apT) / apT * 100, 2) if apT > 0 else None
        out["g"] = []
        for m in MODELOS:
            if not m["vende"] or m.get("frac"): continue
            for g in grupos[:12]:
                gi = [D["ix"][t] for t in (g.get("t") or [])[:30] if t in D["ix"]]
                gi = [k for k, o in zip(gi, pode(D, m["id"], gi)) if o]
                if len(gi) < 2: continue
                r = rotate(D, m["id"], gi, me, aps, wd, tx)
                out["g"].append({"m": m["id"], "n": str(g.get("n") or "")[:60], "t": [D["tick"][x] for x in gi], "v": round(r["v"], 2), "pct": pc(r["v"]), "ra": None if r["ra"] != r["ra"] else round(r["ra"], 2), 
                                 "ir": round(r["ir"], 2), "irv": round(r["irv"], 2), "c": r["c"], "s": r["s"], "hist": r["hist"]})
        out["g"].sort(key=lambda x: -(x["pct"] or -1e9))
    return _cput(key, out)
