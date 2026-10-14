"""Testes do Comparar → Medo e Ganância (medo.analyze) com histórico e índice simulados. Rodar: python tests/test_medo.py"""
import os, sys, calendar
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import history, snapshots, medo

FX = [[25, "Medo extremo"], [45, "Medo"], [55, "Neutro"], [75, "Ganância"], [100, "Ganância extrema"]]
MS = [f"{y}-{m:02d}" for y in range(2010, 2014) for m in range(1, 13)]  # 48 meses
ts = lambda ym: calendar.timegm((int(ym[:4]), int(ym[5:]), 15, 13, 0, 0))
# índice: medo extremo (10) nos meses 0–11, ganância extrema (90) nos meses 12–47
FG = {m: (10 if i < 12 else 90) for i, m in enumerate(MS)}
# ação: sobe 2% ao mês, mas cai 30% no mês 20 (depois de ganância extrema) e sobe 40% no mês 5 (depois de medo extremo)
C, c = [], 10.0
for i, m in enumerate(MS):
    c *= 0.7 if i == 20 else 1.4 if i == 5 else 1.02
    C.append(round(c, 4))


def setup():
    history.b3hist = lambda t: {"m": {"t": [ts(m) for m in MS], "c": C}, "divs": [[ts(m), 0.1] for m in MS]}
    history.get = lambda t, k: {"t": [ts(m) for m in MS], "c": [100 + i for i in range(len(MS))]}
    snapshots.load = lambda name, **k: ({"d": [m + "-28" for m in MS], "v": [FG[m] for m in MS], "faixas": FX, "fetched_at": "x"}, "teste")
    medo._C.clear()


def test_analysis():
    setup()
    d = medo.analyze("TEST3", "2010-01-01", "2013-12-31")
    assert d["n"] == 48 and d["per"] == ["2010-01", "2013-12"]
    q = d["quedas"][0]; assert q["m"] == MS[20] and q["r"] == -30.0 and q["b"] == 4  # maior queda veio depois de ganância extrema
    a = d["altas"][0]; assert a["m"] == MS[5] and a["r"] == 40.0 and a["b"] == 0     # maior alta começou com medo extremo
    fa = {x["b"]: x for x in d["faixa"]}
    assert fa[0]["n"] == 12 and fa[4]["n"] == 36 and fa[1]["n"] == fa[2]["n"] == fa[3]["n"] == 0
    assert fa[0]["n12"] == 12 and fa[0]["up12"] == sum(1 for i in range(12) if C[i + 12] > C[i]) and fa[0]["dy"] is not None
    hi = [MS[i] for i in range(11, 48) if C[i] >= max(C[i - 11:i + 1])]  # máximas de 12 meses: conta direta
    assert sum(d["topos"]) == len(hi) and d["topos"][0] == sum(1 for m in hi if FG[m] == 10) and d["topos"][4] == sum(1 for m in hi if FG[m] == 90)
    assert d["hoje"]["v"] == 90 and d["hoje"]["b"] == 4
    assert d["serie"]["m"] == MS and len(d["serie"]["fg"]) == 48
    assert d["recup"]["n"] == 0  # o índice não "entrou" em medo extremo dentro do período (já começou nele)


def test_period_filter_and_cache():
    setup()
    d = medo.analyze("TEST3", "2012-01-01", "2012-12-31")
    assert d["n"] == 12 and all(x["b"] == 4 for x in d["faixa"] if x["n"])
    assert medo.analyze("TEST3", "2012-01-01", "2012-12-31") is d  # mesmo pedido: vem da memória


if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
