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
    assert abs(r["v"][0] - 1000 * (1 - modelos.CUSTO)) < 1e-6 and r["c"][0] == 1 and r["s"][0] == 0


def test_ir_isencao_ate_20_mil():
    c = [10.0] * 5 + [20.0] * (NW - 5); m2 = [10] * 10 + [-10] * (NW - 10)  # dobra de preço; perde a média na semana 10
    D = modelos.build(snap({"AAA3": {"c": c, "m2": m2}}), cdi())
    me = months(D, "2020-01", "2020-06")
    for ini, isento in ((10000.0, True), (15000.0, False)):
        r = modelos.simulate(D, "tendencia", [0], me, [ini] + [0.0] * (len(me) - 1), [0.0] * len(me))
        venda = ini * (1 - modelos.CUSTO) / 10 * 20 * (1 - modelos.CUSTO)
        ir = 0 if isento else (venda - ini) * modelos.IR
        assert r["s"][0] == 1 and abs(r["ir"][0] - ir) < 1e-6 and abs(r["v"][0] - (venda - ir)) < 1e-6, (ini, r)


def test_prejuizo_compensa_lucro_seguinte():
    A = modelos.Conta(1); A.cash += 30000
    one, p = np.array([True]), lambda x: np.array([x])
    A.buy(one, p(10)); A.sell(one, p(8)); A.close_month(p(8), p(0), p(0), None)
    perda = 30000 - 30000 * (1 - modelos.CUSTO) / 10 * 8 * (1 - modelos.CUSTO)
    assert A.ir[0] == 0 and abs(A.carry[0] - perda) < 1e-6
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
    mv = [(x["de"], x["para"]) for x in r["hist"]["mov"]]
    assert mv[:3] == [(None, "AAA3"), ("AAA3", "BBB3"), ("BBB3", None)], mv  # melhor chance, troca por margem, todas desfavoráveis
    # (depois de meses em 400, a mediana do último ano também vira 400 e a empresa volta a ser favorável)
    assert r["hist"]["mov"][1]["d"] == W[61] and "BBB3 com sinal melhor" in r["hist"]["mov"][1]["m"]
    m = r["hist"]["mov"]
    assert m[0]["vc"] > 0 and m[1]["vv"] > 0 and m[1]["pct"] is not None and m[1]["vc"] > 0 and m[2]["vv"] > 0  # valores de compra e venda
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
    assert sum(r["pts"] for r in out["res"]) == 2 * sum((modelos.PONTOS + (0,) * nm)[:nm - 2])  # sem Barsi (fora) e sem Ouro (sem cotação no teste)
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
    D = modelos.build(snap({"AAA3": {"c": 10.0}}), cdi(0.01), gold)
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
    out = modelos.compare(D, ["AAA3"], "2020-02", "2020-12", ap)
    assert [r["m"] for r in out["ref"]] == ["cdb", "ouro"] and out["m"][-2:] == ["cdb", "ouro"] and modelos.MOD["cdb"]["n"] == "CDB"
    pts = {out["m"][i]: out["res"][i]["pts"] for i in range(len(out["m"]))}
    assert sorted(pts.values())[:2] == sorted([pts["cdb"], pts["ouro"]])  # nos Pontos, sempre as últimas colocações
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
    v, ir, nb, ns = modelos.grupo(D, "hold", [0, 1], me, ap)
    assert abs(v - sum(ap) * (1 - modelos.CUSTO)) < 1e-6 and ns == 0 and nb == 2 * len(me)  # divide cada aporte entre as duas
    out = modelos.compare(D, ["AAA3", "BBB3"], "2020-02", "2020-12", ap)
    c = {x["m"]: x for x in out["cart"]}; assert abs(c["hold"]["v"] - v) < 0.01 and c["cdb"].get("ref")



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



def test_rend_medio_anual():
    """Bloco de 12 meses com rendimento fixo: média anual = o rendimento do ano, com ou sem aportes; sobra < 12 meses não entra."""
    g = 1.10 ** (1 / 12); VM = [1000 * g ** k for k in range(25)]
    assert abs(modelos.anual(VM, [1000.0], [])[0] - 10) < 1e-9
    ap = [1000.0] + [100.0] * 24; VM = [1000.0]
    for k in range(1, 25): VM.append(VM[-1] * g + 100)
    assert abs(modelos.anual(VM, ap, [])[0] - 10) < 0.2  # Dietz modificado: aproximação do rendimento com aportes
    assert abs(modelos.anual(VM[:20], ap, [])[0] - modelos.anual(VM[:13], ap, [])[0]) < 1e-9  # 2º bloco incompleto fica fora
    assert np.isnan(modelos.anual(VM[:12], ap, [])[0])


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
        assert sum(1 for x in h["mov"] if x["op"] == "venda") == b[3]
    al = {x["m"]: x for x in r["m"]}["alg1"]; assert any(x["op"] == "venda" for x in al["mov"]) and all({"d", "t", "q", "p", "v"} <= set(x) for x in al["mov"] if x["op"] in ("compra", "venda"))
    # dia seguinte (uma semana nova nos dados): as movimentações de ontem continuam iguais, só entram as novas (igual a recalcular)
    for nw in (NW - 7, NW - 3):
        D0, D1 = modelos.build(_sim_snap(nw), cdi(0.03)), modelos.build(_sim_snap(nw + 1), cdi(0.03))
        modelos._C.clear(); r0, r1 = modelos.simgrupo(D0, tk, "2020-02", 10000), modelos.simgrupo(D1, tk, "2020-02", 10000)
        for x0 in r0["m"]:
            if x0.get("ref"): continue
            x1 = next(x for x in r1["m"] if x["m"] == x0["m"])
            trade = lambda L: [x for x in L if x["op"] in ("compra", "venda")]
            assert trade(x1["mov"])[:len(trade(x0["mov"]))] == trade(x0["mov"]), x0["m"]
    assert "error" in modelos.simgrupo(D, tk, "2020-02", 0)
    modelos._C.clear()


if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
