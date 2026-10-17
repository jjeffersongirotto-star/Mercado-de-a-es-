"""Barato/Caro (valor_justo.fair): janela do LPA (3 anos, 5 anos, 12 meses) e rótulos sem valor justo. Rodar: python tests/test_valor_justo.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import valor_justo as V

def f(r, **v):
    r = {"cur": "BRL", **r}
    return V.fair(r, lambda o, k: (o.get("v") or v).get(k), [])

def test_janelas():
    j, pct, m = f({"ln3": 0.1}, preco=10.0, vpa=20.0, lpa=-1.0)  # prejuízo só em 12 meses não trava com média de 3 anos positiva
    assert m == "Graham" and abs(j - (22.5 * 2.0 * 20) ** .5) < 1e-9
    j, pct, m = f({"ln3": -0.02, "ln5": 0.01}, preco=10.0, vpa=20.0, lpa=-1.0)  # média de 3 anos negativa, 5 anos positiva
    assert m == "Graham · média 5a" and abs(j - (22.5 * 0.2 * 20) ** .5) < 1e-9
    j, pct, m = f({"ln3": -0.02, "ln5": 0.01, "seg": "Energia Elétrica", "dpsm": 0.9}, preco=15.0, vpa=20.0, lpa=-1.0)  # AURE3: Barsi
    assert m == "Barsi · média 5a" and abs(j - 15.0) < 1e-9
    assert f({}, preco=10.0, vpa=20.0, lpa=1.0)[2] == "Graham · LPA 12m"  # sem média na CVM: 12 meses

def test_zero():  # AURE3 mostrava −0%: o que arredonda para 0% vira 0 (verde, sem sinal)
    assert V.margem(14.79, 14.82) == 0.0 and V.margem(14.9, 14.82) > 0 and V.margem(10.0, 10.06) < 0
    assert f({"ln3": 0.1}, preco=(22.5 * 2.0 * 20) ** .5 * 1.004, vpa=20.0)[1] == 0.0

def test_rotulos():
    _, why, _ = f({"ln3": -0.02, "ln5": -0.01}, preco=10.0, vpa=20.0, lpa=1.0)
    assert why == "Prejuízo médio nos últimos 3 e 5 anos" and V.rotulo(why) == ["Prejuízo recorrente", "Prej."]
    assert V.rotulo(f({"ln3": -0.02}, preco=10.0, vpa=20.0)[1])[0] == "Prejuízo recorrente"
    for r, v in (({}, dict(preco=0.0, vpa=20.0, lpa=1.0)), ({}, dict(preco=None, vpa=20.0, lpa=1.0)), ({}, dict(preco=10.0, vpa=-5.0, lpa=1.0)),
                 ({}, dict(preco=10.0, vpa=None, lpa=1.0)), ({"st": {"vpa": "red"}}, dict(preco=10.0, vpa=20.0, lpa=1.0)),
                 ({"ln3": 0.0}, dict(preco=10.0, vpa=20.0, lpa=1.0)), ({}, dict(preco=10.0, vpa=20.0, lpa=-1.0))):
        j, why, m = f(r, **v)
        assert j is None and V.rotulo(why) == ["Sem valor justo", "s/ VJ"], (r, v, why)
    assert f({}, preco=10.0, vpa=-5.0)[1] == "Patrimônio negativo"

if __name__ == "__main__":
    for k, fn in list(globals().items()):
        if k.startswith("test_"): fn()
    print("ok")
