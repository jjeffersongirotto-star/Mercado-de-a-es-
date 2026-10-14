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
    history.b3full = lambda t: {"t": [ts(x) for x in DAYS], "c": C}
    history.get = lambda t, k: {"t": [ts(x) for x in DAYS[::21]], "c": [100 + i for i in range(len(DAYS[::21]))]}
    snapshots.load = lambda name, **k: ({"d": [x.isoformat() for x in DAYS], "v": [FG[x.isoformat()] for x in DAYS], "faixas": FX,
                                         "fetched_at": "x", "acoes": {"TEST3": [60, 58, 55, 40]}}, "teste")
    medo._C.clear()


def test_analysis():
    setup()
    d = medo.analyze("TEST3", "2010-01-01", "2013-12-31")
    assert d["n"] == 48 and d["per"] == ["2010-01", "2013-12"]
    q = d["quedas"][0]; assert q["d"] == DAYS[299].isoformat() and round(q["r"]) == -30 and q["fg"] == 90 and q["b"] == 4
    a = d["altas"][0]; assert a["d"] == DAYS[99].isoformat() and round(a["r"]) == 40 and a["fg"] == 10 and a["b"] == 0
    assert len(d["altas"]) == 10 and all(x["r"] > 0 for x in d["altas"])
    starts = sorted(DAYS.index(date.fromisoformat(x["d"])) for x in d["altas"])
    assert all(b - a >= 5 for a, b in zip(starts, starts[1:]))  # semanas sem sobreposição
    fa = {x["b"]: x for x in d["faixa"]}
    assert fa[0]["n"] == 12 and fa[4]["n"] == 36 and fa[0]["n12"] == 12
    assert d["acao"] == [60, 58, 55, 40] and d["mercado"][0] == 90 and d["hoje"]["v"] == 90 and d["hoje"]["b"] == 4
    s = d["serie"]; assert s["d"][0] >= "2010-01-01" and len(s["d"]) == len(s["c"]) == len(s["fg"])
    assert "dy" not in fa[0]


def test_weekly_points_before_6_years_and_cache():
    setup()
    d = medo.analyze("TEST3", "2010-01-01", "2013-12-31")
    assert len(d["serie"]["d"]) == len(DAYS)  # período menor que 6 anos: todos os pregões
    d2 = medo.analyze("TEST3", "2010-01-01", "2019-12-31")  # fim mais de 6 anos depois: 2010–2013 viram um ponto por semana
    assert len(d2["serie"]["d"]) < len(DAYS) * 0.3
    assert medo.analyze("TEST3", "2010-01-01", "2019-12-31") is d2  # mesmo pedido: vem da memória


if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
