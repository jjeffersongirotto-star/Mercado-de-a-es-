"""/api/widget e /api/widget/chart com ações de fora (sem rede: cotações e histórico simulados). Rodar: python tests/test_widget_api.py"""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import server, history

ROWS = [{"ticker": "PETR4", "nome": "PETROLEO BRASILEIRO S.A. PETROBRAS", "cur": "BRL", "var": 1.2, "v": {"preco": 30.0, "vpa": 20.0, "lpa": 3.0}}]
FQ = {"KO": {"c": "us", "cur": "USD", "n": "Coca-Cola Company (The)", "var": -0.5, "sub": None, "v": {"preco": 60.0, "vpa": 6.0, "lpa": 2.5}},
      "BRK.B": {"c": "us", "cur": "USD", "n": "Berkshire Hathaway Inc.", "var": 0.3, "sub": None, "v": {"preco": 480.0, "vpa": 300.0, "lpa": -1.0}},
      "7203": {"c": "jp", "cur": "JPY", "n": "Toyota Motor Corporation", "var": 1.0, "sub": None, "v": {"preco": 3000.0, "vpa": None, "lpa": 300.0}}}

def setup():
    server.cache.data = {"rows": ROWS, "updated_at_sp": "17/10/2026 09:00:00"}
    server._FQ.update(q=FQ, at=time.time(), busy=False)
    server._LOGO_IDX.update(t={"KO": {"f": "4cd4fb315e6f.png", "s": "favicon"}, "AAPL34": {"f": "651952a76745.png", "s": "bdr"}}, at=time.time())

def widget(t, v=2):
    return json.loads(server.api_widget(t, v).body)["r"]

def test_short_and_dotted_tickers():
    setup()
    r = {x["t"]: x for x in widget("KO,BRK.B,PETR4,AAPL34,7203,bad ticker!,X" + "Y" * 20)}
    assert set(r) == {"KO", "BRK.B", "PETR4", "AAPL34", "7203"}
    assert r["KO"]["p"] == 60.0 and r["KO"]["v"] == -0.5 and r["KO"]["c"] == "USD" and r["KO"]["s"] == "Coca-Cola" and r["KO"]["l"] == "4cd4fb315e6f.png"
    assert r["KO"]["g"] is None and r["KO"]["m"] == "Graham" and r["KO"]["f"] is not None  # Graham com LPA e VPA do TradingView, como fairOf
    assert r["BRK.B"]["p"] == 480.0 and r["BRK.B"]["f"] is None  # prejuízo: sem valor justo (como fairOf)
    assert r["7203"]["c"] == "JPY" and r["7203"]["f"] is None  # sem VPA
    assert r["AAPL34"] == {"t": "AAPL34", "l": "651952a76745.png", "s": "Apple"}  # BDR que o site não mostra: só o logo e o nome popular
    assert "c" not in r["PETR4"] and r["PETR4"]["p"] == 30.0
    assert server._FQ["want"].get("us")  # país pedido: passa a ser renovado ao vivo
    old = {x["t"]: x for x in widget("KO,PETR4", v=1)}  # app 1.5 (sem v=2): sem preço de fora (mostraria R$)
    assert old["KO"] == {"t": "KO", "l": "4cd4fb315e6f.png", "s": "Coca-Cola", "k": "us"} and old["PETR4"]["p"] == 30.0

def test_chart_foreign_uses_card_history():
    setup()
    seen = []
    now = int(time.time()); pts = list(range(now - 6 * 365 * 86400, now, 86400 * 7))
    fake = {"t": pts, "c": [10.0 + i for i in range(len(pts))], "at": "x"}
    oy, og = history.yget, history.get
    history.yget = lambda sym, kind: (seen.append(sym), fake)[1]
    history.get = lambda t, kind: (seen.append("B3:" + t), fake)[1]
    try:
        server._WCHART.clear()
        a = json.loads(server.api_widget_chart("BRK.B").body)
        b = json.loads(server.api_widget_chart("PETR4").body)
    finally:
        history.yget, history.get = oy, og
    assert seen == ["BRK-B", "B3:PETR4"] and a["c"] == "USD" and "c" not in b and len(a["p"]) > 50

def test_widget_refresh_only_stale_in_session():
    from datetime import datetime
    tz = server.TZ
    seg_14h, sab_14h, seg_20h = datetime(2026, 10, 19, 14, 0, tzinfo=tz), datetime(2026, 10, 17, 14, 0, tzinfo=tz), datetime(2026, 10, 19, 20, 0, tzinfo=tz)
    assert server.widget_should_refresh(15 * 60, seg_14h)
    assert not server.widget_should_refresh(5 * 60, seg_14h)       # dados recentes: só busca
    assert not server.widget_should_refresh(3 * 3600, sab_14h)     # fim de semana: nada pesado
    assert not server.widget_should_refresh(3 * 3600, seg_20h)     # depois do pregão
    calls = []
    orig_ra, orig_age = server.cache.refresh_async, server.cache.age
    server.cache.refresh_async = lambda: calls.append(1); server.cache.age = lambda: 0
    try:
        fq = dict(server.cache.foreign)
        r = server.api_refresh("widget")
        assert r == {"started": False, "refreshing": server.cache.refreshing} and not calls and server.cache.foreign == fq  # não limpa as de fora
    finally:
        server.cache.refresh_async, server.cache.age = orig_ra, orig_age

def test_popular_names_by_country():
    import snapshots as S
    assert S.nome_popular("GOOG", "Alphabet Inc.", "us") == "Google" and "facebook" in S.nome_busca("META", "us")
    assert S.nome_popular("ALV", "Autoliv Inc.", "us") == "Autoliv" and S.nome_popular("ALV", "Allianz SE", "de") == "Allianz"  # mesmo ticker, outra bolsa
    assert S.nome_popular("PETR4", "PETROLEO BRASILEIRO") == "Petrobras" and "magazine luiza" in S.nome_busca("MGLU3")
    assert S.nome_popular("PCAR", "Paccar Inc", "us") == "Paccar" and S.nome_popular("PCAR3", "CIA BRASILEIRA DE DISTRIBUICAO") == "GPA"

if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"): f(); n += 1
    print(n, "testes ok")
