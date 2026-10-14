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
    pa = [600] * 80 + [400] * (NW - 80); pb = [590] * 60 + [700] * 20 + [400] * (NW - 80)
    D = modelos.build(snap({"AAA3": {"c": 10.0, "p1": pa}, "BBB3": {"c": 10.0, "p1": pb}}), cdi())
    me = months(D, "2020-09", "2022-03")
    r = modelos.rotate(D, "alg1", [0, 1], me, [1000.0] + [0.0] * (len(me) - 1), [0.0] * len(me))
    mv = [(x["de"], x["para"]) for x in r["hist"]["mov"]]
    assert mv[:3] == [(None, "AAA3"), ("AAA3", "BBB3"), ("BBB3", None)], mv  # melhor chance, troca por margem, todas desfavoráveis
    # (depois de meses em 400, a mediana do último ano também vira 400 e a empresa volta a ser favorável)
    assert r["hist"]["mov"][1]["d"] == W[61] and "BBB3 com sinal melhor" in r["hist"]["mov"][1]["m"]
    assert r["hist"]["trocas"] == 1 and r["hist"]["cdb"] > 0 and {x["t"] for x in r["hist"]["emp"]} == {"AAA3", "BBB3"}


def test_hibrido_nunca_vende_e_segue_quem_acerta():
    c = [10.0 * 1.01 ** k for k in range(NW)]  # ação subindo sempre: o especialista "comprar e segurar" ganha peso
    D = modelos.build(snap({"AAA3": {"c": c, "p1": 400, "p3": 400, "m2": -10}}), cdi(0.01))
    assert D["HX"][0, 60] == 1 and D["HW"][:, 0, 60].argmax() == 0  # 100% na ação, seguindo Comprar e segurar
    me = months(D, "2020-09", "2021-12")
    r = modelos.simulate(D, "hibrido", [0], me, [1000.0] + [100.0] * (len(me) - 1), [0.0] * len(me), rec=True)
    assert r["s"][0] == 0 and r["ir"][0] == 0 and "Comprar e segurar" in r["rows"][0][-1]["pos"]


def test_run_todos_ordena_grupos_primeiro():
    D = modelos.build(snap({"AAA3": {"c": [10.0 + k * .1 for k in range(NW)]}, "BBB3": {"c": 10.0}}), cdi())
    out = modelos.run(D, {"di": "2020-09", "df": "2021-12", "ap": [1000] + [100] * 15, "ticker": "*", "modelo": "*", "universo": ["AAA3", "BBB3"],
                          "grupos": [{"n": "G", "t": ["AAA3", "BBB3"]}]})
    ks = [x["k"] for x in out["rows"]]
    assert ks == sorted(ks, key=lambda k: k != "g") and ks.count("g") == 3  # um rodízio por modelo que troca de empresa (Algoritmos e Tendência)
    emp = [x for x in out["rows"] if x["k"] == "a"]
    assert all(a["pct"] >= b["pct"] for a, b in zip(emp, emp[1:])) and len(emp) == 2 * len(modelos.MODELOS)


if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
