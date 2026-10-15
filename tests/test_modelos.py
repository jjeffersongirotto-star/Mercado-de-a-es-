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
    assert pts.tolist() == [8, 12, 4]  # 3 modelos: 1º = 4, 2º = 2, 3º = 0


def test_comparar_media_e_empresas_sem_preco():
    D = modelos.build(snap({"AAA3": {"c": [10.0 + k * .1 for k in range(NW)]}, "BBB3": {"c": 10.0}}), cdi())
    out = modelos.compare(D, ["AAA3", "BBB3", "XXX3"], "2020-09", "2021-12", [1000.0] + [100.0] * 15, grupos=[{"n": "G", "t": ["AAA3", "BBB3"]}])
    assert len(out["v"]) == len(modelos.MODELOS) and len(out["v"][0]) == 2 and sum(r["pts"] for r in out["res"]) == 2 * sum(range(0, 2 * len(modelos.MODELOS), 2))
    assert {g["m"] for g in out["g"]} == {"alg1", "alg3", "tendencia"}
    assert out["t"] == ["AAA3", "BBB3"] and out["pedidas"] == 3 and len(out["p"]) == len(modelos.MODELOS)
    i = out["m"].index("hold"); assert abs(out["res"][i]["media"] - sum(out["p"][i]) / 2) < 0.01
    assert [out["res"][k]["media"] for k in out["ord_media"]] == sorted((r["media"] for r in out["res"]), reverse=True)


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
    assert ks == sorted(ks, key="rga".index) and ks.count("g") == 3 and ks.count("r") == len(modelos.REF)  # CDB e Ouro uma vez, no topo  # um rodízio por modelo que troca de empresa (Algoritmos e Tendência)
    emp = [x for x in out["rows"] if x["k"] == "a"]
    assert all(a["pct"] >= b["pct"] for a, b in zip(emp, emp[1:])) and len(emp) == 2 * len(modelos.MODELOS)


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
    assert [r["m"] for r in out["ref"]] == ["cdb", "ouro"] and len(out["res"]) == len(modelos.MODELOS)  # fora das colocações
    t = modelos.run(D, {"di": "2020-02", "df": "2020-12", "ap": ap, "tab": {"t": "", "m": "ouro"}})["tab"]
    assert abs(t[-1]["com"] - o["v"]) < 1e-6
    sem = modelos.simulate_ref(modelos.build(snap({"AAA3": {"c": 10.0}}), cdi()), "ouro", me, ap, w)
    assert sem["v"] != sem["v"]  # sem ouro: sem dado


if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
