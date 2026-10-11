"""Chat sobre os dados do site: Gemini (se GEMINI_API_KEY no ambiente) com contexto montado aqui; senão, respostas por regras."""
import os, re, json, unicodedata, logging
from datetime import date, timedelta
import requests
log = logging.getLogger("chat")
IDX = {"@ibov": ["ibovespa", "ibov"], "@usd": ["dolar", "usd"], "@cdi": ["cdb", "cdi"], "@ipca": ["ipca", "inflacao"],
       "@poup": ["poupanca"], "@gold": ["ouro"]}
IDXN = {"@ibov": "Ibovespa", "@usd": "Dólar", "@cdi": "CDB 100% do CDI", "@ipca": "IPCA", "@poup": "Poupança", "@gold": "Ouro"}
MX = {"ret1": "valorização 1 ano (%)", "ret2": "valorização 2 anos (%)", "ret3": "valorização 3 anos (%)", "ret5": "valorização 5 anos (%)",
      "dy1": "DY médio 1 ano (%)", "prov12": "proventos 12m ÷ preço (%)", "avg1": "preço médio 1 mês", "v30": "volume médio 30 pregões (R$)"}
SYN = {"dividendo": "dy", "dy": "dy", "yield": "dy", "p/l": "pl", "pl": "pl", "preco/lucro": "pl", "p/vp": "pvp", "pvp": "pvp", "roe": "roe",
       "valor de mercado": "valmerc", "liquidez": "liq2m", "cotacao": "preco", "preco": "preco", "margem": "mliq", "divida": "divliq_pl",
       "valorizacao": "ret1", "subiu": "ret1", "rentabilidade": "ret1", "proventos": "prov12", "volume": "v30", "lpa": "lpa", "vpa": "vpa", "roic": "roic"}
def norm(s): return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
def br(x, d=2):
    if x is None: return "—"
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def build(rows, fields, metrics):
    F = {f[0]: (f[1], f[2]) for f in fields}
    by = {r["ticker"]: r for r in rows}
    return {"rows": rows, "F": F, "by": by, "M": metrics or {}}

def _tickers(q, D):
    up = re.findall(r"\b[A-Za-z]{4}\d{1,2}[A-Za-z]?\b", q)
    out = [t.upper() for t in up if t.upper() in D["by"]]
    nq = norm(q)
    if not out:  # nome da empresa
        for r in D["rows"]:
            n = norm(r.get("nome") or "").split(" ")[0]
            if len(n) >= 4 and re.search(r"\b" + re.escape(n) + r"\b", nq): out.append(r["ticker"])
    return list(dict.fromkeys(out))[:6]
def _idx(q):
    nq = norm(q); return [k for k, ws in IDX.items() if any(re.search(r"\b" + w + r"\b", nq) for w in ws)]
def _metric(q, D):
    nq = norm(q)
    for w, k in sorted(SYN.items(), key=lambda x: -len(x[0])):
        if w in nq:
            if k == "ret1":
                m = re.search(r"(\d)\s*anos?", nq); k = f"ret{m.group(1)}" if m and m.group(1) in "1235" else k
            return k
    return None
def _period(q):
    nq = norm(q); t = date.today()
    m = re.search(r"(\d+)\s*(ano|anos|mes|meses|dia|dias)", nq)
    if m:
        n = int(m.group(1)); u = m.group(2)
        d0 = t - timedelta(days=n * (365 if u.startswith("ano") else 30 if u.startswith("mes") else 1))
    else: d0 = t - timedelta(days=365)
    return d0.isoformat(), t.isoformat()
def val(D, r, k):
    if k in (r.get("v") or {}): return r["v"].get(k)
    return (D["M"].get(r["ticker"]) or {}).get(k)
def label(D, k): return D["F"].get(k, (MX.get(k, k), ""))[0]

def card(D, t):
    r = D["by"][t]; v = r.get("v") or {}; m = D["M"].get(t) or {}
    keys = [k for k in ("preco", "dy", "pl", "pvp", "roe", "roic", "mliq", "divliq_pl", "lpa", "vpa", "valmerc", "liq2m") if v.get(k) is not None]
    s = f"{t} — {r.get('nome','')} · {r.get('setor') or ''}\n" + "; ".join(f"{label(D,k)}: {br(v[k])}" for k in keys)
    st = r.get("st") or {}
    if st: s += "\nDivergência entre fontes: " + ", ".join(f"{label(D,k)} ({'sem maioria' if x == 'red' else 'maioria'})" for k, x in st.items())
    if r.get("ix"): s += "\nÍndices B3: " + ", ".join(r["ix"].keys())
    if r.get("tags"): s += "\nEtiquetas: " + ", ".join(r["tags"])
    mm = [f"{MX[k]}: {br(m[k])}" for k in MX if m.get(k) is not None]
    if mm: s += "\n" + "; ".join(mm)
    if m.get("ytd"): s += "\nProventos no ano: " + "; ".join(f"{e[0]} R$ {br(e[1],4)} ({e[2]})" for e in m["ytd"][:8])
    return s

def top(D, k, n=10, asc=None):
    lo = D["F"].get(k, ("", ""))
    asc = (k in ("pl", "pvp", "divliq_pl")) if asc is None else asc
    L = [(r, val(D, r, k)) for r in D["rows"]]
    L = [(r, x) for r, x in L if isinstance(x, (int, float)) and (k not in ("pl", "pvp") or x > 0)]
    L.sort(key=lambda z: z[1], reverse=not asc)
    return L[:n]

COLS = [("preco", 2), ("pl", 1), ("pvp", 2), ("dy", 1), ("roe", 1), ("roic", 1), ("mbruta", 0), ("mliq", 1), ("dlebit", 1), ("dlpl", 2),
        ("cresc5a", 0), ("lucro5a", 0), ("lpa", 2), ("valmerc", -6), ("liq2m", -3)]
def table(D, cx):
    tg = {}
    for it in str(cx.get("tags") or "").split(";"):
        if ":" in it: a, b = it.split(":", 1); tg[a] = b
    head = "ticker,nome,setor,var_dia%,P/L,P/VP,DY%,ROE%,ROIC%,MargBruta%,MargLiq%,DivLiq/EBIT,DivLiq/PL,CrescReceita5a%,CrescLucro5a%,LPA,ValorMercado(R$mi),Liquidez2m(R$mil),preco,ret1a%,indices,etiquetas|confianca"
    out = [head]
    for r in D["rows"]:
        v = r.get("v") or {}; m = D["M"].get(r["ticker"]) or {}
        def f(k, d):
            x = v.get(k)
            if not isinstance(x, (int, float)): return ""
            if d < 0: return str(round(x / 10 ** -d))
            return str(round(x, d)) if d else str(round(x))
        cells = [r["ticker"], (r.get("nome") or "")[:22].replace(",", " "), (r.get("setor") or "")[:20].replace(",", " "),
                 str(round(r["var"], 1)) if isinstance(r.get("var"), (int, float)) else ""] + [f(k, d) for k, d in COLS if k != "preco"] + \
                [f("preco", 2), str(round(m["ret1"])) if isinstance(m.get("ret1"), (int, float)) else "", "/".join((r.get("ix") or {}).keys()), tg.get(r["ticker"], "")]
        out.append(",".join(cells))
    return "\n".join(out)

def context(q, D, ret_fn, cx=None):
    cx = cx or {}
    parts = ["TABELA DE TODAS AS AÇÕES (CSV; vazio = sem dado):\n" + table(D, cx)]
    if cx.get("groups"): parts.append("GRUPOS PRONTOS DO SITE (top 10):\n" + str(cx["groups"])[:8000])
    try:
        from datetime import date as _d, timedelta as _t
        R = ret_fn((_d.today() - _t(days=365)).isoformat(), _d.today().isoformat(), [])
        parts.append("ÍNDICES, variação em 1 ano: " + "; ".join(f"{IDXN[k]} {br(R[k],1)}%" for k in IDXN if k in R))
    except Exception: pass
    for k, lab in (("prev", "PREVISÃO RENTABILIDADE (entradas do usuário, JSON)"), ("prevRes", "PREVISÃO RENTABILIDADE (resultado na tela)"),
                   ("alug", "PREVISÃO ALUGUEL (entradas, JSON)"), ("alugRes", "PREVISÃO ALUGUEL (resultado na tela)"),
                   ("comp", "COMPARAR (seleção, JSON)"), ("compRes", "COMPARAR (resultado na tela)")):
        if cx.get(k): parts.append(lab + ":\n" + str(cx[k])[:5000])
    T = _tickers(q, D); I = _idx(q)
    for t in T[:3]: parts.append("DETALHE " + card(D, t))
    if T or I:
        di, df = _period(q); R = ret_fn(di, df, T)
        parts.append(f"Variação no período {di} a {df}: " + "; ".join(f"{IDXN.get(x, x)} {br(R.get(x))}%" for x in T + I if x in R))
    return "\n\n".join(parts)[:300000], T, I, None

def context_old(q, D, ret_fn):
    T = _tickers(q, D); I = _idx(q); k = _metric(q, D); parts = []
    for t in T: parts.append(card(D, t))
    if T or I:
        di, df = _period(q); R = ret_fn(di, df, T)
        parts.append(f"Variação no período {di} a {df}: " + "; ".join(f"{IDXN.get(x, x)} {br(R.get(x))}%" for x in T + I if x in R))
    if k and not T:
        for asc in ((False, True) if k in ("pl", "pvp") else (False,)):
            parts.append(f"Top 10 por {label(D,k)} ({'menor' if (k in ('pl','pvp','divliq_pl')) else 'maior'} primeiro): " + "; ".join(f"{r['ticker']} {br(x)}" for r, x in top(D, k, 10)))
            break
    if not parts:
        parts.append("Top 10 DY: " + "; ".join(f"{r['ticker']} {br(x)}" for r, x in top(D, "dy")))
        parts.append("Top 10 valorização 1 ano: " + "; ".join(f"{r['ticker']} {br(x)}" for r, x in top(D, "ret1")))
        parts.append(f"Total de ações no site: {len(D['rows'])}")
    return "\n\n".join(parts), T, I, k

def rules(q, D, ret_fn):
    T = _tickers(q, D); I = _idx(q); k = _metric(q, D); nq = norm(q)
    if len(T) + len(I) >= 2 or (I and not k):
        di, df = _period(q); R = ret_fn(di, df, T)
        items = [(IDXN.get(x, x), R.get(x)) for x in T + I]
        items.sort(key=lambda z: -(z[1] if z[1] is not None else -1e9))
        return f"Variação de {di[8:]}/{di[5:7]}/{di[:4]} a {df[8:]}/{df[5:7]}/{df[:4]}:\n" + "\n".join(f"• {a}: {br(b)}%" if b is not None else f"• {a}: sem dados" for a, b in items)
    if T:
        t = T[0]
        if k:
            x = val(D, D["by"][t], k)
            return f"{t} — {label(D,k)}: {br(x)}" if x is not None else f"Não tenho {label(D,k)} de {t}."
        return card(D, t)
    if k:
        n = int((re.search(r"\b(\d{1,2})\b", nq) or [0, 10])[1]); asc = any(w in nq for w in ("menor", "menores", "baratas", "pior", "piores"))
        if k in ("pl", "pvp"): asc = not any(w in nq for w in ("maior", "maiores"))
        L = top(D, k, max(1, min(n, 30)), asc)
        return f"{'Menores' if asc else 'Maiores'} {label(D,k)}:\n" + "\n".join(f"{i+1}. {r['ticker']} ({(r.get('nome') or '')[:28]}): {br(x)}" for i, (r, x) in enumerate(L))
    return ("Não entendi. Exemplos: “DY do BBAS3”, “maiores dividend yield”, “PETR4 vs Ibovespa 2 anos”, “menores P/L”, "
            "“o que é VALE3?”.")

def gemini(q, ctx, hist):
    key = os.environ.get("GEMINI_API_KEY")
    if not key: raise RuntimeError("sem chave")
    models = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-3.5-flash", "gemini-3.1-flash-lite"] if m]
    sys_t = ("Você é o assistente do site Screener B3. Responda em português do Brasil, de forma concisa, usando SOMENTE os dados abaixo "
             "(dados do site: tabela de todas as ações, grupos, índices e o que o usuário preencheu em Previsão e Comparar). "
             "Você pode filtrar, ranquear e cruzar critérios na tabela (ex.: P/L baixo + LPA positivo + crescimento) e deve explicar os critérios usados. "
             "Diga quais ações atendem aos critérios, sem recomendação personalizada de investimento. Se um dado não estiver aqui, diga que o site não tem. "
             "Números no formato brasileiro.\n\nDADOS DO SITE:\n" + ctx)
    contents = [{"role": "user" if h.get("r") == "u" else "model", "parts": [{"text": str(h.get("t", ""))[:1500]}]} for h in (hist or [])[-6:]]
    contents.append({"role": "user", "parts": [{"text": q[:1000]}]})
    err = None
    tries = [(m, True) for m in models] + [("gemini-flash-latest", False)]  # sem raciocínio (rápido); por último, com raciocínio padrão
    for model, think0 in tries:  # modelo indisponível/sobrecarregado: tenta o próximo
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                              json={"systemInstruction": {"parts": [{"text": sys_t}]}, "contents": contents,
                                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3000, **({"thinkingConfig": {"thinkingBudget": 0}} if think0 else {})}}, timeout=90)
        except requests.RequestException as e:
            err = type(e).__name__; continue
        if r.status_code != 200: err = f"http {r.status_code}"; continue
        c = r.json()["candidates"][0]["content"]["parts"]
        t = "".join(p.get("text", "") for p in c if not p.get("thought")).strip()
        if t: return t
        err = "vazio"
    raise RuntimeError(f"gemini {err}")

def answer(q, hist, D, ret_fn, cx=None):
    try:
        ctx = context(q, D, ret_fn, cx)[0]
        return {"a": gemini(q, ctx, hist), "mode": "gemini"}
    except Exception as e:
        log.info("chat fallback: %s", str(e)[:80])
        return {"a": rules(q, D, ret_fn), "mode": "regras"}


# ================= Economia de tokens: respostas locais, contexto relevante, cache diário =================
import hashlib, html as _html, time as _time
_GUIDE = None
def guide():
    """Guia do site extraído do painel ⓘ (index.html)."""
    global _GUIDE
    if _GUIDE is None:
        try:
            s = open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8").read()
            i = s.index('<div id="infoModal"'); j = s.index("<script", i); t = s[i:j]
            t = re.sub(r"<(summary|h\d)[^>]*>", "\n## ", t); t = re.sub(r"<li[^>]*>", "\n- ", t); t = re.sub(r"<[^>]+>", "", t)
            t = _html.unescape(t); t = re.sub(r"[ \t]+", " ", t); _GUIDE = re.sub(r"\n\s*\n+", "\n", t).replace("✕", "").strip()
        except Exception: _GUIDE = ""
    return _GUIDE
def guide_sections():
    out, cur = {}, None
    for l in guide().split("\n"):
        if l.startswith("## "): cur = l[3:].strip(); out[cur] = []
        elif cur: out[cur].append(l)
    return {k: "\n".join(v).strip() for k, v in out.items()}

GLOSS = {
    "p/l": "P/L (preço/lucro): preço da ação ÷ lucro por ação. Quantos anos de lucro atual pagariam o preço; menor = mais barata (só faz sentido com lucro positivo).",
    "p/vp": "P/VP (preço/valor patrimonial): preço ÷ patrimônio líquido por ação. Abaixo de 1 = negocia abaixo do patrimônio contábil.",
    "dy": "DY (dividend yield): proventos pagos nos últimos 12 meses ÷ preço da ação, em %.",
    "dividend yield": "DY (dividend yield): proventos pagos nos últimos 12 meses ÷ preço da ação, em %.",
    "roe": "ROE (retorno sobre o patrimônio): lucro líquido ÷ patrimônio líquido, em %. Mede a rentabilidade do capital dos acionistas.",
    "roic": "ROIC (retorno sobre o capital investido): lucro operacional após impostos ÷ capital investido (dívida + patrimônio), em %.",
    "lpa": "LPA (lucro por ação): lucro líquido dos últimos 12 meses ÷ número de ações.",
    "vpa": "VPA (valor patrimonial por ação): patrimônio líquido ÷ número de ações.",
    "ev/ebitda": "EV/EBITDA: valor da firma (valor de mercado + dívida líquida) ÷ EBITDA. Menor = mais barata em relação à geração de caixa operacional.",
    "ev/ebit": "EV/EBIT: valor da firma ÷ EBIT (lucro operacional).",
    "psr": "PSR: valor de mercado ÷ receita líquida dos últimos 12 meses.",
    "margem liquida": "Margem líquida: lucro líquido ÷ receita líquida, em %.",
    "margem bruta": "Margem bruta: lucro bruto ÷ receita líquida, em %.",
    "liquidez": "Liquidez (2 meses): volume financeiro médio negociado por dia na bolsa nos últimos 2 meses, em R$.",
    "cdi": "CDI: taxa de juros entre bancos, referência da renda fixa. No site os gráficos usam 'CDB 100% do CDI' (CDI diário acumulado).",
    "ipca": "IPCA: índice oficial de inflação do Brasil (IBGE), mensal.",
    "graham": "Preço justo de Graham = √(22,5 × LPA × VPA). 'Baratas pelo Graham' = maior desconto do preço em relação a esse valor (só LPA>0, VPA>0, P/L≥2).",
    "magic formula": "Magic Formula (Greenblatt): soma do ranking de earnings yield (EBIT/EV) e do ranking de ROIC; menor soma = melhor posição.",
    "consenso": "Consenso entre fontes: para cada indicador o site compara as fontes (Fundamentus, Status Invest etc.) e exibe o valor da maioria; cores indicam divergência.",
    "bonificacao": "Bonificação: a empresa entrega ações novas aos acionistas (registrada pela B3 como BONIFICAÇÃO). Desdobramento/grupamento só mudam quantidade e preço.",
}
COLORS = ("Cores no site: verde = positivo/ganho/confirmar; vermelho = negativo/perda/sem maioria entre as fontes; âmbar/laranja = maioria com divergência; "
          "azul = informação/EBIT ajustado; azul-escuro = bancos/seguradoras (indicador não comparável); violeta = Valorização total na Previsão; "
          "amarelo = imposto (Previsão).")
HOWTO = [
 (("previsao aluguel","previsao de aluguel","aluguel"), "Previsão aluguel:\n1. Abra a aba Previsão e toque em Previsão aluguel.\n2. Toque em ＋ Ação, busque a ação e informe Quantidade, Adições mensais, Prazo e % não alugado.\n3. A Taxa (% a.a.) vem preenchida com a taxa de aluguel da B3 (se indisponível, digite-a); confirme com ✓.\n4. Ajuste a Taxa da corretora e marque 'Descontar automaticamente taxa da corretora + IR 15%' se quiser.\n5. A tabela mostra o valor recebido mês a mês; use ✏ Editar/Excluir em cada ação."),
 (("previsao rentab","rentabilidade","previsao","simula"), "Previsão rentabilidade:\n1. Abra a aba Previsão (sub-aba Previsão rentabilidade).\n2. Em Referências, preencha Valor inicial, Aporte mensal, Dividendos e Rentabilidade (MÊS ou ANO) e o Imposto s/ dividendo.\n3. Em Projeções, busque uma empresa para usar os números dela; ou em 'E se eu tivesse investido?' escolha a ação e a Data inicial/final para simular com o histórico real.\n4. Use + em Aportes extraordinários e Retiradas extraordinárias para lançamentos avulsos.\n5. A tabela mostra mês a mês (imposto em amarelo, Valorização total em violeta); toque em Mostrar mais meses para continuar."),
 (("compar",), "Aba Comparar:\n1. Abra a aba Comparar.\n2. Em 'Buscar ação ou índice principal…' escolha a referência.\n3. Em 'Adicionar ação ou índice…' inclua as outras para comparar.\n4. O resultado separa as colunas Renderam menos e Renderam mais que a principal; use 'Filtrar…' em cada coluna e o botão Remover para tirar itens."),
 (("favorit",), "Favoritos:\n1. Na aba Ações, toque na ☆ do card para favoritar (ele vai para o topo da lista); toque em ★ para remover.\n2. Na aba Grupos, toque na ☆ de um grupo para favoritá-lo; ele aparece em ★ Favoritados.\n3. Ficam salvos no seu navegador."),
 (("reorganiz","arrastar","reordenar"), "Reorganizar:\n1. Na aba Grupos, toque em ⇅ Reorganizar.\n2. Escolha ★ Favoritados ou Demais.\n3. Arraste os grupos pela alça ⠿ para a ordem desejada e toque em Salvar (ou Cancelar).\nNos filtros da aba Ações, também dá para arrastar pela alça ⠿ para reordenar ou mandar para Filtros ocultos."),
 (("grupo",), "Grupos:\n1. Na aba Ações (＋ Criar grupo) ou na aba Grupos (＋ Criar), comece um grupo.\n2. Toque nos cards das empresas para selecioná-las (uma ação por empresa).\n3. Digite o Nome do grupo e toque em Salvar.\n4. Na aba Grupos, abra o grupo para ver só as empresas dele na lista; use Editar ou Excluir para alterar."),
 (("filtr","ordenar","ordena","busca","pesquis"), "Filtros e ordenação (aba Ações):\n1. Digite em 'Buscar ticker ou nome…' – a lista filtra enquanto você digita.\n2. Toque na lupa 🔍 para Mais filtros: Só líquidas, Índice B3, Setor e os campos de mínimo/máximo (≥ maior é melhor, ≤ menor é melhor; percentuais como número, 8 = 8%).\n3. Arraste filtros pela alça ⠿ para reordenar ou para Filtros ocultos; Limpar zera tudo.\n4. Em Ordenar, escolha o indicador e toque em Maior → menor para inverter.\n5. ↓ CSV exporta o resultado."),
 (("chat",), "Aba Chat:\n1. Digite em 'Pergunte sobre as ações do site…' (ex.: 'P/L da PETR4', 'compare VALE3 e ITUB4', 'maiores DY') e envie.\n2. Perguntas simples são respondidas na hora pelo próprio site; as abertas usam IA com os dados do site (a origem aparece abaixo da resposta).\n3. Se achar que algo está errado, diga e ele revisa."),
 (("acoes","acao","aba acoes","cards"), "Aba Ações:\n1. Cada card mostra preço, variação e os indicadores (consenso das fontes em Todos).\n2. No topo escolha país e fonte; veja 'Status das fontes' abaixo dos filtros.\n3. Toque no card para expandir (Expandir todos/Recolher todos abrem ou fecham todos): histórico, índices B3, peso no Ibovespa e outras classes da ação.\n4. As cores indicam concordância entre fontes (pergunte 'o que significam as cores').\n5. Use a busca, a lupa de filtros e Ordenar para refinar; Carregar mais mostra mais resultados."),
]
HOWW = ("como usar", "como funciona", "como faco", "como faço", "como uso", "para que serve", "onde fica", "explica a aba", "o que faz a aba", "como mexer", "passo a passo", "como adicion", "como cri", "como favorit", "como filtr", "como orden", "como compar", "como reorganiz", "tutorial")
SCREEN = ("qual acao", "quais acoes", "que acao", "que acoes", "melhores", "melhor acao", "descontad", "barat", "desvaloriz", "potencial", "crescimento",
          "recomend", "ranking", "liste", "listar", "filtr", "quais empresas", "qual empresa", "sugest", "oportunidade", "subvaloriz")
COMPLEX = ("por que", "porque", "explique", "analise", "analisa", "devo", "vale a pena", "compensa", "opiniao", "sugest", "e se", "minha", "meu ", "previs", "aluguel", "simula")
TABS = {"aluguel": "Aluguel", "previsao": "Previsão", "comparar": "Comparar", "grupos": "Grupos", "acoes": "Ações", "chat": "Chat", "filtro": "Ações", "favorit": "Grupos"}

def local(q, D, ret_fn, cx):
    """Respostas prontas sem IA. Retorna texto ou None."""
    nq = norm(q); T = _tickers(q, D); I = _idx(q); k = _metric(q, D)
    if any(w in nq for w in WRONG): return None
    if any(w in nq for w in COMPLEX) and not any(w in nq for w in HOWW): return None
    if any(w in nq for w in SCREEN) and not any(w in nq for w in HOWW): return None
    if "cor" in nq.split() or "cores" in nq or "colorid" in nq: return COLORS
    if any(w in nq for w in HOWW) or re.search(r"\baba\b", nq):
        for keys, txt in HOWTO:
            if any(w in nq for w in keys): return txt
        return None
    m = re.search(r"\b(o que (e|significa|quer dizer)|significado d[eo]|defin[ae])\b\s*(o |a |um |uma )?(.+?)\??$", nq)
    if m and not T:
        term = m.group(4).strip()
        for g, txt in sorted(GLOSS.items(), key=lambda x: -len(x[0])):
            if norm(g) in term or term in norm(g): return txt
        return None
    if cx.get("groups") and ("grupo" in nq or "quem esta" in nq or "quais estao" in nq):
        for line in str(cx["groups"]).split("\n"):
            name = norm(line.split(":")[0].split("[")[0]).strip()
            if name and name in nq: return line
    if T and not k and re.search(r"\b(preco|cotacao|quanto (esta|ta|custa)|valor da acao|variacao do dia|subiu hoje|caiu hoje|hoje)\b", nq):
        r = D["by"][T[0]]; v = r.get("v") or {}
        return f"{T[0]}: R$ {br(v.get('preco'))} ({'+' if (r.get('var') or 0) >= 0 else ''}{br(r.get('var'))}% no dia)."
    if (len(T) + len(I) >= 2) or (T and re.search(r"\b(rendeu|rentabilidade|valorizou|variacao|retorno|subiu|caiu)\b", nq)) or (I and not T and not k):
        return rules(q, D, ret_fn)
    if T and k: return rules(q, D, ret_fn)
    if k and re.search(r"\b(maiores|menores|top|maior|menor)\b", nq): return rules(q, D, ret_fn)
    return None

def rel_context(q, D, ret_fn, cx):
    """Só o contexto necessário à pergunta."""
    nq = norm(q); T = _tickers(q, D); I = _idx(q); parts = []
    screen = any(w in nq for w in SCREEN) or not (T or I)
    if screen: parts.append("TABELA DE TODAS AS AÇÕES (CSV; vazio = sem dado):\n" + table(D, cx))
    else:
        tb = table(D, cx).split("\n"); parts.append("AÇÕES CITADAS (CSV):\n" + "\n".join([tb[0]] + [l for l in tb[1:] if l.split(",")[0] in T]))
        for t in T[:4]: parts.append("DETALHE " + card(D, t))
    if cx.get("groups") and (screen or "grupo" in nq): parts.append("GRUPOS PRONTOS DO SITE (top 10):\n" + str(cx["groups"])[:8000])
    if T or I or "indice" in nq or "ibov" in nq:
        di, df = _period(q); R = ret_fn(di, df, T)
        parts.append(f"Variação no período {di} a {df}: " + "; ".join(f"{IDXN.get(x, x)} {br(R.get(x))}%" for x in T + list(IDXN) if x in R))
    for kk, lab, ws in (("prev", "PREVISÃO RENTABILIDADE (entradas, JSON)", ("previs", "simula", "aporte", "minha", "meu")),
                        ("prevRes", "PREVISÃO RENTABILIDADE (resultado na tela)", ("previs", "simula", "aporte", "minha", "meu")),
                        ("alug", "PREVISÃO ALUGUEL (entradas, JSON)", ("aluguel", "alugar", "btc")),
                        ("alugRes", "PREVISÃO ALUGUEL (resultado na tela)", ("aluguel", "alugar", "btc")),
                        ("comp", "COMPARAR (seleção, JSON)", ("compar", "rendeu mais", "rendeu menos")),
                        ("compRes", "COMPARAR (resultado na tela)", ("compar", "rendeu mais", "rendeu menos"))):
        if cx.get(kk) and any(w in nq for w in ws): parts.append(lab + ":\n" + str(cx[kk])[:5000])
    if any(w in nq for w in ("como", "aba", "funciona", "significa", "regra", "cor", "calcul", "fonte", "previs", "aluguel", "compar", "grupo")):
        parts.append("GUIA DO SITE (painel ⓘ):\n" + guide())
    return "\n\n".join(parts)

_QA = {}  # mesma pergunta no mesmo dia
_CACHE = {"day": None, "ok": False}
def answer2(q, hist, D, ret_fn, cx=None):
    cx = cx or {}; nq = norm(q).strip(" ?!.")
    rel = "|".join(str(cx.get(k, ""))[:3000] for k in ("prev", "alug", "comp") if any(w in nq for w in ("previs", "aluguel", "compar", "minha", "meu")))
    key = date.today().isoformat() + "|" + hashlib.sha1((nq + "|" + rel).encode()).hexdigest()
    if key in _QA and not hist: return dict(_QA[key], cached=True)
    loc = None
    try: loc = local(q, D, ret_fn, cx)
    except Exception as e: log.info("local: %s", e)
    if loc:
        out = {"a": loc, "mode": "regras", "tok": 0}
    else:
        ctx = rel_context(q, D, ret_fn, cx)
        T = _tickers(q, D)
        want = any(w in nq for w in WRONG) or any("red" in ((D["by"].get(t) or {}).get("st") or {}).values() for t in T)
        out = None
        if not want:
            try:
                a, tok = gemini2(q, ctx, hist)
                out = {"a": a, "mode": "gemini", "tok": tok}
                if any(w in norm(a) for w in MISSING): want = True
            except Exception as e:
                log.info("chat fallback: %s", str(e)[:80])
        if want:  # (a) falta dado, (b) divergência entre fontes, (c) usuário diz que está errado
            try:
                a, tok = ground(q, ctx, hist); out = {"a": a, "mode": "gemini+web", "tok": tok}
            except Exception as e:
                log.info("busca web: %s", str(e)[:60])
                note = "\n\n(Busca na web indisponível agora — plano gratuito/cota do Gemini; resposta com os dados do site.)"
                if out is None:
                    try: a, tok = gemini2(q, ctx, hist); out = {"a": a, "mode": "gemini", "tok": tok}
                    except Exception: out = {"a": rules(q, D, ret_fn), "mode": "regras", "tok": 0}
                out = dict(out, a=out["a"] + note)
        if out is None: out = {"a": rules(q, D, ret_fn), "mode": "regras", "tok": 0}
    if out["mode"] == "gemini" or loc: _QA[key] = out
    if len(_QA) > 2000: _QA.clear()
    return out

WRONG = ("esta errado", "ta errado", "errado", "nao e isso", "incorreto", "confere", "confira", "verifica", "verifique", "nao bate", "desatualizado")
MISSING = ("nao tem esse dado", "nao possui", "nao ha informac", "nao contem", "nao dispoe", "nao tem informac", "nao consta", "nao encontrei")
TRUST = ("Ao pesquisar na web, prefira fontes confiáveis: B3 (b3.com.br), CVM (gov.br/cvm, rad.cvm.gov.br), sites de RI das empresas, "
         "Status Invest, Fundamentus. Diga claramente o que veio da web e o que veio do site.")
def ground(q, ctx, hist):
    """Gemini com busca Google. Retorna (texto com fontes, tokens) ou levanta erro."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key: raise RuntimeError("sem chave")
    contents = [{"role": "user" if h.get("r") == "u" else "model", "parts": [{"text": str(h.get("t", ""))[:1500]}]} for h in (hist or [])[-4:]]
    contents.append({"role": "user", "parts": [{"text": q[:1000]}]})
    sys_t = ("Você é o assistente do site Screener B3. Responda em português do Brasil, conciso. Use os DADOS DO SITE e, quando faltarem ou parecerem errados, "
             "a busca na web. " + TRUST + " Sem recomendação personalizada.\n\nDADOS DO SITE:\n" + ctx[:60000])
    err = None
    for model in [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-3.5-flash", "gemini-3.1-flash-lite"] if m]:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", headers={"x-goog-api-key": key},
                          json={"systemInstruction": {"parts": [{"text": sys_t}]}, "contents": contents, "tools": [{"google_search": {}}],
                                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3000, "thinkingConfig": {"thinkingBudget": 0}}}, timeout=90)
        if r.status_code != 200: err = r.status_code; continue
        j = r.json(); c = j["candidates"][0]
        t = "".join(p.get("text", "") for p in c["content"]["parts"] if not p.get("thought")).strip()
        src = [(x.get("web") or {}) for x in (c.get("groundingMetadata") or {}).get("groundingChunks", [])]
        src = [w for w in src if w.get("uri")][:6]
        if src: t += "\n\nFontes da web:\n" + "\n".join(f"• {w.get('title') or 'fonte'}: {w['uri']}" for w in src)
        if t: return t, (j.get("usageMetadata") or {}).get("promptTokenCount")
    raise RuntimeError(f"busca {err}")

def gemini2(q, ctx, hist):
    key = os.environ.get("GEMINI_API_KEY")
    if not key: raise RuntimeError("sem chave")
    # cache de contexto do Gemini (cachedContents): no plano gratuito o limite é 0 -> tenta 1x por dia e usa contexto inline
    if _CACHE["day"] != date.today().isoformat():
        _CACHE["day"] = date.today().isoformat()
        try:
            r = requests.post("https://generativelanguage.googleapis.com/v1beta/cachedContents", headers={"x-goog-api-key": key},
                              json={"model": "models/gemini-3.5-flash", "systemInstruction": {"parts": [{"text": "GUIA DO SITE:\n" + guide()}]}, "ttl": "86400s"}, timeout=20)
            _CACHE["ok"] = r.status_code == 200 and r.json().get("name"); log.info("cachedContents: %s", r.status_code)
        except Exception: _CACHE["ok"] = False
    sys_t = ("Você é o assistente do site Screener B3. Responda em português do Brasil, de forma concisa, usando SOMENTE os dados abaixo. "
             "Pode filtrar, ranquear e cruzar critérios na tabela e deve explicar os critérios usados. Diga quais ações atendem aos critérios, "
             "sem recomendação personalizada de investimento. Se um dado não estiver aqui, diga que o site não tem. Números no formato brasileiro.\n\nDADOS DO SITE:\n" + ctx)
    contents = [{"role": "user" if h.get("r") == "u" else "model", "parts": [{"text": str(h.get("t", ""))[:1500]}]} for h in (hist or [])[-4:]]
    contents.append({"role": "user", "parts": [{"text": q[:1000]}]})
    models = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-3.5-flash", "gemini-3.1-flash-lite"] if m]
    err = None
    for model, th in [(m, True) for m in models] + [("gemini-flash-latest", False)]:
        body = {"contents": contents, "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3000, **({"thinkingConfig": {"thinkingBudget": 0}} if th else {})}}
        if _CACHE["ok"] and model == "gemini-3.5-flash": body["cachedContent"] = _CACHE["ok"]; body["systemInstruction"] = {"parts": [{"text": sys_t}]}
        else: body["systemInstruction"] = {"parts": [{"text": sys_t}]}
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body, timeout=90)
        except requests.RequestException as e: err = type(e).__name__; continue
        if r.status_code != 200: err = f"http {r.status_code}"; continue
        j = r.json(); c = j["candidates"][0]["content"]["parts"]
        t = "".join(p.get("text", "") for p in c if not p.get("thought")).strip()
        if t: return t, (j.get("usageMetadata") or {}).get("promptTokenCount")
        err = "vazio"
    raise RuntimeError(f"gemini {err}")
