"""Testes do Comparar → Medo e Ganância (medo.analyze) com histórico diário e índice simulados. Rodar: python tests/test_medo.py"""
import os, sys, calendar
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import history, snapshots, medo

FX = [[25, "Medo extremo"], [45, "Medo"], [55, "Neutro"], [75, "Ganância"], [100, "Ganância extrema"]]
# pregões de 2010 a 2013 (dias úteis)
DAYS = [date(2010, 1, 4) + timedelta(days=k) for k in range(0, 4 * 366)]
DAYS = [x for x in DAYS if x.weekday() < 5 and x.year <= 2013]
ts = lambda x: calendar.timegm((x.year, x.month, x.day, 13, 0, 0))
FG = {x.isoformat(): (10 if x.year == 2010 else 90) for x in DAYS}  # medo extremo em 2010, ganância extrema depois
# ação: +0,1% por pregão; semana com −30% começando no pregão 300 (ganância) e +40% começando no pregão 100 (medo)
C, c = [], 10.0
for i in range(len(DAYS)):
    c *= 0.7 ** (1 / 5) if 300 <= i < 305 else 1.4 ** (1 / 5) if 100 <= i < 105 else 1.001
    C.append(round(c, 6))


def setup():
    history.b3full = lambda t: {"t": [ts(x) for x in DAYS], "c": C, "v": [1e6 + (i % 7) * 1e5 for i in range(len(DAYS))]}
    history.get = lambda t, k: {"t": [ts(x) for x in DAYS[::21]], "c": [100 + i for i in range(len(DAYS[::21]))]}
    snapshots.load = lambda name, **k: ({"d": [x.isoformat() for x in DAYS], "v": [FG[x.isoformat()] for x in DAYS], "faixas": FX,
                                         "fetched_at": "x"}, "teste")
    medo._C.clear()


def test_analysis():
    setup()
    d = medo.analyze("TEST3", "2010-01-01", "2013-12-31")
    SI = medo.stock_index(C, [1e6 + (i % 7) * 1e5 for i in range(len(DAYS))])  # índice da própria ação
    assert d["n"] == 48 and d["per"] == ["2010-01", "2013-12"]
    q = d["quedas"][0]; assert q["d"] == DAYS[299].isoformat() and round(q["r"]) == -30 and q["fg"] == SI[299]
    assert q["b"] == medo._band(SI[299], FX) and SI[299] >= 55  # depois de mais de um ano subindo, a ação estava em ganância
    assert len(d["altas"]) == 10 and all(x["r"] > 0 for x in d["altas"])
    starts = sorted(DAYS.index(date.fromisoformat(x["d"])) for x in d["altas"])
    assert all(b - a >= 5 for a, b in zip(starts, starts[1:]))  # semanas sem sobreposição
    L = [s for s in SI if s is not None]
    assert d["acao"] == [L[-1], L[-2], L[-6], L[-22]] and d["mercado"][0] == 90  # velocímetros: ação e mercado
    assert d["hoje"]["v"] == L[-1] and d["hoje"]["b"] == medo._band(L[-1], FX)
    assert sum(x["n"] for x in d["faixa"]) == len({x.isoformat()[:7] for i, x in enumerate(DAYS) if SI[i] is not None})  # meses com índice da ação
    assert sum(d["topos"]) > 0 and d["topos"][4] + d["topos"][0] == sum(d["topos"])  # topos e fundos: índice do mercado (10 ou 90)
    s = d["serie"]; assert len(s["d"]) == len(s["c"]) == len(s["fg"]) and s["fg"][-1] == L[-1]
    assert "dy" not in d["faixa"][0]


def test_weekly_points_before_6_years_and_cache():
    setup()
    d = medo.analyze("TEST3", "2010-01-01", "2013-12-31")
    SI = medo.stock_index(C, [1e6 + (i % 7) * 1e5 for i in range(len(DAYS))])
    assert len(d["serie"]["d"]) == sum(1 for s in SI if s is not None)  # período menor que 6 anos: todo pregão com índice da ação
    d2 = medo.analyze("TEST3", "2010-01-01", "2019-12-31")  # fim mais de 6 anos depois: 2010–2013 viram um ponto por semana
    assert len(d2["serie"]["d"]) < len(DAYS) * 0.3
    assert medo.analyze("TEST3", "2010-01-01", "2019-12-31") is d2  # mesmo pedido: vem da memória


if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
