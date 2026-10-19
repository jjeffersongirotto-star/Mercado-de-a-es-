import json
"""Testes dos modelos da Previsão (modelos.py): custos, IR com isenção e prejuízo a compensar, CDB e rodízio.
Rodar: python tests/test_modelos.py"""
import os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
import modelos

NW = 120
W = [(date(2020, 1, 3) + timedelta(weeks=k)).isoformat() for k in range(NW)]  # sextas-feiras


def cdi(rate=0.0):
    d0 = date(2019, 12, 1)
    ds = [(d0 + timedelta(days=k)).isoformat() for k in range(900)]
    return {"d": ds, "v": [rate] * len(ds)}


def snap(a, mi=None):
    full = lambda v: v if isinstance(v, list) else [v] * NW
    return {"w": W, "mi": full(mi if mi is not None else 50),
            "a": {t: {"i0": 0, "c": full(x["c"]), "dv": {}, "si": full(x.get("si", 50)), "m2": full(x.get("m2", 10)),
                      "r12": full(x.get("r12", 0)), "p1": full(x.get("p1", 500)), "p3": full(x.get("p3", 500))} for t, x in a.items()}}


def months(D, di, df):
    return modelos._span(D, di, df)


def test_hold_paga_custo_de_compra():
    D = modelos.build(snap({"AAA3": {"c": 10.0}}), cdi())
    me = months(D, "2020-01", "2020-12")
    r = modelos.simulate(D, "hold", [0], me, [1000.0] + [0.0] * 11, [0.0] * 12)
    q = 99  # ações inteiras: 1000 × (1 − custo) ÷ 10 = 99,7 -> 99; a sobra fica no CDB
    assert abs(r["v"][0] - (q * 10 + 1000 - q * 10 / (1 - modelos.CUSTO))) < 1e-6 and r["c"][0] == 1 and r["s"][0] == 0


def test_ir_isencao_ate_20_mil():
    c = [10.0] * 5 + [20.0] * (NW - 5); m2 = [10] * 10 + [-10] * (NW - 10)  # dobra de preço; perde a média na semana 10
    D = modelos.build(snap({"AAA3": {"c": c, "m2": m2}}), cdi())
    me = months(D, "2020-01", "2020-06")
    for ini, isento in ((10000.0, True), (15000.0, False)):
        r = modelos.simulate(D, "tendencia", [0], me, [ini] + [0.0] * (len(me) - 1), [0.0] * len(me))
        q = int(ini * (1 - modelos.CUSTO) / 10); custo = q * 10 / (1 - modelos.CUSTO); sobra = ini - custo
        venda = q * 20 * (1 - modelos.CUSTO)
        ir = 0 if isento or q * 20 <= modelos.ISENTO else (venda - custo) * modelos.IR
        assert r["s"][0] == 1 and abs(r["ir"][0] - ir) < 1e-6 and abs(r["v"][0] - (venda + sobra - ir)) < 1e-6, (ini, r)


def test_prejuizo_compensa_lucro_seguinte():
    A = modelos.Conta(1); A.cash += 30000
    one, p = np.array([True]), lambda x: np.array([x])
    A.buy(one, p(10)); perda = -A.sell(one, p(8))[0]; A.close_month(p(8), p(0), p(0), None)
    assert A.ir[0] == 0 and perda > 0 and abs(A.carry[0] - perda) < 1e-6 and A.sh[0] == 0
    base = A.cash[0]; A.buy(one, p(8)); A.sell(one, p(12)); ganho = A.mgain[0]
    A.close_month(p(12), p(0), p(0), None)
    assert abs(A.ir[0] - (ganho - perda) * modelos.IR) < 1e-6 and A.carry[0] == 0 and base > 0


def test_dinheiro_parado_rende_cdb():
    D = modelos.build(snap({"AAA3": {"c": 10.0}}, mi=90), cdi(0.1))  # mercado em ganância: o modelo de medo nunca aplica
    me = months(D, "2020-02", "2020-12")
    r = modelos.simulate(D, "medo_mercado", [0], me, [1000.0] + [0.0] * (len(me) - 1), [0.0] * len(me))
    dias = (date.fromisoformat(W[me[-1]]) - date.fromisoformat(W[me[0]])).days
    assert r["c"][0] == 0 and abs(r["v"][0] - 1000 * 1.001 ** dias) < 1e-6


def test_rodizio_troca_com_motivo_e_vai_para_cdb():
    pa = [500] * 35 + [600] * 45 + [400] * (NW - 80); pb = [500] * 60 + [700] * 20 + [400] * (NW - 80)  # só entra com chance bem acima da mediana
    D = modelos.build(snap({"AAA3": {"c": 10.0, "p1": pa}, "BBB3": {"c": 10.0, "p1": pb}}), cdi())
    me = months(D, "2020-09", "2022-03")
    r = modelos.rotate(D, "alg1", [0, 1], me, [1000.0] + [0.0] * (len(me) - 1), [0.0] * len(me))
    m = [x for x in r["hist"]["mov"] if x["k"] in ("compra", "venda")]
    mv = [(x["k"], x["t"]) for x in m]
    # melhor chance, troca por margem (vende e compra a outra na mesma semana), todas desfavoráveis
    assert mv[:4] == [("compra", "AAA3"), ("venda", "AAA3"), ("compra", "BBB3"), ("venda", "BBB3")], mv
    # (depois de meses em 400, a mediana do último ano também vira 400 e a empresa volta a ser favorável)
    assert m[1]["d"] == W[61] == m[2]["d"] and "BBB3 com sinal melhor" in m[1]["x"] and "chance" in m[2]["x"]
    assert all(x["v"] > 0 and isinstance(x["q"], int) and x["q"] >= 1 and x["p"] > 0 for x in m) and m[1]["pct"] is not None
    assert m[0]["q"] == 99 and r["hist"]["mov"][0] == {"d": W[me[0]], "k": "aporte", "v": 1000.0, "x": "valor inicial"}
    assert r["hist"]["trocas"] == 1 and r["hist"]["cdb"] > 0 and {x["t"] for x in r["hist"]["emp"]} == {"AAA3", "BBB3"}


def test_hibrido_nunca_vende_e_segue_quem_acerta():
    c = [10.0 * 1.01 ** k for k in range(NW)]  # ação subindo sempre: o especialista "comprar e segurar" ganha peso
    D = modelos.build(snap({"AAA3": {"c": c, "p1": 400, "p3": 400, "m2": -10}}), cdi(0.01))
    assert D["HX"][0, 60] == 1 and D["HW"][:, 0, 60].argmax() == 0  # 100% na ação, seguindo Comprar e segurar
    me = months(D, "2020-09", "2021-12")
    r = modelos.simulate(D, "hibrido", [0], me, [1000.0] + [100.0] * (len(me) - 1), [0.0] * len(me), rec=True)
    assert r["s"][0] == 0 and r["ir"][0] == 0 and "Comprar e segurar" in r["rows"][0][-1]["pos"]


def test_colocacoes_desempate_pelo_segundo_lugar():
    # 3 modelos × 4 empresas: A e B têm dois 1º lugares cada; B tem mais 2º lugares -> B antes de A
    V = np.array([[10, 10, 1, 1], [9, 9, 11, 11], [1, 1, 10, 10]], dtype=float)  # B: 1º nas duas últimas, 2º nas duas primeiras
    rk, cnt, order, pts = modelos.ranking(V)
    assert cnt[0].tolist() == [2, 0, 2] and cnt[1].tolist() == [2, 2, 0] and order == [1, 0, 2]
    assert pts.tolist() == [21 + 21 + 15 + 15, 18 + 18 + 21 + 21, 15 + 15 + 18 + 18]  # 1º = 21, 2º = 18, 3º = 15
    # referência (última linha) com o maior rendimento: 1º nas colocações, mas nos Pontos fica com a última colocação
    V2 = np.vstack([V, np.full(4, 99.0)]); rk2, cnt2, _, pts2 = modelos.ranking(V2, 1)
    assert cnt2[3].tolist() == [4, 0, 0, 0] and pts2[3] == 4 * 12 and pts2[:3].tolist() == pts.tolist()
    # nan = fora (Método Barsi fora do método): não pontua nem conta colocação
    V3 = V.copy(); V3[0, 0] = np.nan; rk3, cnt3, _, pts3 = modelos.ranking(V3)
    assert rk3[0, 0] == -1 and cnt3[0].sum() == 3 and pts3[1] == 21 + 18 + 21 + 21


def test_comparar_media_e_empresas_sem_preco():
    D = modelos.build(snap({"AAA3": {"c": [10.0 + k * .1 for k in range(NW)]}, "BBB3": {"c": 10.0}}), cdi())
    out = modelos.compare(D, ["AAA3", "BBB3", "XXX3"], "2020-09", "2021-12", [1000.0] + [100.0] * 15, grupos=[{"n": "G", "t": ["AAA3", "BBB3"]}])
    nm = len(modelos.MODELOS) + len(modelos.REF); fo = out["fora"]  # Barsi fora do método (sem setor perene) nas 2 empresas
    assert len(out["v"]) == nm and len(out["v"][0]) == 2 and fo == 2 and out["p"][out["m"].index("barsi")] == [None, None]
    assert sum(r["pts"] for r in out["res"]) == 2 * sum((modelos.PONTOS + (0,) * nm)[:nm - 4])  # sem Barsi (fora), Ouro, Ibovespa e IDIV (sem cotação no teste)
    assert {g["m"] for g in out["g"]} == {"alg1", "alg3", "tendencia"}
    assert out["t"] == ["AAA3", "BBB3"] and out["pedidas"] == 3 and len(out["p"]) == nm
    i = out["m"].index("hold"); assert abs(out["res"][i]["media"] - sum(out["p"][i]) / 2) < 0.01
    md = [out["res"][k]["media"] for k in out["ord_media"] if out["res"][k]["media"] is not None]
    assert md == sorted(md, reverse=True) and out["res"][out["m"].index("cdb")]["ref"]


def test_lucro_no_balanco_bloqueia_so_algoritmo_3_meses_e_tendencia():
    sn = snap({"AAA3": {"c": 10.0, "m2": 10, "p1": 600, "p3": 600}})
    sn["a"]["AAA3"]["lp"] = [0] * NW  # prejuízo no último balanço em todas as semanas
    D = modelos.build(sn, cdi())
    me = months(D, "2020-09", "2021-06"); ap = [1000.0] + [0.0] * (len(me) - 1); w = [0.0] * len(me)
    c = {m: modelos.simulate(D, m, [0], me, ap, w)["c"][0] for m in ("alg1", "alg3", "tendencia", "media200")}
    assert c["alg3"] == 0 and c["tendencia"] == 0 and c["alg1"] == 1 and c["media200"] == 1, c


def test_run_todos_ordena_grupos_primeiro():
    D = modelos.build(snap({"AAA3": {"c": [10.0 + k * .1 for k in range(NW)]}, "BBB3": {"c": 10.0}}), cdi())
    out = modelos.run(D, {"di": "2020-09", "df": "2021-12", "ap": [1000] + [100] * 15, "ticker": "*", "modelo": "*", "universo": ["AAA3", "BBB3"],
                          "grupos": [{"n": "G", "t": ["AAA3", "BBB3"]}]})
    ks = [x["k"] for x in out["rows"]]
    # grupos primeiro (um rodízio por modelo que troca de empresa); depois modelos e CDB/Ouro juntos, pelo rendimento
    assert ks[:3] == ["g"] * 3 and ks.count("g") == 3 and ks.count("r") == len(modelos.REF)
    emp = [x for x in out["rows"] if x["k"] != "g" and x["pct"] is not None]
    assert all(a["pct"] >= b["pct"] for a, b in zip(emp, emp[1:]))
    assert len([x for x in out["rows"] if x["k"] == "a"]) == 2 * (len(modelos.MODELOS) - 1)  # Barsi: as 2 estão fora do método


def test_referencias_cdb_e_ouro():
    gold = {"d": [w for w in W], "v": [100.0 * 1.01 ** k for k in range(NW)]}  # ouro sobe 1% por semana
    idiv = {"d": [w for w in W], "v": [1000.0 * 1.02 ** k for k in range(NW)]}  # IDIV sobe 2% por semana
    D = modelos.build(snap({"AAA3": {"c": 10.0}}), cdi(0.01), gold, idiv=idiv)
    me = months(D, "2020-02", "2020-12"); ap = [1000.0] + [100.0] * (len(me) - 1); w = [0.0] * len(me)
    c = modelos.simulate_ref(D, "cdb", me, ap, w, rec=True)
    v = 0.0  # CDB: aporte no fim de cada mês, rende o CDI entre as semanas
    for i in range(me[0], me[-1] + 1):
        if i > me[0]: v *= D["cdb"][i]
        if i in me: v += ap[me.index(i)]
    assert abs(c["v"] - v) < 1e-6 and len(c["rows"]) == len(me) and c["rows"][-1]["tax"] == 0
    o = modelos.simulate_ref(D, "ouro", me, ap, w)
    q = sum(a * (1 - modelos.CUSTO) / gold["v"][i] for a, i in zip(ap, me))
    assert abs(o["v"] - q * gold["v"][me[-1]]) < 1e-6
    iv = modelos.simulate_ref(D, "idiv", me, ap, w)
    q = sum(a * (1 - modelos.CUSTO) / idiv["v"][i] for a, i in zip(ap, me))
    assert abs(iv["v"] - q * idiv["v"][me[-1]]) < 1e-6
    out = modelos.compare(D, ["AAA3"], "2020-02", "2020-12", ap)
    R = ["cdb", "ouro", "ibov", "idiv"]
    assert [r["m"] for r in out["ref"]] == R and out["m"][-4:] == R and modelos.MOD["cdb"]["n"] == "CDB"
    pts = {out["m"][i]: out["res"][i]["pts"] for i in range(len(out["m"]))}
    assert sorted(pts.values())[:4] == sorted(pts[m] for m in R)  # nos Pontos, sempre as últimas colocações
    t = modelos.run(D, {"di": "2020-02", "df": "2020-12", "ap": ap, "tab": {"t": "", "m": "ouro"}})["tab"]
    assert abs(t[-1]["com"] - o["v"]) < 1e-6
    sem = modelos.simulate_ref(modelos.build(snap({"AAA3": {"c": 10.0}}), cdi()), "ouro", me, ap, w)
    assert sem["v"] != sem["v"]  # sem ouro: sem dado


def test_metodo_barsi():
    # 7 anos semanais; proventos de R$ 0,60 por ano -> teto = média 0,60 ÷ 6% = R$ 10,00 a partir do 5º ano completo
    Wl = [(date(2015, 1, 2) + timedelta(weeks=k)).isoformat() for k in range(52 * 7 + 10)]; n = len(Wl)
    dv = {str(k): 0.6 for k in range(n) if k % 52 == 26}
    mk = lambda c: {"w": Wl, "mi": [50] * n, "a": {"AAA3": {"i0": 0, "c": [c] * n, "dv": dv, "si": [50] * n, "m2": [10] * n, "r12": [0] * n, "p1": [500] * n, "p3": [500] * n}}}
    d0 = date(2014, 12, 1); cd = {"d": [(d0 + timedelta(days=k)).isoformat() for k in range(n * 7 + 40)], "v": [0.0] * (n * 7 + 40)}
    for preco, compra in ((10.0, True), (9.0, True), (10.5, False)):  # compra só no teto (R$ 10) ou abaixo; acima espera no CDB
        D = modelos.build(mk(preco), cd)
        modelos.set_setores(D, [{"ticker": "AAA3", "subsetor": "Bancos"}])
        me = modelos._span(D, "2020-06", "2021-12"); ap = [1000.0] + [100.0] * (len(me) - 1)
        r = modelos.simulate(D, "barsi", [0], me, ap, [0.0] * len(me), rec=True)
        assert r["s"][0] == 0 and (r["rows"][0][-1]["pos"] == ("Ação" if compra else "CDB")), (preco, r["rows"][0][-1])
        assert not modelos.fora_barsi(D, [0], me)[0]
    D = modelos.build(mk(8.0), cd); modelos.set_setores(D, [{"ticker": "AAA3", "subsetor": "Varejo"}])
    assert modelos.fora_barsi(D, [0], modelos._span(D, "2020-06", "2021-12"))[0]  # setor não perene: fora do método
    assert modelos.perene({"ticker": "UNIP6", "subsetor": None, "setor": "Process Industries"}, {"UNIP": ["UNIPAR", "Químicos Diversos"]})


def test_modo_grupo():
    D = modelos.build(snap({"AAA3": {"c": 10.0}, "BBB3": {"c": 20.0}}), cdi())
    me = months(D, "2020-02", "2020-12"); ap = [1000.0] + [100.0] * (len(me) - 1)
    v, ir, nb, ns = modelos.grupo(D, "hold", [0, 1], me, ap, RG={})  # sem as regras de carteira
    # divide cada aporte entre as duas (reserva de cada uma até dar 1 ação inteira); preço parado: só o custo das compras
    assert sum(ap) * (1 - modelos.CUSTO) - 1e-6 <= v <= sum(ap) and ns == 0 and nb >= len(me)
    v2 = modelos.grupo(D, "hold", [0, 1], me, ap)[0]  # com as regras (REGRAS): o Comparar usa as mesmas
    out = modelos.compare(D, ["AAA3", "BBB3"], "2020-02", "2020-12", ap)
    c = {x["m"]: x for x in out["cart"]}; assert abs(c["hold"]["v"] - v2) < 0.01 and c["cdb"].get("ref")



def test_pre_calculado():
    """Resposta pronta (modelos_pre) só vale quando a entrada inteira bate; resultado igual ao cálculo ao vivo."""
    D = modelos.build(snap({"AAA3": {"c": 10.0}, "BBB3": {"c": 20.0}}), cdi())
    me = months(D, "2020-02", "2020-12"); ap = [1000.0] + [100.0] * (len(me) - 1)
    modelos._C.clear(); modelos.set_pre(None); live = modelos.compare(D, ["AAA3", "BBB3"], "2020-02", "2020-12", ap)
    k = modelos.pre_key(D, ["AAA3", "BBB3"], [0, 1], me, ap)
    modelos._C.clear(); modelos.set_pre({"fetched_at": "x", "e": {k: json.loads(json.dumps(live))}})
    assert modelos.compare(D, ["AAA3", "BBB3"], "2020-02", "2020-12", ap) == json.loads(json.dumps(live))
    modelos._C.clear(); modelos.set_pre({"fetched_at": "y", "e": {k: {"pre": 1}}})
    assert modelos.compare(D, ["AAA3", "BBB3"], "2020-02", "2020-12", ap) == {"pre": 1}
    modelos._C.clear(); assert "pre" not in modelos.compare(D, ["AAA3", "BBB3"], "2020-02", "2020-12", [999.0] + ap[1:])  # outro aporte: ao vivo
    modelos._C.clear(); assert "pre" not in modelos.compare(D, ["BBB3", "AAA3"], "2020-02", "2020-12", ap)  # outra lista: ao vivo
    modelos.set_pre(None); modelos._C.clear()



def test_tir_anual():
    VM = np.array([1000.0 * 1.1 ** (k / 12) for k in range(25)])  # 10% ao ano, sem aportes
    assert abs(modelos.anual(VM, [1000.0], [])[0] - 10) < 1e-6
    r = 1.1 ** (1 / 12) - 1; ap = [1000.0] + [100.0] * 24; v = 0.0; VM2 = []  # aportes mensais rendendo 10% ao ano: TIR = 10% exato
    for a in ap: v = v * (1 + r) + a; VM2.append(v)
    assert abs(modelos.anual(np.array(VM2), ap, [])[0] - 10) < 1e-6
    assert np.isnan(modelos.anual(VM[:12], ap, [])[0])  # menos de 12 meses: sem valor

def _sim_snap(nw):
    """3 empresas com preços e sinais que mudam (compra, venda e reforço), nw semanas."""
    import math
    a = {}
    for k, t in enumerate(["AAA3", "BBB3", "CCC3"]):
        c = [10.0 * (k + 1) * (1 + .1 * math.sin(i / (5 + k))) for i in range(NW)][:nw]
        p1 = [400 + 300 * math.sin(i / (3 + k)) for i in range(NW)][:nw]
        m2 = [10 * math.sin(i / (7 + k)) for i in range(NW)][:nw]
        a[t] = {"i0": 0, "c": c, "dv": {"10": .5, "60": .5}, "si": [50] * nw, "m2": m2, "r12": [0] * nw, "p1": p1, "p3": p1}
    return {"w": W[:nw], "mi": [50] * nw, "a": a}


def test_grupo_simulacao():
    """Grupo simulação = Modo Grupo do Comparar com data final = hoje; rec não muda a conta; um dia/semana a mais só acrescenta."""
    D = modelos.build(_sim_snap(NW), cdi(0.03)); tk = D["tick"]; modelos._C.clear()
    r = modelos.simgrupo(D, tk, "2020-02", 10000)
    cmp = modelos.compare(D, tk, "2020-02", D["fim"], [10000.0] + [0.0] * 600)
    cart = {x["m"]: x for x in cmp["cart"]}
    for x in r["m"]:
        assert (x["v"] is None and cart[x["m"]]["v"] is None) or abs(x["v"] - cart[x["m"]]["v"]) < 0.01, x["m"]
        if not x.get("ref"): assert x["c"] == cart[x["m"]]["c"] and x["s"] == cart[x["m"]]["s"]
    me = modelos._span(D, "2020-02", D["fim"]); ap = [10000.0] + [0.0] * (len(me) - 1)
    for m in modelos.MODELOS:
        a, b = modelos.grupo(D, m["id"], [0, 1, 2], me, ap), modelos.grupo(D, m["id"], [0, 1, 2], me, ap, rec=True)
        assert a == b[:4]
        h = b[4]; assert abs(sum(p["v"] for p in h["pos"]) + h["cash"] - b[0]) < 0.05
        assert sum(1 for x in h["mov"] if x["k"] == "venda") == b[3] and sum(1 for x in h["mov"] if x["k"] == "compra") == b[2]
        assert all(float(p["q"]).is_integer() for p in h["pos"]) and not any(x["k"] == "reforço" for x in h["mov"])
        sem = {}  # CDI: no máximo uma linha por semana
        for x in h["mov"]:
            if x["k"] in ("cdi_ap", "cdi_res"): sem[x["d"]] = sem.get(x["d"], 0) + 1
        assert all(c == 1 for c in sem.values())
    al = {x["m"]: x for x in r["m"]}["alg1"]; assert any(x["k"] == "venda" for x in al["mov"]) and all({"d", "t", "q", "p", "v"} <= set(x) for x in al["mov"] if x["k"] in ("compra", "venda"))
    # dia seguinte (uma semana nova nos dados): as movimentações de ontem continuam iguais, só entram as novas (igual a recalcular)
    for nw in (NW - 7, NW - 3):
        D0, D1 = modelos.build(_sim_snap(nw), cdi(0.03)), modelos.build(_sim_snap(nw + 1), cdi(0.03))
        modelos._C.clear(); modelos._MZ.clear()
        for m in modelos.MODELOS:
            def full(DD):  # todas as movimentações, em páginas
                L, off = [], 0
                while True:
                    p = modelos.simmov(DD, tk, "2020-02", 10000, m["id"], off=off, n=200); L += p["mov"]; off += 200
                    if off >= p["nmov"]: return L[::-1]
            trade = lambda L: [x for x in L if x["k"] in ("compra", "venda")]
            t0, t1 = trade(full(D0)), trade(full(D1))
            assert t1[:len(t0)] == t0, m["id"]
    assert "error" in modelos.simgrupo(D, tk, "2020-02", 0)
    modelos._C.clear()


def test_acoes_inteiras_reserva_e_jcp():
    """Ação de R$ 300 com aportes de R$ 100: a reserva rende CDB e compra 1 ação inteira quando dá; JCP cai líquido de 15%."""
    sn = snap({"AAA3": {"c": 300.0}, "BBB3": {"c": 10.0}})
    sn["a"]["BBB3"]["dv"] = {"40": 1.0}; sn["a"]["BBB3"]["jc"] = {"40": 1.0}; sn["a"]["BBB3"]["tp"] = {"40": "J"}
    D = modelos.build(sn, cdi(0.01))
    me = months(D, "2020-02", "2020-12"); ap = [100.0] * len(me); w = [0.0] * len(me)
    r = modelos.simulate(D, "hold", [0], me, ap, w)
    assert r["c"][0] == len(me) // 3 and r["v"][0] > sum(ap) * .99  # 1 ação a cada 3 aportes de 100 (300 × 1,003 = 300,90; a sobra rende CDB)
    v, ir, nb, ns, h = modelos.grupo(D, "hold", [0, 1], me, ap, rec=True)
    assert all(isinstance(p["q"], int) for p in h["pos"]) and abs(sum(p["v"] for p in h["pos"]) + h["cash"] - v) < 0.05
    pv = [x for x in h["mov"] if x["k"] == "provento"]
    q = next(x["q"] for x in h["mov"] if x["k"] == "compra" and x["t"] == "BBB3" and x["d"] <= W[40])
    assert pv and pv[0]["t"] == "BBB3" and "JCP" in pv[0]["x"] and abs(D["DV"][1, 40] - .85) < 1e-9 and ir > 0
    assert {x["k"] for x in h["mov"]} >= {"aporte", "compra", "provento", "cdi_ap"} and q >= 1


def test_simmov_paginas_empresa_e_preco_medio():
    """Movimentações em páginas = todas (nenhuma escondida); por empresa: só as dela, preço médio e proventos recebidos batem com elas."""
    D = modelos.build(_sim_snap(NW), cdi(0.03)); tk = D["tick"]; modelos._C.clear(); modelos._MZ.clear()
    r = modelos.simgrupo(D, tk, "2016-02", 10000)
    me = modelos._span(D, "2016-02", D["fim"]); ap = [10000.0] + [0.0] * (len(me) - 1)
    for x in r["m"]:
        if x.get("ref"): continue
        h = modelos.grupo(D, x["m"], [0, 1, 2], me, ap, rec=True)[4]
        assert x["nmov"] == len(h["mov"]) and x["mov"] == h["mov"][-modelos.MOV_SITE:] and len(x["pos"]) == x["np"]
        pg, off = [], 0
        while True:
            p = modelos.simmov(D, tk, "2016-02", 10000, x["m"], off=off, n=7); pg += p["mov"]; off += 7  # páginas pequenas: várias por modelo
            assert p["nmov"] == len(h["mov"])
            if off >= p["nmov"]: break
        assert pg == h["mov"][::-1], x["m"]  # todas, das mais recentes à primeira (aporte inicial)
        modelos._MZ.clear()  # fora da memória: refaz só o modelo e dá o mesmo
        assert modelos.simmov(D, tk, "2016-02", 10000, x["m"], off=7, n=7)["mov"] == pg[7:14]
        for t in tk:
            e = modelos.simmov(D, tk, "2016-02", 10000, x["m"], tk=t)
            assert all(y["t"] == t for y in e["mov"]) and e["nmov"] == sum(1 for y in h["mov"] if y.get("t") == t)
            assert abs(e["dv"] - sum(y["v"] for y in e["mov"] if y["k"] == "provento")) < 0.05
            assert all(y["p"] > 0 and y["q"] > 0 for y in e["mov"] if y["k"] == "provento")
            cost = q = 0
            for y in e["mov"][::-1]:  # preço médio: compras ponderadas com custos; venda (total) zera
                if y["k"] == "compra": cost += y["v"]; q += y["q"]
                elif y["k"] == "venda": cost = q = 0
            if e["pos"]: assert e["pos"]["q"] == q and abs(e["pos"]["pm"] - cost / q) < 0.01 and abs(e["pos"]["pct"] - (e["pos"]["p"] / (cost / q) - 1) * 100) < 0.1
            else: assert q == 0
    assert "error" in modelos.simmov(D, tk, "2016-02", 10000, "ibov")
    modelos._C.clear(); modelos._MZ.clear()


def test_grupo_simulacao_aportes_e_retiradas():
    """Grupo simulação com as entradas da Previsão: aporte mensal, extras e retiradas -> valor aportado, linhas no histórico, % sobre o aportado."""
    aps, wd = modelos.sim_flows(12000, 500, [{"t": "u", "m": 3, "v": 1000, "n": 0}, {"t": "m", "m": 7, "v": 0, "n": 0}], [{"t": "u", "m": 5, "v": 2000, "n": 0}], 8)
    assert aps == [12000, 500, 1500, 500, 0, 500, 0, 0] and wd == [0, 0, 0, 0, 2000, 0, 0, 0]  # mês com retirada não aporta; mensal 0 encerra
    assert modelos.sim_def({"di": "2020-02", "v0": "12000", "ap": 500, "ex": [{"t": "x", "m": 1, "v": 1}, {"m": 2, "v": 5, "ok": False}], "ret": "lixo"}) == ("2020-02", 12000.0, 500.0, [], [])
    D = modelos.build(_sim_snap(NW), cdi(0.03)); tk = D["tick"]; modelos._C.clear(); modelos._MZ.clear()
    r0 = modelos.simgrupo(D, tk, "2020-02", 12000)
    r = modelos.simgrupo(D, tk, "2020-02", 12000, 500, [], [{"t": "u", "m": 10, "v": 3000, "n": 0}])
    me = modelos._span(D, "2020-02", D["fim"]); a, w = modelos.sim_flows(12000, 500, [], [{"t": "u", "m": 10, "v": 3000, "n": 0}], len(me))
    assert r["apT"] == round(sum(a) - sum(w), 2) and r["apT"] > r0["apT"] == 12000 and r0["m"][0]["v"] != r["m"][0]["v"]
    for x in r["m"]:
        if x.get("ref") or x["v"] is None: continue
        assert abs(x["pct"] - (x["v"] / r["apT"] - 1) * 100) < 0.01
        h = modelos.grupo(D, x["m"], [0, 1, 2], me, a, rec=True, wd=w)[4]
        assert sum(1 for e in h["mov"] if e["k"] == "aporte") == sum(1 for v in a if v > 0)
        rt = [e for e in h["mov"] if e["k"] == "retirada"]; assert len(rt) == 1 and abs(rt[0]["v"] - 3000) < 0.01, x["m"]
        assert abs(sum(p["v"] for p in h["pos"]) + h["cash"] - x["v"]) < 0.05
        assert all(abs(p["pm"] * p["q"] - p["inv"]) < 0.02 * p["q"] + 0.01 for p in h["pos"])
    modelos._C.clear(); modelos._MZ.clear()


def test_regras_de_carteira():
    # 40 empresas iguais: no máximo 30 na carteira; aporte do mês em até 3; sem volume mínimo não compra
    a = {f"A{k:02d}3": {"c": 10.0} for k in range(40)}
    D = modelos.build(snap(a), cdi()); me = months(D, "2020-02", "2021-06"); ap = [30000.0] + [3000.0] * (len(me) - 1)
    v, ir, nb, ns, h = modelos.grupo(D, "hold", list(range(40)), me, ap, rec=True)
    assert len(h["pos"]) <= 30
    comp = [e for e in h["mov"] if e["k"] == "compra"]; por_mes = {}
    for e in comp: por_mes.setdefault(e["d"][:7], set()).add(e["t"])
    assert max(len(x) for k, x in por_mes.items() if k > "2020-02") <= 3  # depois do 1º mês, cada aporte vai para até 3
    D["VL"][:] = 500e3; D["VL"][5] = 2e6  # só A053 tem R$ 1 mi por dia
    h = modelos.grupo(D, "hold", list(range(40)), me, ap, rec=True)[4]
    assert {x["t"] for x in h["pos"]} == {"A053"}


def test_venda_ocasional_olha_tamanho_setor_e_historico():
    anos = list(range(2008, 2020))
    def fund(hist):  # lucro (hist) até 2017, prejuízo grande em 2018 e 2019 (40 sobre patrimônio de 100)
        return {"y": anos, "ni": hist + [-20.0, -20.0], "eq": [100.0] * 10 + [80.0, 60.0], "rev": [1.0] * 12}
    for hist, vende in (([5.0] * 10, False), ([5.0, -1.0] * 5, True)):  # histórico forte (lucro em 10 de 10 anos) segura; fraco vende
        D = modelos.build(snap({"AAA3": {"c": 10.0}}), cdi(), fund={"AAA3": fund(hist)})
        me = months(D, "2020-02", "2021-12"); ap = [1000.0] + [0.0] * (len(me) - 1)
        h = modelos.grupo(D, "hold", [0], me, ap, rec=True)[4]
        vs = [e for e in h["mov"] if e["k"] == "venda"]
        assert bool(vs) == vende and all(e["d"] >= "2021-02" for e in vs), (hist, vs)  # só depois de 1 ano com a ação
        if vende:
            assert "prejuízo grande" in vs[0]["x"] and "nota" in vs[0]["x"]
            assert not [e for e in h["mov"] if e["k"] == "compra" and e["d"] >= vs[0]["d"]]  # sem recompra depois da venda
    # só prejuízos: nota 0, nem entra na carteira
    D = modelos.build(snap({"AAA3": {"c": 10.0}}), cdi(), fund={"AAA3": fund([-1.0] * 10)})
    me = months(D, "2020-02", "2021-12")
    assert D["FM"]["Q"][0, -1] < modelos.NOTA["min_compra"]
    assert not [e for e in modelos.grupo(D, "hold", [0], me, [1000.0] + [0.0] * (len(me) - 1), rec=True)[4]["mov"] if e["k"] == "compra"]


def test_nota_de_qualidade_e_porte():
    anos = list(range(2008, 2020)); N = 12
    fund = {f"A{k:02d}3": {"y": anos, "ni": [float(k + 1)] * 12, "eq": [100.0] * 12, "rev": [10.0 * (k + 1)] * 12} for k in range(N)}
    D = modelos.build(snap({t: {"c": 10.0} for t in fund}), cdi(), fund=fund)
    Q, PO = D["FM"]["Q"][:, -1], D["FM"]["PORTE"][:, -1]
    assert PO[-1] == 3 and PO[0] == 0 and Q[-1] > Q[0], (Q, PO)  # maior receita = gigante, nota maior (porte e ROE)
    me = months(D, "2020-02", "2020-06")
    h = modelos.grupo(D, "hold", list(range(N)), me, [1000.0] + [0.0] * (len(me) - 1), rec=True)[4]
    assert all("nota" in e.get("x", "") for e in h["mov"] if e["k"] == "compra")


def test_divida_na_nota_e_na_venda():
    anos = list(range(2008, 2020))
    def fund(dl, eb):  # lucro constante; dívida líquida e EBITDA de cada ano
        return {"y": anos, "ni": [5.0] * 12, "eq": [100.0] * 12, "rev": [50.0] * 12, "dl": dl, "eb": eb}
    D = modelos.build(snap({"AAA3": {"c": 10.0}, "BBB3": {"c": 10.0}, "CCC3": {"c": 10.0}}), cdi(),
                      fund={"AAA3": fund([-10.0] * 12, [20.0] * 12), "BBB3": fund([40.0] * 11 + [200.0], [20.0] * 12),
                            "CCC3": {"y": anos, "ni": [5.0] * 12, "eq": [100.0] * 12, "rev": [50.0] * 12}})
    Q = D["FM"]["Q"][:, -1]; lim = modelos.valor_justo.FAIR["al_dlebitda"]
    assert Q[0] > Q[1], Q  # caixa líquido vale mais que dívida de 2× (2018) e 10× (2019)
    assert D["FM"]["DIV"][1, -1] and D["FM"]["DLX"][1, -1] > lim and not D["FM"]["DIV"][0, -1]
    assert not D["FM"]["DIV"][2].any()  # sem dívida no fund (banco/seguradora): parte de fora
    i = D["w"].index(next(w for w in D["w"] if w >= "2020-06"))
    q, txt = modelos._venda(D, "hold", np.array([1]), i, np.array([10.0]), np.array([100.0]), np.array([10.0]), np.array([True]), np.array([60]))[0], None
    assert q == ""  # só a dívida (1 ponto) não vende uma empresa de nota boa e histórico forte


def test_empresa_que_saiu_da_bolsa():
    k = W.index(next(w for w in W if w >= "2021-03"))  # último pregão da BBB3 em 2021-03 (falência: preço caiu a 1)
    c = [10.0] * (k - 20) + [1.0] * 21 + [None] * (NW - k - 1)
    sn = snap({"AAA3": {"c": 10.0}, "BBB3": {"c": c}}); sn["saiu"] = {"BBB3": W[k]}
    D = modelos.build(sn, cdi(), saida={"BBB3": "Falência"})
    assert D["saiu"] == ["BBB3"] and modelos.todas(D, [{"ticker": "AAA3"}]) == ["AAA3", "BBB3"]
    me = months(D, "2020-02", "2021-12"); ap = [2000.0] + [100.0] * (len(me) - 1)
    h = modelos.grupo(D, "hold", [0, 1], me, ap, rec=True, RG={})[4]  # sem as regras: só a saída da bolsa vende
    vs = [e for e in h["mov"] if e["k"] == "venda" and e["t"] == "BBB3"]
    assert len(vs) == 1 and vs[0]["d"] > W[k] and vs[0]["p"] == 1.0 and vs[0]["x"] == "saiu da bolsa: falência", vs  # perda entra de verdade
    assert not [e for e in h["mov"] if e["k"] == "compra" and e["t"] == "BBB3" and e["d"] >= W[k]]
    assert [p["t"] for p in h["pos"]] == ["AAA3"]
    r = modelos.simulate(D, "hold", [1], me, ap, [0.0] * len(me))
    assert r["s"][0] == 1  # cada empresa sozinha: também vende ao sair
    assert modelos.compare(D, ["BBB3"], "2022-01", "2022-12", [1000.0] * 12).get("error")  # sem preço no início: fica de fora


def test_noticias_so_do_mercado_brasileiro():
    it = lambda m: {"itens": [{"data": "2021-06-02", "t": ["AAA3"], "titulo": "Pedido de recuperação judicial", **({"m": m} if m else {})}]}
    assert len(modelos.noticias_itens(noticias=it(["br", "us"]))) == 1 and len(modelos.noticias_itens(noticias=it(None))) == 1
    assert modelos.noticias_itens(noticias=it(["us"])) == []  # notícia de outro mercado: fica para modelos de lá


def test_noticias_fato_e_suposicao():
    assert modelos.tom_noticia("Pedido de Recuperação Judicial") == (-2.0, False)
    assert modelos.tom_noticia("Encerramento da recuperação judicial")[0] > 0  # frase longa vale sobre a curta
    assert modelos.tom_noticia("Empresa pode pedir recuperação judicial, dizem analistas")[1]  # suposição
    assert modelos.tom_noticia("Pagamento de juros sobre capital próprio")[0] == 0
    fatos = {"t": {"AAA3": "1"}, "c": {"1": [["2021-06-02", "Pedido de Recuperação Judicial"]]}}
    for news, vende in ((modelos.noticias_itens(fatos), True),
                        ([{"d": "2021-06-02", "t": ["AAA3"], "x": "Empresa pode pedir recuperação judicial, dizem analistas"}], False),

                        ([], False)):
        D = modelos.build(snap({"AAA3": {"c": 10.0}}), cdi(), news=news)
        me = months(D, "2020-02", "2021-12")
        h = modelos.grupo(D, "hold", [0], me, [1000.0] + [0.0] * (len(me) - 1), rec=True)[4]
        vs = [e for e in h["mov"] if e["k"] == "venda"]
        assert bool(vs) == vende, (news, vs)
        if vende: assert vs[0]["d"] >= "2021-06-02" and "Recuperação Judicial" in vs[0]["x"]  # nunca antes de a notícia sair


if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
