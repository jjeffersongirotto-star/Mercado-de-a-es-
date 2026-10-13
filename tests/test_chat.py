"""Testes do chat: perguntas reais escritas de vários jeitos. Rodar: python -m pytest tests/ (ou python tests/test_chat.py)."""
import os, time, sys, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.pop("GEMINI_API_KEY", None)
import chat
chat._WIKI.update(t=time.time(), d={})  # testes sem rede: base da Wikipedia vazia (cada teste injeta o que precisa)

FIELDS = [("preco", "Cotação", "R$", None, False), ("dy", "Div. Yield", "%", "high", False), ("pl", "P/L", "x", "low", True),
          ("pvp", "P/VP", "x", "low", True), ("roe", "ROE", "%", "high", False), ("roic", "ROIC", "%", "high", False),
          ("mliq", "Marg. Líquida", "%", "high", False), ("dlpl", "Dív.Líq/Patrim.", "x", "low", False), ("lpa", "LPA", "R$", "high", False),
          ("vpa", "VPA", "R$", "high", False), ("evebitda", "EV/EBITDA", "x", "low", True), ("liq2m", "Liquidez 2 meses", "R$", "high", False),
          ("valmerc", "Valor de Mercado", "R$", None, False)]


def R(t, nome, setor, sub, var, **v):
    return {"ticker": t, "nome": nome, "setor": setor, "subsetor": sub, "var": var, "v": dict(v, liq2m=v.get("liq2m", 1e8)), "st": {}}


ROWS = [R("PETR4", "Petroleo Brasileiro SA Pfd", "Energy Minerals", "Integrated Oil", 0.9, preco=56.0, dy=6.5, pl=5.4, pvp=1.5, roe=30.3, dlpl=0.65, lpa=10.3, valmerc=7.6e11, liq2m=2.5e9),
        R("PETR3", "Petroleo Brasileiro SA", "Energy Minerals", "Integrated Oil", 1.8, preco=60.0, dy=6.0, pl=5.8, pvp=1.6, roe=30.3, valmerc=7.6e11, liq2m=4e8),
        R("VALE3", "Vale S.A.", "Non-Energy Minerals", "Steel", 0.4, preco=67.9, dy=8.3, pl=28.0, pvp=1.5, roe=5.0, dlpl=0.34, valmerc=2.7e11, liq2m=1.5e9),
        R("ITUB4", "Itau Unibanco Holding SA Pfd", "Finance", "Major Banks", 2.3, preco=50.5, dy=5.9, pl=12.5, pvp=2.6, roe=22.0, valmerc=5.7e11, liq2m=1.4e9),
        R("ITUB3", "Itau Unibanco Holding S.A.", "Finance", "Major Banks", 1.0, preco=54.2, dy=5.6, pl=13.4, pvp=2.7, roe=22.0, liq2m=1e8),
        R("BBDC4", "Banco Bradesco SA Pfd", "Finance", "Major Banks", 0.5, preco=18.0, dy=7.9, pl=9.4, pvp=1.0, roe=11.0, liq2m=9e8),
        R("BBAS3", "Banco do Brasil S.A.", "Finance", "Major Banks", 1.6, preco=24.6, dy=9.9, pl=4.0, pvp=0.7, roe=6.8, liq2m=7e8),
        R("BBSE3", "BB Seguridade Participacoes SA", "Finance", "Life/Health Insurance", 0.2, preco=35.0, dy=11.2, pl=8.0, pvp=6.0, roe=85.0, liq2m=2.7e8),
        R("CYRE3", "Cyrela Brazil Realty SA", "Finance", "Real Estate Development", 0.1, preco=25.0, dy=12.0, pl=6.0, pvp=1.1, roe=18.0, liq2m=3e8),
        R("WEGE3", "WEG SA", "Producer Manufacturing", "Electrical Products", -0.6, preco=40.0, dy=1.8, pl=28.0, pvp=8.0, roe=30.0, mliq=15.6, liq2m=6e8),
        R("MGLU3", "Magazine Luiza S.A.", "Retail Trade", "Department Stores", 19.2, preco=9.0, pl=113.0, pvp=0.9, roe=1.0, liq2m=4e8),
        R("CMIG4", "Companhia Energetica de Minas Gerais", "Utilities", "Electric Utilities", 0.3, preco=11.0, dy=9.4, pl=6.0, pvp=1.2, roe=20.0),
        R("TAEE11", "Transmissora Alianca De Energia Eletrica S.A. Unit", "Utilities", "Electric Utilities", 1.8, preco=36.0, dy=6.5, pl=9.0, pvp=1.8, roe=18.0),
        R("POSI3", "Positivo Tecnologia SA", "Electronic Technology", "Computer Processing Hardware", 14.5, preco=6.0, dy=3.0, pl=5.0, pvp=0.45, roe=9.0, lpa=1.2),
        R("SYNE3", "Syn Prop e Tech SA", "Finance", "Real Estate Development", 0.0, preco=3.0, dy=74.0, pl=2.0, pvp=0.5, roe=10.0)]
ROWS[6]["st"] = {"roe": "red"}
CAD = {"PETR": ["PETROLEO BRASILEIRO S.A. PETROBRAS", "Exploração. Refino e Distribuição"], "VALE": ["VALE S.A.", "Minerais Metálicos"],
       "ITUB": ["ITAU UNIBANCO HOLDING S.A.", "Bancos"], "BBDC": ["BCO BRADESCO S.A.", "Bancos"], "BBAS": ["BCO BRASIL S.A.", "Bancos"],
       "BBSE": ["BB SEGURIDADE PARTICIPAÇÕES S.A.", "Seguradoras"], "WEGE": ["WEG S.A.", "Motores . Compressores e Outros"],
       "MGLU": ["MAGAZINE LUIZA S.A.", "Eletrodomésticos"], "CMIG": ["CIA ENERGETICA DE MINAS GERAIS - CEMIG", "Energia Elétrica"],
       "TAEE": ["TRANSMISSORA ALIANÇA DE ENERGIA ELÉTRICA S.A.", "Energia Elétrica"], "CYRE": ["CYRELA BRAZIL REALTY S.A.", "Incorporações"]}
M = {"PETR4": {"ret1": 85.4, "ret5": 92.3, "anual": {"2024": 20.8, "2025": 10.0}}, "VALE3": {"ret1": -5.0, "ret5": -20.0, "anual": {"2024": -15.0}},
     "ITUB4": {"ret1": 39.8, "ret5": 60.0, "anual": {"2024": 12.0}}, "MGLU3": {"ret1": -40.0, "ret5": -95.0, "anual": {"2024": -50.0}}}
D = chat.build(ROWS, FIELDS, M, CAD)
CALLS = []


def ret_fn(di, df, T):
    CALLS.append((di, df, tuple(T)))
    return {**{t: 5.0 for t in T}, "@ibov": 8.0, "@cdi": 11.0, "@usd": -2.0}


def ask(q, hist=None):
    P = chat.parse(q, D, hist)
    return P, chat.local(q, D, ret_fn, {}, P)


def test_metric_lookup_many_phrasings():
    for q in ("DY do PETR4", "dy da petr4", "qual o dividend yield da petrobras", "quanto paga de dividendos a Petrobras?",
              "petrobrás dividendos", "dy petr 4", "divdendo da petr4", "rendimento em dividendos da petrobras"):
        P, a = ask(q)
        assert P["tickers"] == ["PETR4"] and P["metrics"] == ["dy"], q
        assert "PETR4" in a and "6,50%" in a, (q, a)


def test_company_with_several_classes_is_one_entity():
    P, a = ask("valor de mercado da petrobras")  # antes: virava comparação PETR3 x PETR4
    assert P["tickers"] == ["PETR4"] and "R$ 760,0 bi" in a


def test_class_on_pn_unit():
    assert ask("itau ON")[0]["tickers"] == ["ITUB3"]
    assert ask("dy do itau pn")[0]["tickers"] == ["ITUB4"]
    assert ask("PETR9")[0]["tickers"] == ["PETR4"]


def test_nicknames_and_names():
    assert ask("margem da WEG")[0]["tickers"] == ["WEGE3"]
    assert ask("magalu p/l")[0]["tickers"] == ["MGLU3"]
    assert ask("banco do brasil roe")[0]["tickers"] == ["BBAS3"]
    assert ask("bb seguridade dy")[0]["tickers"] == ["BBSE3"]
    assert ask("cemig dy")[0]["tickers"] == ["CMIG4"]
    assert ask("taesa p/l")[0]["tickers"] == ["TAEE11"]
    assert sorted(ask("vale ou itau, qual melhor")[0]["tickers"]) == ["ITUB4", "VALE3"]


def test_common_words_are_not_companies():
    assert ask("vale a pena comprar PETR4?")[0]["tickers"] == ["PETR4"]
    P, _ = ask("ações com lucro positivo e p/vp menor que 1")
    assert P["tickers"] == [] and ("lpa", ">", 0) in P["filters"] and ("pvp", "<=", 1.0) in P["filters"]
    assert ask("quero aplicar 1000 reais por mês")[0]["metrics"] == []  # "aplicar" não é P/L
    assert ask("mais 5 ações")[0].get("unknown_tickers") is None


def test_debt_metric_exists():
    P, a = ask("dívida da petrobras")
    assert P["metrics"] == ["dlpl"] and "Dív.Líq/Patrim.: 0,65" in a
    assert ask("endividamento da PETR4")[0]["metrics"] == ["dlpl"]


def test_several_metrics_and_tickers():
    P, a = ask("P/L e DY da PETR4")
    assert P["metrics"] == ["pl", "dy"] and "P/L: 5,40" in a and "Div. Yield: 6,50%" in a
    P, a = ask("DY PETR4 e VALE3")
    assert "Maior Div. Yield: VALE3" in a
    _, a = ask("petrobras ou vale, qual paga mais dividendos?")
    assert "Maior Div. Yield: VALE3" in a


def test_returns_and_periods():
    P, a = ask("PETR4 rendeu quanto em 1 ano?")
    assert "Variação de preço em 1 ano" in a and "+5,00%" in a
    P, _ = ask("PETR4 em 2024"); assert P["period"][:2] == ("2024-01-01", "2024-12-31")
    P, _ = ask("VALE3 de 2020 a 2023"); assert P["period"][:2] == ("2020-01-01", "2023-12-31")
    P, _ = ask("PETR4 desde 2020"); assert P["period"][0] == "2020-01-01"
    P, _ = ask("PETR4 na última semana"); assert P["period"][2] == "nos últimos 7 dias"
    P, a = ask("PETR4 vs Ibovespa 2 anos"); assert P["idx"] == ["@ibov"] and "Ibovespa: +8,00%" in a
    P, a = ask("quanto está o Itaú hoje"); assert "ITUB4 — Cotação: R$ 50,50 (+2,30% no dia)" in a
    _, a = ask("dolar hoje"); assert "Variação no dia" in a
    P, _ = ask("liquidez acima de 2000 mil"); assert P["period"] is None


def test_rankings_sector_filters():
    _, a = ask("qual o maior roe dos bancos")
    assert a.startswith("Maiores ROE — Bancos") and "ITUB4" in a and "CYRE3" not in a and "BBSE3" not in a
    _, a = ask("ações de bancos com dy acima de 8")
    assert "BBAS3" in a and "ITUB4" not in a and "Div. Yield ≥ 8,00%" in a
    _, a = ask("quais as 3 ações com maior dividend yield")
    assert "SYNE3" not in a and "Mostrando 3" in a  # DY ≥ 40% fora (como nos grupos)
    _, a = ask("menores P/L")
    assert a.index("BBAS3") < a.index("PETR4") and "PETR3" not in a  # 1 ticker por empresa
    _, a = ask("ações com ROE acima de 20 e P/L abaixo de 8")
    assert "PETR4" in a and "WEGE3" not in a
    _, a = ask("empresas de energia com dy maior que 6")
    assert "CMIG4" in a and "TAEE11" in a
    _, a = ask("maiores altas em 2024"); assert a.startswith("Maiores altas em 2024") and a.index("PETR4") < a.index("ITUB4")
    _, a = ask("maiores quedas hoje"); assert a.startswith("Maiores quedas no dia")
    _, a = ask("piores em 5 anos"); assert a.startswith("Maiores quedas em 5 anos") and a.index("MGLU3") < a.index("VALE3")
    _, a = ask("quais as maiores empresas da bolsa"); assert "1. PETR4" in a


def test_follow_up_uses_conversation():
    h = [{"r": "u", "t": "DY do PETR4"}, {"r": "a", "t": "PETR4 — Div. Yield: 6,50%"}]
    P, a = ask("e o P/L?", h); assert P["tickers"] == ["PETR4"] and "P/L: 5,40" in a
    P, a = ask("e a VALE3?", h); assert P["tickers"] == ["VALE3"] and P["metrics"] == ["dy"]
    P, _ = ask("maiores DY", h); assert P["tickers"] == []  # ranking não herda a ação
    P, _ = ask("o que é DY", h); assert P["tickers"] == []


def test_definitions_colors_howto():
    assert ask("o que é P/L")[1].startswith("P/L")
    assert ask("oq é pvp")[1].startswith("P/VP")
    assert ask("o que é ebitda")[1].startswith("EBITDA")
    assert ask("ebitda?")[1].startswith("EBITDA")
    assert ask("o que é jcp")[1].startswith("JCP")
    assert "Cores" in ask("pq o card ta vermelho")[1]
    assert ask("como usar a aba comparar")[1].startswith("Comparar:\n1.")
    assert ask("onde fica o botão de exportar")[1].startswith("Exportar (CSV)")
    assert ask("como funciona o consenso")[1].startswith("Regras de mescla")
    assert ask("como uso a carteira")[1].startswith("Carteira:\n1.")
    assert ask("como adicionar uma posição na carteira")[1].startswith("Carteira:\n1.")
    assert "Abaixo🔔" in ask("como criar alerta de preço")[1]
    assert ask("o que é consenso")[1].startswith("Regras de mescla")
    assert "Graham" in ask("o que é graham")[1]
    assert ask("o que é on e pn")[1].startswith("ON, PN e Unit")
    assert ask("bom dia")[1].startswith("Olá")
    assert ask("como instalar o app no celular")[1].startswith("Instalar o app")


def test_fake_labels_only_for_site_buttons():
    assert ask("onde fica o botão de imprimir")[1].startswith("Não encontrei a opção")
    assert "Importar grupos" in ask("onde fica o botão de importar")[1]  # existe (↑ na aba Grupos)
    assert ask("tem o botão modo escuro?")[1].startswith("Não encontrei a opção")
    assert not (ask("qual opção mais barata entre PETR4 e VALE3")[1] or "").startswith("Não encontrei a opção")
    assert not (ask("menu de setores")[1] or "").startswith("Não encontrei a opção")


def test_open_questions_go_to_ai():
    for q in ("vale ou itau, qual melhor", "o roe do banco do brasil ta errado", "qual empresa tem o maior lucro",
              "explique o que é roic e por que importa"):
        assert ask(q)[1] is None, q


def test_single_source_guide():
    """Passo a passo, glossário, cores e nomes de botões vêm do painel ⓘ / da interface — o chat não tem cópia própria."""
    secs = chat.guide_sections()
    assert all(t in secs and secs[t] for _, ts in chat.HOWTO_KEYS for t in ts)  # toda seção citada pelo chat existe no painel
    G = chat.glossary(); assert all(t in G for t in set(chat.GLOSS_SYN.values()) if t not in ("graham", "magic formula"))
    assert "Importar grupos" in chat.ui_labels() and "Reorganizar" in chat.ui_labels()
    for name in ("GLOSS", "HOWTO", "LABELS", "COLORS"): assert not hasattr(chat, name)


def test_unknown_ticker_suggests():
    _, a = ask("XPTO3 dy")
    assert a.startswith("Não encontrei XPTO3")


# ---------- caminho da IA (Gemini simulado) ----------
class Resp:
    def __init__(self, payload, code=200): self.status_code, self._p = code, payload
    def json(self): return self._p


def _gem(text, grounding=None):
    c = {"content": {"parts": [{"text": text}]}}
    if grounding: c["groundingMetadata"] = {"groundingChunks": [{"web": {"uri": "https://ri.exemplo.com", "title": "RI"}}]}
    return Resp({"candidates": [c], "usageMetadata": {"promptTokenCount": 10}})


def _with_ai(fake):
    os.environ["GEMINI_API_KEY"] = "x"; old = chat.requests.post; chat.requests.post = fake
    chat.LOG_FILE = os.path.join(tempfile.mkdtemp(), "chat_log.jsonl"); chat._QA.clear()
    return old


def _restore(old):
    chat.requests.post = old; os.environ.pop("GEMINI_API_KEY", None)


def test_ai_interprets_and_python_computes():
    sent = []

    def fake(url, headers=None, json=None, timeout=None):
        sent.append((url, json, timeout))
        assert json["generationConfig"]["responseMimeType"] == "application/json"
        return _gem('{"tipo":"ranking","acoes":[],"indicadores":["dy"],"setor":"Bancos","filtros":[],"ordem":"desc","n":2}')
    old = _with_ai(fake)
    try:
        out = chat.answer2("quais bancos pagam os dividendos mais gordos", [], D, ret_fn, {})
    finally:
        _restore(old)
    assert out["mode"] == "ia+dados" and out["a"].startswith("Maiores Div. Yield — Bancos") and "1. BBAS3" in out["a"]
    assert all(t <= 25 for _, _, t in sent)
    rec = json.loads(open(chat.LOG_FILE).read().splitlines()[-1])
    assert rec["mode"] == "ia+dados" and rec["q"].startswith("quais bancos")


def test_ai_open_question_and_complaint_web():
    def fake(url, headers=None, json=None, timeout=None):
        if "tools" in json: return _gem("Segundo o RI, o ROE é 11%.", grounding=True)
        if json["generationConfig"].get("responseMimeType"): return _gem('{"tipo":"analise"}')
        return _gem("A PETR4 tem P/L menor.")
    old = _with_ai(fake)
    try:
        a1 = chat.answer2("vale a pena comprar PETR4?", [], D, ret_fn, {})
        a2 = chat.answer2("o roe do banco do brasil ta errado", [], D, ret_fn, {})
        a3 = chat.answer2("ROE do Banco do Brasil e por que diverge", [], D, ret_fn, {})  # indicador sem maioria -> busca web
    finally:
        _restore(old)
    assert a1["mode"] == "gemini" and a1["a"] == "A PETR4 tem P/L menor."
    assert a2["mode"] == "gemini+web" and "Fontes da web" in a2["a"]
    assert a3["mode"] == "gemini+web"


def test_ai_failure_falls_back_to_rules_and_respects_deadline():
    calls = []

    def fake(url, headers=None, json=None, timeout=None):
        calls.append(timeout); return Resp({}, 503)
    old = _with_ai(fake)
    try:
        out = chat.answer2("ações mais baratas pelo P/L dos bancos", [], D, ret_fn, {})
    finally:
        _restore(old)
    assert out["mode"] == "regras" and "Bancos" in out["a"] and len(calls) <= 8 and out.get("sug")


def test_no_ai_gives_suggestions():
    chat._QA.clear(); chat.LOG_FILE = os.path.join(tempfile.mkdtemp(), "chat_log.jsonl")
    out = chat.answer2("qual empresa tem o maior lucro", [], D, ret_fn, {})
    assert out["mode"] == "regras" and out["a"].startswith("Não consegui entender") and len(out["sug"]) >= 3
    assert chat.read_log(10, "sem_resposta")[0]["q"] == "qual empresa tem o maior lucro"



def test_pop_culture_links_company_and_topics():
    def fake(url, headers=None, json=None, timeout=None):
        if json["generationConfig"].get("responseMimeType"): return _gem('{"tipo":"analise"}')
        txt = json["contents"][-1]["parts"][0]["text"]
        return _gem("O GTA é da Take-Two, negociada na Nasdaq.\n[[EMPRESA:TTWO:us]]" if "gta" in txt.lower() else "Não sei do que se trata.\n[[ASSUNTO]]")
    ext = lambda t, c: {"ticker": t, "nome": "Take-Two Interactive", "var": 1.0, "cur": "USD", "pais": "Estados Unidos", "preco": 200.0, "valmerc": 3.9e10, "pl": None} if (t, c) == ("TTWO", "us") else None
    old = _with_ai(fake)
    try:
        chat._QA.clear()
        a1 = chat.answer2("E o gta?", [], D, ret_fn, {}, ext)
        a2 = chat.answer2("e aquele lance do zorbax?", [], D, ret_fn, {}, ext)
    finally:
        _restore(old)
    assert "[[" not in a1["a"] and "TTWO" in a1["a"] and "200,00 USD" in a1["a"] and "Deseja mais alguma informação" in a1["a"]
    assert "[[" not in a2["a"] and [x["l"] for x in a2["sug"]][-1] == "Outros"
    assert a2["sugl"] == "Está falando sobre:" and all(x["q"] == "e aquele lance do zorbax?" and x["topic"] for x in a2["sug"])


def test_topic_resends_same_question_with_context():
    seen = []
    def fake(url, headers=None, json=None, timeout=None):
        seen.append((json["systemInstruction"]["parts"][0]["text"], json["contents"][-1]["parts"][0]["text"]))
        return _gem("Eleições costumam mexer com estatais e bancos.")
    old = _with_ai(fake)
    try:
        chat._QA.clear()
        out = chat.answer2("e as eleições?", [], D, ret_fn, {}, None, None, "Política")
    finally:
        _restore(old)
    sys_t, q = seen[-1]
    assert q == "e as eleições?" and "tema Política" in sys_t and "assunto:" not in q and out["mode"] == "gemini"
    assert "Busca na web indisponível" not in open(chat.__file__, encoding="utf-8").read()



def test_weak_points_fixed():
    ROWS[0]["ix"] = {"IBOV": [1.0]}; ROWS[2]["ix"] = {"IBOV": [1.0]}  # PETR4 e VALE3 no Ibovespa
    a = ask("qual a ação mais barata do ibov?")[1]
    assert a and "Menores P/L — IBOV" in a and "PETR4" in a and "ITUB4" not in a
    P, a = ask("ações com roe acima de 20 e divida baixa")
    assert ("dlebit", "<=", 2) in P["filters"] and ("roe", ">=", 20) in P["filters"] and "≤ 2,00" in a
    a = ask("bbas3 caiu pq hj?")[1]
    assert a.startswith("BBAS3: +1,60% hoje") and "não sabe o motivo" in a
    P = chat.parse("quanto ta o dolar hoje", D)
    a = chat.local("quanto ta o dolar hoje", D, ret_fn, {}, P, lambda k: ("2026-10-09", 5.43) if k == "@usd" else None)
    assert a == "Dólar: R$ 5,43 (fechamento de 09/10/2026)" and chat.suggestions(P, D)[0] == "Dólar rendeu quanto em 1 ano?"
    a = ask("compara itau e bradesco")[1]
    assert a.startswith("Comparação ") and "ITUB4" in a and "BBDC4" in a and "Resumo: BBDC4 se sai melhor em 3 de 4" in a and "melhor:" in a
    assert ask("ações mais baratas")[1].startswith("Menores P/L")




def test_knowledge_and_methods():
    k = chat.kb_context("e o barsi?")
    assert "Luiz Barsi Filho" in k and "TAEE11" in k
    assert "Take-Two" in chat.kb_context("e o gta 6?") and "Campeões da Copa" in chat.kb_context("quem ganhou a copa de 2014")
    assert chat.kb_context("bom dia") == ""
    a = chat.local("como monto uma carteira pelo método Barsi?", D, ret_fn, {})
    assert a.startswith("Método Barsi:") and "critérios aproximados" in a
    assert chat.local("o que é o método graham", D, ret_fn, {}).startswith("Método Graham:")
    assert chat.local("quais métodos de investimento existem?", D, ret_fn, {}).startswith("Métodos de investimento")


def test_ai_down_answers_fast_from_knowledge():
    calls = []
    def fake(url, headers=None, json=None, timeout=None):
        calls.append(url); return Resp({}, 503)
    old = _with_ai(fake)
    try:
        chat._DOWN["until"] = 0; t0 = time.time()
        out = chat.answer2("E o goku?", [], D, ret_fn, {}, None)
        out2 = chat.answer2("e o naruto?", [], D, ret_fn, {}, None)
    finally:
        _restore(old); chat._DOWN["until"] = 0
    assert "Dragon Ball" in out["a"] and "sites especializados" in out["a"] and time.time() - t0 < 5
    assert "Naruto" in out2["a"] and len(calls) <= 2  # depois do 503, não tenta a IA de novo por 2 min

def test_slang_typos_and_synonyms():
    for q, k in (("vacas leiteiras dos bancos", "dy"), ("blue chips", "valmerc"), ("ações lucrativas", "roe"), ("dy da petrobars", "dy")):
        assert ask(q)[0]["metrics"] == [k], q
    assert ask("dy da petrobars")[0]["tickers"] == ["PETR4"] and ask("dividendos do bradesko")[0]["tickers"] == ["BBDC4"]
    P, a = ask("quais ações estão sangrando em 2024")
    assert a.startswith("Maiores quedas em 2024") and "MGLU3" in a
    assert ask("ações em conta")[1].startswith("Menores P/L")
    assert ask("o que é vaca leiteira")[1].startswith("Vaca leiteira:")
    V = json.load(open(os.path.join(os.path.dirname(chat.__file__), "vocabulario.json"), encoding="utf-8"))  # fonte única do vocabulário
    assert chat.SYN["pl"] == V["sinonimos"]["pl"] and chat.ALIAS == V["apelidos"] and "vaca leiteira" in chat.SYN["dy"]


def test_offline_base_search_and_variety():
    old = chat._WIKI.copy()
    chat._WIKI.update(t=time.time(), d={"animes|dragon ball": {"t": "Dragon Ball", "x": "Dragon Ball é uma franquia de mídia japonesa criada por Akira Toriyama. "
                                         "Começou como mangá em 1984. Virou anime pela Toei Animation. É uma das séries mais vendidas."}})
    chat._IX["key"] = None
    try:
        h = []
        a1 = chat.kb_answer("e o goku?", None, h); h += [{"r": "u", "t": "e o goku?"}, {"r": "a", "t": a1}]
        a2 = chat.kb_answer("e o goku?", None, h)
        assert a1 != a2 and "Wikipédia" in a2 and "sites especializados" in a1 and "sites especializados" in a2
        assert "franquia de mídia japonesa" in chat.kb_context("e o goku?")
    finally:
        chat._WIKI.clear(); chat._WIKI.update(old); chat._IX["key"] = None
    P = chat.parse("onde vejo os alertas de preço dos favoritos", D)
    assert "Favoritos" in chat.rules(P["q"], D, ret_fn, P)
    P = chat.parse("qual empresa tem o maior lucro", D)
    assert chat.rules(P["q"], D, ret_fn, P).startswith("Não consegui entender")  # uma palavra só não basta para a busca
    h = [{"r": "u", "t": "oi"}]
    seen = set()
    for _ in range(3):
        a = chat.local("oi", D, ret_fn, {}, chat.parse("oi", D, h)); seen.add(a); h += [{"r": "a", "t": a}, {"r": "u", "t": "oi"}]
    assert len(seen) == 3 and all(x.startswith("Olá") for x in seen)


def _with_wiki(d):
    old = (chat._WIKI.copy(), chat._NM.get("key"))
    chat._WIKI.update(t=time.time(), d=d); chat._NM["key"] = None; chat._IX["key"] = None
    return old


def _restore_wiki(old):
    chat._WIKI.clear(); chat._WIKI.update(old[0]); chat._NM["key"] = None; chat._IX["key"] = None


WIKI = {"animes|dragon ball": {"t": "Dragon Ball", "x": "Dragon Ball é uma franquia japonesa.", "al": ["Dragon Ball Z"],
                               "p": [{"n": "Kuririn", "a": ["Krillin"], "d": "melhor amigo de Goku"}, {"n": "Son Goku", "a": []}, {"n": "Sakura"}]},
        "animes|naruto": {"t": "Naruto", "x": "Naruto é um mangá.", "p": [{"n": "Sakura Haruno", "a": ["Sakura"]}, {"n": "Sasuke Uchiha"}]},
        "filmes|homem-aranha": {"t": "Homem-Aranha", "x": "", "c": [{"n": "Tom Holland", "d": "ator britânico"}]},
        "filmes|vingadores: ultimato": {"t": "Vingadores", "x": "", "c": [{"n": "Tom Holland", "d": "ator britânico"}]}}


def test_characters_cast_and_ambiguity():
    old = _with_wiki(WIKI)
    ext = lambda t, c: {"ticker": t, "nome": "Toei Animation", "pais": "Japão", "bolsa": "Bolsa de Tóquio", "indice": "Nikkei 225",
                        "preco": 2911.0, "var": 2.46, "cur": "JPY", "valmerc": 5.9e11, "pl": 23.0} if t == "4816" else None
    try:
        for q in ("E o kuririn?", "e o kulilin?", "e o krillin?"):
            a = chat.kb_answer(q, ext, [])
            assert a and "Kuririn: personagem de Dragon Ball" in a, (q, a)
        a = chat.kb_answer("E o kuririn?", ext, [])
        i_who, i_emp, i_fora, i_fim = (a.index("Kuririn"), a.index("Toei Animation (4816)"), a.index("sites especializados"),
                                       a.index("Deseja mais alguma informação"))
        assert i_who < i_emp < i_fora < i_fim and "Japão · Bolsa de Tóquio · índice Nikkei 225" in a  # ordem: quem é, ação, sites, pergunta
        a = chat.kb_answer("quem é tom holland?", None, [])
        assert "Tom Holland: ator britânico; atuou em" in a and "Homem-Aranha" in a and "Vingadores" in a  # ator em 2 filmes: não pergunta
        amb = chat.kb_ambiguous("e a sakura?")
        assert amb and "Está falando de qual?" in amb["a"] and {s["l"] for s in amb["sug"]} == {"Dragon Ball", "Naruto"}
        assert chat.kb_ambiguous("e a sakura de naruto?") is None  # a obra citada desfaz a dúvida
        k = [s["topic"] for s in amb["sug"] if s["l"] == "Naruto"][0]
        out = chat.answer2("e a sakura?", [], D, ret_fn, {}, None, None, k)  # botão escolhido: responde sobre a obra
        assert "Sakura Haruno: personagem de Naruto" in out["a"] and "Dragon Ball" not in out["a"]
        out = chat.answer2("e a sakura?", [], D, ret_fn, {}, None)
        assert out["a"].startswith("“Sakura") and len(out["sug"]) == 2
        assert chat.kb_ambiguous("dy da petr4") is None and "Kuririn" not in chat.kb_context("dividendos da taesa", ["TAEE11"], fuzzy=False)
    finally:
        _restore_wiki(old)


def test_ai_answer_order_moves_specialized_sites():
    ext = lambda t, c: {"ticker": "4816", "nome": "Toei Animation", "pais": "Japão", "bolsa": "Bolsa de Tóquio", "indice": "Nikkei 225", "preco": 2911.0}
    a = chat.link_ext({"a": "Goku é o protagonista de Dragon Ball. Para informações sobre entretenimento, procure sites especializados no assunto.\n"
                            "[[EMPRESA:4816:jp]]"}, "e o goku?", ext)["a"]
    assert a.index("protagonista") < a.index("(4816)") < a.index("sites especializados") < a.index("Deseja mais")
    assert "Para informações sobre entretenimento, procure sites especializados no assunto." in a


if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
