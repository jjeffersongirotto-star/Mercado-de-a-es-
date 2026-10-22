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
    assert r["KO"]["g"] is None and r["KO"]["f"] is None and r["KO"]["x"] == "s/ VJ"  # ação de fora: sem valor justo (Empresa estrangeira)
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

def test_widget_simgrupo_live_values():
    """Widget Grupo simulação: valor atual = caixa + ações × preço de agora; variação do dia só das ações com cotação."""
    import modelos
    setup()
    sg = {"d0": "2025-03", "d1": "2026-10", "v0": 1000.0, "m": [
        {"m": "barsi", "n": "Barsi", "cash": 100.0, "pos": [{"t": "PETR4", "q": 10, "inv": 250.0, "p": 28.0}, {"t": "ZZZZ3", "q": 5, "inv": 50.0, "p": 12.0}]},
        {"m": "ibov", "n": "Ibovespa", "ref": 1, "cash": 0, "pos": []}]}
    od, os_, oss, ou = modelos.data, modelos.set_setores, modelos.simgrupo, server.universe.universe
    modelos.data = lambda: {}; modelos.set_setores = lambda *a: None; modelos.simgrupo = lambda *a, **k: sg; server.universe.universe = lambda rows: rows
    try:
        r = json.loads(server.api_widget_simgrupo("2025-03", 1000).body)
    finally:
        modelos.data, modelos.set_setores, modelos.simgrupo, server.universe.universe = od, os_, oss, ou
    assert [x["m"] for x in r["r"]] == ["barsi"] and r["v0"] == 1000.0  # referência (ibov) fora
    b = r["r"][0]
    assert b["v"] == 100 + 10 * 30.0 + 5 * 12.0 and b["np"] == 2 and b["ap"] == 1000.0  # PETR4 ao vivo (30), ZZZZ3 sem cotação: preço da simulação
    assert abs(b["dv"] - 300 * 1.2 / 101.2) < 0.01 and b["pos"][0] == {"t": "PETR4", "q": 10, "inv": 250.0, "v": 300.0, "pm": None, "s": "Petrobras"}


def test_widget_simgrupo_dia_app_antigo():
    """Widget até a 1.18 (data só AAAA-MM): o site manda o dia em f.d e o servidor simula desde o dia (o mesmo grupo da aba Grupos)."""
    import modelos
    setup()
    vis = []; sg = {"d0": "2025-04-07", "d1": "2026-10", "v0": 1000.0, "m": []}
    od, os_, oss, ou = modelos.data, modelos.set_setores, modelos.simgrupo, server.universe.universe
    modelos.data = lambda: {}; modelos.set_setores = lambda *a: None; server.universe.universe = lambda rows: rows
    modelos.simgrupo = lambda D, tk, di, *a, **k: (vis.append(di), sg)[1]
    try:
        server.api_widget_simgrupo("2025-04", 1000, json.dumps({"ap": 0, "ex": [], "ret": [], "d": "2025-04-07"}))
        server.api_widget_simgrupo("2025-04", 1000, json.dumps({"d": "2024-01-02"}))  # dia de outro mês: ignora
    finally:
        modelos.data, modelos.set_setores, modelos.simgrupo, server.universe.universe = od, os_, oss, ou
    assert vis == ["2025-04-07", "2025-04"]


def test_widget_simgrupo_xlsx():
    """Planilha do ⬇ do widget: Resumo com todos os modelos, uma aba por modelo com resumo, posições (preço médio) e TODAS as movimentações."""
    import io, modelos, openpyxl
    setup()
    sg = {"d0": "2025-03-28", "d1": "2026-10-15", "v0": 1000.0, "apT": 1500.0, "m": [
        {"m": "barsi", "n": "Método Barsi", "cash": 100.0, "ir": 5.0, "c": 2, "s": 0, "pos": [{"t": "PETR4", "q": 10, "inv": 250.0, "p": 28.0, "pm": 25.0}]}]}
    mov = [{"d": "2025-03-28", "k": "aporte", "v": 1000.0, "x": "valor inicial"}] + [{"d": "2025-04-04", "k": "compra", "t": "PETR4", "q": 1, "p": 25.0, "v": 25.08}] * 300
    od, os_, oss, oh, ou = modelos.data, modelos.set_setores, modelos.simgrupo, modelos.sim_hist, server.universe.universe
    modelos.data = lambda: {}; modelos.set_setores = lambda *a: None; modelos.simgrupo = lambda *a, **k: sg; modelos.sim_hist = lambda *a: {"mov": mov}; server.universe.universe = lambda rows: rows
    try:
        r = server.api_widget_simgrupo_xlsx("2025-03", 1000, '{"ap":500}', "Meu/grupo")
    finally:
        modelos.data, modelos.set_setores, modelos.simgrupo, modelos.sim_hist, server.universe.universe = od, os_, oss, oh, ou
    assert r.status_code == 200 and "Meu-grupo" in r.headers["content-disposition"]
    wb = openpyxl.load_workbook(io.BytesIO(r.body))
    assert wb.sheetnames == ["Resumo", "Método Barsi"]
    R = wb["Resumo"]; assert [c.value for c in R[3]][:3] == ["Modelo", "Carteira", "Valor aportado"] and R["C4"].value == 1500 and R.freeze_panes == "A4"
    assert R["D4"].value == 400.0 and abs(R["G4"].value - (400 / 1500 - 1)) < 1e-9 and "R$" in R["D4"].number_format and "%" in R["G4"].number_format
    M = wb["Método Barsi"]; rows = [[c.value for c in r] for r in M.iter_rows()]
    i = next(k for k, x in enumerate(rows) if x[0] == "Empresa"); assert rows[i + 1][:4] == ["Petrobras", "PETR4", 10, 25.0]
    j = next(k for k, x in enumerate(rows) if x[0] == "Data"); assert len(rows) - j - 1 == 301 and rows[-1][2] == "Aporte" and rows[j + 1][3] == "PETR4" and rows[0 + j][1] == "Hora"

def test_horario_das_ordens_ao_vivo():
    # hora vista ao vivo (_PROV) vai para a compra/venda do mesmo dia nas movimentações; sem cópia no cache dos modelos
    server._PROV[("2026-01-05", 1000.0, "hold", "PETR4", "c", "2026-01-07")] = "11:32"
    mov = [{"d": "2026-01-07", "k": "compra", "t": "PETR4", "q": 10}, {"d": "2026-01-07", "k": "venda", "t": "PETR4", "q": 10}]
    out = server._horas("2026-01-05", 1000.0, "hold", mov)
    assert out[0]["h"] == "11:32" and "h" not in out[1] and "h" not in mov[0]


def test_assuntos_das_noticias():
    # assunto de cada notícia da aba Notícias: palavras de vocabulario.json → noticias.assuntos; Alertas pelo tom dos modelos; Destaque = Dividendos
    A = server.noticia_assuntos
    assert A({"titulo": "Itaú anuncia JCP"}) == ["div"] and A({"titulo": "Copom mantém a Selic"}) == ["eco"] and A({"titulo": "Lucro do 3T sobe"}) == ["res"]
    assert A({"titulo": "Empresa pede recuperação judicial"}) == ["al"] and A({"titulo": "Preço-teto", "destaque": True})[0] == "div" and A({"titulo": "nada"}) == []


def test_simulacoes_ao_vivo_limitadas():
    # _SIMS: uma por definição validada (p1/r1 no f não criam outra), só depois de dar certo, no máximo SIMS_MAX
    import modelos
    setup(); server._SIMS.clear()
    sg = {"d0": "2025-03", "d1": "2026-10", "v0": 1000.0, "m": []}
    od, os_, oss, ou = modelos.data, modelos.set_setores, modelos.simgrupo, server.universe.universe
    modelos.data = lambda: {}; modelos.set_setores = lambda *a: None; server.universe.universe = lambda rows: rows
    modelos.simgrupo = lambda D, tk, di, v0, *a, **k: sg if v0 < 1e6 else {"error": "x"}
    try:
        for k in range(3): server._simw("2025-03-10", 1000, json.dumps({"p1": {"PETR4": [10 + k, "11:00", "2025-03-10"]}}))
        assert len(server._SIMS) == 1 and json.loads(list(server._SIMS.values())[0][3])["p1"]["PETR4"][0] == 12  # guarda o último f
        server._simw("2025-03-10", 1e7, "")  # erro: não acompanha
        assert len(server._SIMS) == 1
        for k in range(server.SIMS_MAX + 5): server._simw("2025-03-10", 100 + k, "")
        assert len(server._SIMS) == server.SIMS_MAX and ("2025-03-10", 105.0, 0.0, "[]", "[]") in server._SIMS and ("2025-03-10", 104.0, 0.0, "[]", "[]") not in server._SIMS  # saem as mais antigas
        assert all(k[0] == "2025-03-10" for k in server._SIMS)  # di validado (modelos.sim_def)
    finally:
        modelos.data, modelos.set_setores, modelos.simgrupo, server.universe.universe = od, os_, oss, ou
        server._SIMS.clear()


def test_trim_dias_tira_os_mais_antigos():
    d = {("2026-01-0%d" % (k % 3 + 1), k): k for k in range(9)}
    server._trim_dias(d, 4, lambda k: k[0])
    assert len(d) == 4 and all(k[0] >= "2026-01-02" for k in d)


def test_registro_do_chat_exige_token():
    class Rq: headers = {}
    old = os.environ.pop("CHAT_LOG_TOKEN", None)
    try:
        assert server.api_chat_log(Rq(), token="x").status_code == 403  # sem a variável: ninguém lê
        os.environ["CHAT_LOG_TOKEN"] = "segredo"
        assert server.api_chat_log(Rq(), token="errado").status_code == 403
        Rq.headers = {"x-chat-log-token": "segredo"}
        assert server.api_chat_log(Rq(), n=1).status_code == 200
    finally:
        os.environ.pop("CHAT_LOG_TOKEN", None)
        if old is not None: os.environ["CHAT_LOG_TOKEN"] = old


def test_refresh_espera_depois_de_atualizar():
    calls = []; orig = server.cache.refresh_async, server.cache.done_at
    server.cache.refresh_async = lambda: calls.append(1)
    try:
        server.cache.done_at = time.time()
        assert server.api_refresh() == {"started": False, "refreshing": False} and not calls  # acabou de atualizar
        server.cache.done_at = time.time() - server.REFRESH_MIN - 1
        assert server.api_refresh()["started"] in (True, False) and calls == [1]
    finally:
        server.cache.refresh_async, server.cache.done_at = orig


def test_json_pronto_so_da_versao_atual():
    class Rq: headers = {"accept-encoding": "gzip"}
    server._JSON_CACHE.clear()
    a, b = {"rows": [1]}, {"rows": [2]}
    server._json_fast(Rq(), a, {"refreshing": False}); server._json_fast(Rq(), b, {"refreshing": False}); server._json_fast(Rq(), b, {"refreshing": True})
    assert len(server._JSON_CACHE) == 1 and server._JSON_CACHE["br"]["d"] is b and len(server._JSON_CACHE["br"]["gz"]) == 2
    for k in range(server.GZ_MAX + 3): server._json_fast(Rq(), b, {"e": k})
    assert len(server._JSON_CACHE["br"]["gz"]) == server.GZ_MAX
    server._JSON_CACHE.clear()

if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"): f(); n += 1
    print(n, "testes ok")
