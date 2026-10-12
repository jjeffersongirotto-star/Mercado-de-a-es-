"""Testes do chat: perguntas reais escritas de vários jeitos. Rodar: python -m pytest tests/ (ou python tests/test_chat.py)."""
import os, sys, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.pop("GEMINI_API_KEY", None)
import chat

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
    assert ask("o que é consenso")[1].startswith("Regras de mescla")
    assert "Graham" in ask("o que é graham")[1]
    assert ask("o que é on e pn")[1].startswith("ON, PN e Unit")
    assert ask("bom dia")[1].startswith("Olá")


def test_fake_labels_only_for_site_buttons():
    assert ask("onde fica o botão de imprimir")[1].startswith("Não encontrei a opção")
    assert "Importar grupos" in ask("onde fica o botão de importar")[1]  # existe (↑ na aba Grupos)
    assert ask("tem o botão modo escuro?")[1].startswith("Não encontrei a opção")
    assert not (ask("qual opção mais barata entre PETR4 e VALE3")[1] or "").startswith("Não encontrei a opção")
    assert not (ask("menu de setores")[1] or "").startswith("Não encontrei a opção")


def test_open_questions_go_to_ai():
    for q in ("ações mais baratas", "vale ou itau, qual melhor", "o roe do banco do brasil ta errado", "qual empresa tem o maior lucro",
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


if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
