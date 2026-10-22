"""Chat sobre os dados do site.

Fluxo (answer2):
1. parse(): entende a pergunta sem IA (tickers, nomes/apelidos de empresas, indicadores, setor, filtros, período,
   memória da conversa, abreviações e erros de digitação).
2. Se a interpretação é confiável (nenhuma palavra sobrando), responde na hora com os dados do site (execute()).
3. Senão, com GEMINI_API_KEY: a IA só INTERPRETA a pergunta em JSON (interpret()) e o Python calcula com os dados
   reais; se a pergunta é aberta (análise, opinião, explicação), o Gemini responde com o contexto do site.
4. Reclamação ("está errado"), dado faltando ou indicador citado sem maioria entre as fontes: Gemini com busca na web.
5. Sem IA disponível: melhor esforço das regras e sugestões ("Você quis dizer…").
Toda pergunta é registrada em cache/chat_log.jsonl (veja /api/chat/log)."""
import os, re, json, time, random, difflib, hashlib, unicodedata, logging, math, html as _html
from datetime import date, timedelta, datetime, timezone
import requests

log = logging.getLogger("chat")
BASE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE, "cache", "chat_log.jsonl")
DEADLINE_S = 35  # tempo total da resposta no servidor; IA fora do ar não segura a pessoa por mais que isso
_DOWN = {}  # modelo do Gemini que respondeu 503/429 -> até quando pular só ele (2 min); os outros modelos seguem tentando

# ============================================================ vocabulário
IDX = {"@ibov": ["ibovespa", "ibov", "indice bovespa"], "@usd": ["dolar", "usd", "cambio"], "@cdi": ["cdi", "cdb", "renda fixa"],
       "@ipca": ["ipca", "inflacao"], "@poup": ["poupanca"], "@gold": ["ouro"]}
import history  # noqa: E402
import snapshots  # noqa: E402  (nomes_populares.json → apelidos)
IDXN = {"@" + k: n for k, n in history.INDICES.items()}  # nomes dos índices: fonte única em history.INDICES
# métricas calculadas do histórico (snapshot metrics): rótulo, unidade
MX = {"ret1": ("Valorização 1 ano", "%"), "ret2": ("Valorização 2 anos", "%"), "ret3": ("Valorização 3 anos", "%"),
      "ret4": ("Valorização 4 anos", "%"), "ret5": ("Valorização 5 anos", "%"), "dy1": ("DY médio 1 ano", "%"),
      "prov12": ("Proventos 12m ÷ preço", "%"), "avg1": ("Preço médio 1 mês", "R$")}
BIG = {"valmerc", "patrliq"}  # + campos de volume (grp "vol" em /api/data)
RET = "ret"  # pseudo-indicador: variação de preço no período (calculada pelo histórico)

# vocabulário do chat: fonte única em vocabulario.json (sinônimos, gírias, abreviações, apelidos, frases)
VOC = json.load(open(os.path.join(BASE, "vocabulario.json"), encoding="utf-8"))
# indicador -> sinônimos e gírias (texto normalizado: sem acento, minúsculo). Casam por palavra inteira, o mais longo primeiro.
SYN = {k: list(dict.fromkeys(ws + VOC["girias"].get(k, []))) for k, ws in VOC["sinonimos"].items()}


def frase(kind, hist=None):
    """Uma das variações da frase (vocabulario.json -> frases), evitando as que já apareceram nas respostas da conversa."""
    opts = VOC["frases"][kind]
    used = " ".join(str(h.get("t", "")) for h in (hist or []) if h.get("r") != "u")
    return random.choice([o for o in opts if o.strip() not in used] or opts)
SYN_LIST = sorted(((w, k) for k, ws in SYN.items() for w in ws), key=lambda x: -len(x[0]))
METRIC_WORDS = {p for w, _ in SYN_LIST for p in re.split(r"[\s/]+", w) if p}

# setor (palavras do usuário) -> regex aplicado em setor/subsetor/segmento B3 (inglês do TradingView/brapi + português da B3)
SECTORS = {
    "Bancos": (("banco", "bancos", "bancarias", "bancario", "bancarios", "financeiro", "financeiras", "financeiros", "financas"),
               r"bank|banco|\bbco\b|bancos"),
    "Seguradoras": (("seguradora", "seguradoras", "seguros", "seguro", "seguridade"), r"insur|segur|resseg"),
    "Energia elétrica": (("energia", "eletrica", "eletricas", "eletrico", "eletricas", "eletricidade", "utilities", "utilidade publica",
                          "transmissoras", "transmissao", "geradoras", "distribuidoras"), r"electric|eletric|energia|utilit|power"),
    "Saneamento": (("saneamento", "agua"), r"water|sanea|agua"),
    "Petróleo e gás": (("petroleo", "petroleiras", "petroleira", "oleo e gas", "gas", "combustiveis", "combustivel"),
                       r"oil|gas|petrol|refin|combust"),
    "Mineração e siderurgia": (("mineracao", "mineradoras", "mineradora", "siderurgia", "siderurgicas", "siderurgica", "aco", "metais", "metalurgia"),
                               r"miner|metal|steel|mining|siderur|alumin"),
    "Varejo": (("varejo", "varejistas", "varejista", "lojas", "comercio"), r"retail|varej|comerc|store|department|apparel|tecido|vestu|calcad|eletrodom"),
    "Construção e imóveis": (("construcao", "construtoras", "construtora", "imobiliario", "imobiliarias", "incorporadoras", "imoveis", "shoppings", "shopping"),
                             r"constru|homebuild|real estate|imobil|edific|incorpor|shopping|explor.*imov"),
    "Saúde": (("saude", "hospitais", "hospital", "farmaceuticas", "farmacias", "farmacia", "planos de saude"), r"health|saude|hospital|medic|pharma|farma|drug"),
    "Tecnologia": (("tecnologia", "tech", "software", "ti"), r"tech|software|inform|semicon|computa|programa|data process"),
    "Telecomunicações": (("telecom", "telecomunicacoes", "telefonia", "telefonicas"), r"telecom|communicat|telefon"),
    "Alimentos e bebidas": (("alimentos", "alimenticias", "frigorificos", "frigorifico", "bebidas", "carnes"), r"food|aliment|beverage|bebida|carne|meat|cervej"),
    "Agronegócio": (("agro", "agronegocio", "agricolas", "agricultura"), r"agri|agro|farm|acucar|alcool|grao"),
    "Papel e celulose": (("papel", "celulose"), r"paper|pulp|papel|celulose|madeira"),
    "Transporte e logística": (("transporte", "transportes", "logistica", "ferrovias", "rodovias", "aereas", "aviacao", "companhias aereas", "locadoras", "aluguel de carros"),
                               r"transport|logist|rail|airline|truck|rodov|ferrov|aere|locac|aluguel de carro|rental"),
    "Educação": (("educacao", "ensino", "faculdades"), r"educa|school|ensino"),
}
SECT_WORDS = sorted(((w, s) for s, (ws, _) in SECTORS.items() for w in ws), key=lambda x: -len(x[0]))

# apelidos -> raiz de 4 letras (só valem se a raiz existir nos dados)
ALIAS = VOC["apelidos"]
# apelidos que também são palavras comuns: só valem com contexto de ação (ou escritos em maiúsculas)
POP_SKIP = {"caixa", "bolsa", "porto", "light", "petro", "multi", "mateus", "vibra", "motiva", "brava"}  # nomes populares que são palavras comuns
GUARDED = {"vale", "azul", "gol", "tim", "rumo", "porto", "vivo", "even", "positivo", "vamos", "prio", "wiz", "raia", "natura",
           "movida", "camil", "tenda", "motiva", "cury", "bb", "b3"}
SIGN_WORDS = {"positivo", "positiva", "positivos", "positivas", "negativo", "negativa", "negativos", "negativas"}
VALE_IDIOM = re.compile(r"\b(vale a pena|vale mais|vale menos|vale o|vale a|quanto vale|nao vale|vale muito|vale apena|valeria|vale investir|vale comprar|vale ficar)\b")

# palavras que não carregam informação (não tornam a pergunta "difícil")
STOP = set("""a o os as um uma uns umas de do da dos das no na nos nas em e ou que qual quais quem quanto quanta quantos quantas
como pra para por pelo pela pelos pelas com sem se ao aos a, me mim eu voce voces tem ter tinha teve ha hoje agora atual atualmente
atuais esta estao esse essa esses essas isso este isto aquele aquela dele dela deles delas dessa desse sua seu suas seus minha meu
mais menos muito muita pouco ja ainda tambem so somente apenas mostre mostra mostrar me diga diz dizer fale fala falar quero queria
gostaria saber sabe ver veja lista liste listar listagem informe informar traga trazer quais sao sao e eh foi ser sendo fica ficou
acao acoes empresa empresas papel papeis ativo ticker tickers companhia companhias bolsa br brasil brasileira brasileiras
maior maiores menor menores top primeiras primeiros ultimas ultimos mais alto alta altos baixo baixa baixos alto melhor melhores pior
piores dela daquela nele nela qual e obrigado obrigada ola oi bom dia boa tarde noite por favor favor valeu vs versus contra x entre
comparar compare comparacao compara compar comparando atual valor valores numero numeros dado dados indicador indicadores
classe classes on pn unit units ordinaria ordinarias preferencial preferenciais todas todos tudo cada geral site aqui la ai
ano anos mes meses dia dias semana semanas periodo desde ate de a hoje ontem anual mensal ultimo ultima passado passada este
neste nesse deste desse janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro ytd acumulado
acima abaixo superior inferior pelo menos minimo maximo maior que menor que igual positivo positiva positivos positivas negativo
negativa negativos negativas zero ordem crescente decrescente ordenado ordenadas ordenados ranking rank classificacao
paga pagam pagou pagar pagando pagaram possui possuem possuir apresenta apresentam teve tiveram tenha tenham negocia negociam
estava estavam custa custam ficaram mostrando hj sobre ficam fica acoes? ha existe existem seria seriam pode podem consegue
quero ver vejo saber calcula calcule qual resumo informacoes info detalhes dados significa significam significado quer dizer
funciona usar uso faco faz criar onde setor setores segmento segmentos ramo area
""".split())
COMPLEX = ("por que", "porque", "explique", "explica", "analise", "analisa", "analisar", "devo", "vale a pena", "compensa", "opiniao",
           "sugest", "recomend", "indica", "indique", "e se", "minha", "meu ", "minhas", "meus ", "previs", "simula", "futuro", "vai subir",
           "vai cair", "perspectiva", "risco", "arriscad", "seguro investir", "investir", "comprar", "vender", "carteira", "estrategia",
           "boa", "bom ", "ruim", "barata", "baratas", "barato", "baratos", "cara ", "caras", "caro", "descontad", "oportunidade",
           "subvaloriz", "potencial", "justo", "graham", "magic formula", "perene", "perenes", "growth", "turnaround", "etiqueta")
HOWW = ("como usar", "como funciona", "como faco", "como faz", "como uso", "para que serve", "pra que serve", "onde fica", "onde esta",
        "onde encontro", "onde acho", "explica a aba", "o que faz a aba", "como mexer", "passo a passo", "como adicion", "como cri",
        "como favorit", "como filtr", "como orden", "como compar", "como reorganiz", "como export", "como baix", "como atualiz",
        "como mud", "como troc", "como instal", "instalar", "aplicativo", "o app", "baixar app", "como vejo", "como ver", "tutorial", "nao acho", "nao encontro", "cade")
WRONG = ("esta errado", "ta errado", "errado", "errada", "nao e isso", "incorreto", "incorreta", "confere", "confira", "conferir", "verifica",
         "verifique", "nao bate", "desatualizado", "desatualizada", "mentira", "nao esta certo", "esta certo", "ta certo")
MISSING = ("nao tem esse dado", "nao possui", "nao ha informac", "nao contem", "nao dispoe", "nao tem informac", "nao consta",
           "nao encontrei", "nao tem dados", "nao tenho")
ABBR = VOC["abreviacoes"]
MONTHS = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def br(x, d=2):
    if x is None: return "—"
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def dbr(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def money_big(x):
    a = abs(x)
    if a >= 1e9: return f"R$ {br(x / 1e9, 1)} bi"
    if a >= 1e6: return f"R$ {br(x / 1e6, 1)} mi"
    if a >= 1e3: return f"R$ {br(x / 1e3, 1)} mil"
    return f"R$ {br(x)}"


# ============================================================ dados
def build(rows, fields, metrics, cad=None):
    """rows = linhas do site (consenso), fields = FIELDS do servidor, metrics = snapshot metrics, cad = cadastro B3 {RAIZ: [nome, segmento]}."""
    F = {f[0]: {"label": f[1], "unit": f[2], "dir": f[3], "neg": f[4]} for f in fields}
    by = {r["ticker"]: r for r in rows}
    M = metrics or {}
    cad = cad or {}

    def liq(r):
        v = r.get("v") or {}
        return v.get("vol30") or 0
    roots = {}
    for r in rows: roots.setdefault(r["ticker"][:4], []).append(r["ticker"])
    for k in roots: roots[k].sort(key=lambda t: -liq(by[t]))
    # tokens dos nomes -> raízes (só tokens que identificam no máximo 1 empresa)
    tok = {}
    for k, ts in roots.items():
        names = {by[t].get("nome") or "" for t in ts} | {(cad.get(k) or [""])[0] or ""}
        for nm in names:
            for w in re.findall(r"[a-z0-9&']+", norm(nm)):
                if len(w) >= 4 and w not in STOP and w not in GENERIC and w not in METRIC_WORDS:
                    tok.setdefault(w, set()).add(k)
    tok = {w: next(iter(ks)) for w, ks in tok.items() if len(ks) == 1}
    alias = {norm(a): k for a, k in ALIAS.items() if k in roots}
    # nome popular + aliases (nomes_populares.json, fonte única): "magazine luiza", "raia drogasil"…; palavras comuns ficam de fora
    for k in roots:
        for nm in snapshots.nome_busca(k + "3").split(" | "):
            a = norm(nm).strip()
            if len(a) >= 5 and a not in alias and a not in POP_SKIP and a not in STOP and a not in GENERIC and a not in METRIC_WORDS: alias[a] = k
    seg = {k: (cad.get(k) or [None, None])[1] for k in roots}
    vocab = set(tok) | set(alias) | METRIC_WORDS | {w for w, _ in SECT_WORDS} | {w for ws in IDX.values() for w in ws}
    return {"rows": rows, "F": F, "by": by, "M": M, "roots": roots, "tok": tok, "alias": alias, "seg": seg, "liq": liq,
            "vocab": vocab, "tickers": list(by)}


GENERIC = set("""holding holdings participacoes participacao part industria industrias comercio servicos investimentos invest
brasileiro brasileira brasileiros brasil grupo group companhia company corp corporation unit units pfd sa s/a ltda
energia eletrica eletricas transmissora transmissao geracao distribuicao saneamento seguros seguridade financeira
financeiro banco bco bank banc nacional internacional nordeste sudeste norte sul central paulista paulistas mineira
gerais minas sao rio janeiro tecnologia sistemas logistica transportes alimentos imobiliaria empreendimentos realty
incorporadora construtora engenharia mineracao siderurgica metalurgica petroleo papel celulose quimica textil
shopping shoppings centers center educacional educacao saude hospitalar medicina farmaceutica telecomunicacoes
comunicacoes cia companhias ordinaria preferencial units cons class classe each para cada""".split())


def fmt(D, k, x):
    if x is None: return "—"
    if k in BIG or (D["F"].get(k) or {}).get("grp") == "vol": return money_big(x)
    unit = (D["F"].get(k) or {}).get("unit") or (MX.get(k) or ("", ""))[1]
    if unit == "%": return br(x) + "%"
    if unit in ("R$", "$"): return "R$ " + br(x)
    return br(x)


def label(D, k):
    if k in D["F"]: return D["F"][k]["label"]
    if k in MX: return MX[k][0]
    return {RET: "Variação de preço"}.get(k, k)


def val(D, r, k):
    v = (r.get("v") or {}).get(k)
    if v is not None: return v
    return (D["M"].get(r["ticker"]) or {}).get(k)


# ============================================================ entendimento
def _clean(q):
    """Normaliza: sem acento, minúsculo, abreviações expandidas, pontuação vira espaço (preserva p/l, p/vp, ev/ebitda...)."""
    nq = norm(q)
    nq = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", nq)  # 1.000 -> 1000
    nq = re.sub(r"[?!;:\"“”()\[\]{}]", " ", nq)
    nq = re.sub(r"(?<!\d),|,(?!\d)", " ", nq)
    nq = re.sub(r"\s+\.|\.\s+|\.$", " ", nq)
    out = []
    for w in nq.split():
        out.append(ABBR.get(w, w))
    return " ".join(out).strip()


def _fix_typos(nq, D):
    """Corrige palavras desconhecidas parecidas com o vocabulário (dividndo -> dividendo). Devolve (texto, correções)."""
    vocab = [w for w in D["vocab"] if " " not in w and len(w) >= 4]
    fixes, out = [], []
    for w in nq.split():
        if len(w) >= 5 and w.isalpha() and w not in D["vocab"] and w not in STOP and w not in COMMON_WORDS:
            m = difflib.get_close_matches(w, vocab, 1, 0.84)
            if m:
                fixes.append((w, m[0])); w = m[0]
        out.append(w)
    return " ".join(out), fixes


COMMON_WORDS = set("""casa cash game home life best next onda ouro soja oleo mill rede area land vale mais como para qual quem onde
esta isso essa esse nada tudo hoje anos dias taxa dado dados renda fixa bolsa acao boas bons cada cara caro mesa nova novo
pena pela pelo sobre tipo meta foco vida time base bens hora uma umas todo toda show love play jogo real reais""".split())


def _period(nq):
    """-> (inicio, fim, rótulo, tipo) ; tipo: 'dia' | 'periodo' ; None se nada explícito."""
    t = date.today()
    y = t.year
    m = re.search(r"\b(?:de|entre)\s+((?:19|20)\d\d)\s+(?:a|e|ate)\s+((?:19|20)\d\d)\b", nq)
    if m:
        a, b = sorted((int(m.group(1)), int(m.group(2))))
        return f"{a}-01-01", min(date(b, 12, 31), t).isoformat(), f"de {a} a {b}", "periodo"
    m = re.search(r"\bdesde\s+((?:19|20)\d\d)\b", nq)
    if m: return f"{m.group(1)}-01-01", t.isoformat(), f"desde {m.group(1)}", "periodo"
    m = re.search(r"\b(?:desde|a partir de)\s+(" + "|".join(MONTHS) + r")(?:\s+de\s+((?:19|20)\d\d))?\b", nq)
    if m:
        mo = MONTHS.index(m.group(1)) + 1; yy = int(m.group(2) or (y if mo <= t.month else y - 1))
        return f"{yy}-{mo:02d}-01", t.isoformat(), f"desde {m.group(1)}/{yy}", "periodo"
    m = re.search(r"\b(?:em|no ano de|durante|ano de)\s+((?:19|20)\d\d)\b", nq)
    if not m:
        for mm in re.finditer(r"\b((?:19|20)\d\d)\b", nq):
            if not re.search(r"(acima|abaixo|maior|menor|mais|menos|superior|inferior|minimo|maximo|ate|[<>])\s*(de|que|a)?\s*$", nq[:mm.start()]):
                m = mm; break
    if m:
        yy = int(m.group(1))
        if 1994 <= yy <= y:
            return f"{yy}-01-01", min(date(yy, 12, 31), t).isoformat(), f"em {yy}", "periodo"
    if re.search(r"\b(no ano|neste ano|nesse ano|este ano|esse ano|do ano|ytd|acumulado do ano|ano ate agora|desde o inicio do ano|em " + str(y) + r")\b", nq):
        return f"{y}-01-01", t.isoformat(), f"em {y} (até hoje)", "periodo"
    m = re.search(r"\b(\d+|um|uma|dois|duas|tres|quatro|cinco|seis|doze)\s*(anos?|mes|meses|dias?|semanas?|pregoes?)\b", nq)
    if m:
        n = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "doze": 12}.get(m.group(1)) or int(m.group(1))
        u = m.group(2)
        days = n * (365 if u.startswith("ano") else 30 if u.startswith("mes") else 7 if u.startswith("semana") else 1.45 if u.startswith("preg") else 1)
        lab = f"{n} {u}"
        return (t - timedelta(days=round(days))).isoformat(), t.isoformat(), f"em {lab}", "periodo"
    if re.search(r"\b(na semana|nesta semana|essa semana|esta semana|ultima semana|semana passada)\b", nq):
        return (t - timedelta(days=7)).isoformat(), t.isoformat(), "nos últimos 7 dias", "periodo"
    if re.search(r"\b(no mes|neste mes|este mes|esse mes|ultimo mes|mes passado)\b", nq):
        return (t - timedelta(days=30)).isoformat(), t.isoformat(), "nos últimos 30 dias", "periodo"
    if re.search(r"\b(hoje|no dia|do dia|agora|nesse momento|neste momento|ultimo pregao|ontem)\b", nq):
        return (t - timedelta(days=1)).isoformat(), t.isoformat(), "no dia", "dia"
    return None


def _num(s):
    s = s.replace("%", "").strip()
    if re.fullmatch(r"-?\d+,\d+", s): s = s.replace(",", ".")
    try: return float(s)
    except ValueError: return None


CMP_RE = re.compile(r"(acima de|maior que|maior ou igual a|mais de|mais que|superior a|pelo menos|no minimo|minimo de|>=|>|"
                    r"abaixo de|menor que|menor ou igual a|menos de|menos que|inferior a|no maximo|maximo de|ate|<=|<)\s*(-?\d+(?:[.,]\d+)?)\s*(%|mi|milhoes|milhao|bi|bilhoes|bilhao|mil)?")
BETW_RE = re.compile(r"entre\s+(-?\d+(?:[.,]\d+)?)\s*%?\s+e\s+(-?\d+(?:[.,]\d+)?)\s*%?")
SIGN_RE = re.compile(r"\b(positivo|positiva|positivos|positivas|negativo|negativa|negativos|negativas|maior que zero|menor que zero)\b")


# qualificadores -> filtros quando vêm com outro critério; sozinhos viram o critério (indicador, ordem)
_QW = lambda k: r"\b(" + "|".join(re.escape(w) for w in sorted(VOC["qualificadores"][k], key=len, reverse=True)) + r")\b"  # palavras: vocabulario.json
QUALS = [(_QW("barato"), [("pl", ">", 0), ("pl", "<=", 10)], ("pl", "asc")),
         (_QW("pouca_divida"), [("dlebit", "<=", 2)], ("dlebit", "asc")),
         (_QW("boa_pagadora"), [("dy", ">=", 6)], ("dy", "desc"))]
# índice da B3 como filtro de lista ("mais barata do Ibovespa", "small caps")
IXF = [(r"\b(do|da|no|na|dentro do)\s+(ibov|ibovespa|indice bovespa)\b", "IBOV"), (r"\bsmall ?caps?\b|\bsmll\b", "SMLL"), (r"\bidiv\b", "IDIV")]


def parse(q, D, hist=None):
    """Interpretação sem IA. -> dict com tickers, idx, metrics, sector, filters, period, order, n, flags e 'left' (palavras não entendidas)."""
    nq0 = _clean(q)
    nq, fixes = _fix_typos(nq0, D)
    work = " " + nq + " "
    P = {"q": q, "nq": nq, "fixes": fixes, "ixf": None, "tickers": [], "idx": [], "metrics": [], "sector": None, "filters": [], "period": None,
         "order": None, "n": None, "notes": [], "from_hist": False, "all_classes": bool(re.search(r"\btodas as classes\b", nq)),
         "illiquid": bool(re.search(r"\b(iliquidas|incluindo iliquidas|todas as acoes|sem filtro de liquidez)\b", nq)), "hist": hist or []}
    used = []  # trechos consumidos

    def take(span_text):
        nonlocal work
        work = work.replace(" " + span_text + " ", " ", 1) if (" " + span_text + " ") in work else work.replace(span_text, " ", 1)
        used.append(span_text)

    # --- tickers explícitos (PETR4, petr 4, PETR-4, TAEE11)
    for m in re.finditer(r"\b([a-z][a-z0-9]{3})\s?-?(\d{1,2})([a-z]?)\b", nq):
        t = (m.group(1) + m.group(2) + m.group(3)).upper()
        if t not in D["by"]: t = (m.group(1) + m.group(2)).upper()
        if t in D["by"]:
            P["tickers"].append(t); take(m.group(0))
        elif m.group(1).upper() in D["roots"]:  # classe inexistente: usa a mais negociada e avisa
            t2 = D["roots"][m.group(1).upper()][0]
            P["tickers"].append(t2); P["notes"].append(f"Não encontrei {t}; usei {t2}."); take(m.group(0))
        elif re.fullmatch(r"[a-z]{4}\d{1,2}", m.group(0)):
            near = difflib.get_close_matches(m.group(0).replace(" ", "").replace("-", "").upper(), D["tickers"], 3, 0.6)
            P["notes"].append(f"Não encontrei {t} no site." + (f" Você quis dizer {', '.join(near)}?" if near else ""))
            P.setdefault("unknown_tickers", []).append(t); take(m.group(0))
    # --- índices (antes dos apelidos: "ouro", "dolar")
    for k, ws in IDX.items():
        for w in sorted(ws, key=len, reverse=True):
            if re.search(r"\b" + re.escape(w) + r"\b", work):
                P["idx"].append(k); take(w); break
    # --- apelidos (mais longos primeiro) e tokens de nome
    has_ctx = bool(re.search(r"\b(acao|acoes|papel|ticker|empresa|cotacao|preco|dy|dividend|p/l|p/vp|roe|lucro|rendeu|subiu|caiu|valoriz|"
                             r"divida|margem|vs|versus|contra|compar)\b", nq)) or len(nq.split()) <= 4
    for a in sorted(D["alias"], key=lambda x: (x in GUARDED, -len(x))):
        if not re.search(r"\b" + re.escape(a) + r"\b", work): continue
        has_ctx = has_ctx or bool(P["tickers"]) or bool(re.search(r"\b" + re.escape(a) + r"\s+(ou|e|vs|x)\b|\b(ou|e|vs|x)\s+" + re.escape(a) + r"\b", nq))
        if a == "vale" and VALE_IDIOM.search(nq) and not re.search(r"\bvale3\b|\bvale s\.?a", nq): continue
        if a in GUARDED and not has_ctx and not re.search(r"\b" + re.escape(a.upper()) + r"\b", q): continue
        if a == "azul" and re.search(r"\b(cor|cores|card|numero|aparece|fica|badge|etiqueta|aj)\b", nq): continue
        if a == "bb" and "bb seguridade" in work: continue
        P["tickers"].append(_class(D, D["alias"][a], nq)); take(a)
    P["tickers"] = list(dict.fromkeys(P["tickers"]))
    # --- setor
    for w, s in SECT_WORDS:
        if re.search(r"\b" + re.escape(w) + r"s?\b", work):
            P["sector"] = s; take(w); break
    # --- indicadores (mais longo primeiro, por posição)
    found = []
    for w, k in SYN_LIST:
        for m in re.finditer(r"(?<![a-z0-9/])" + re.escape(w) + r"(?![a-z0-9/])", work):
            found.append((m.start(), m.end(), k, w))
            work = work[:m.start()] + " " * (m.end() - m.start()) + work[m.end():]
    found.sort()
    for s, e, k, w in found:
        if k not in P["metrics"]: P["metrics"].append(k)
        used.append(w)
    P["_mpos"] = [(s, e, k) for s, e, k, _ in found]
    for w in list(work.split()):
        k = D["tok"].get(w)
        if k and w not in COMMON_WORDS and w not in SIGN_WORDS:
            P["tickers"].append(_class(D, k, nq)); take(w)
    # --- raiz sozinha (petr, VALE) se não for palavra comum
    for m in re.finditer(r"\b([a-z]{4})\b", work):
        w = m.group(1)
        if w.upper() in D["roots"] and w not in COMMON_WORDS and w not in STOP and w not in METRIC_WORDS and w not in D["vocab"]:
            P["tickers"].append(_class(D, w.upper(), nq)); take(w)
    P["tickers"] = list(dict.fromkeys(P["tickers"]))
    # --- período
    P["period"] = _period(nq)
    # --- filtros
    mpos = _metric_positions(nq, P["metrics"])
    for m in CMP_RE.finditer(nq):
        op = ">=" if m.group(1) in ("acima de", "maior que", "maior ou igual a", "mais de", "mais que", "superior a", "pelo menos", "no minimo", "minimo de", ">=", ">") else "<="
        x = _num(m.group(2))
        if x is None: continue
        mul = {"mi": 1e6, "milhoes": 1e6, "milhao": 1e6, "bi": 1e9, "bilhoes": 1e9, "bilhao": 1e9, "mil": 1e3}.get(m.group(3) or "", 1)
        k = _metric_before(mpos, m.start()) or (P["metrics"][0] if len(P["metrics"]) == 1 else None)
        if k and k != RET: P["filters"].append((k, op, x * mul))
    for m in BETW_RE.finditer(nq):
        k = _metric_before(mpos, m.start()) or (P["metrics"][0] if len(P["metrics"]) == 1 else None)
        a, b = _num(m.group(1)), _num(m.group(2))
        if k and k != RET and a is not None and b is not None:
            P["filters"] += [(k, ">=", min(a, b)), (k, "<=", max(a, b))]
    for m in SIGN_RE.finditer(nq):
        k = _metric_before(mpos, m.start())
        if not k and re.search(r"\blucro\b", nq[max(0, m.start() - 25):m.start()]): k = "lpa"; used.append("lucro")
        if k and k != RET:
            P["filters"].append((k, ">" if m.group(1).startswith(("positiv", "maior")) else "<", 0))
    # --- índice como filtro e qualificadores
    for rx, ix in IXF:
        if re.search(rx, nq):
            P["ixf"] = ix
            if ix == "IBOV": P["idx"] = [x for x in P["idx"] if x != "@ibov"]
            break
    quals = [(rx, f, m) for rx, f, m in QUALS if re.search(rx, nq)]
    qwords = set()
    for rx, f, m in quals:
        for mm in re.finditer(rx, nq): qwords |= set(mm.group(0).split())
    if quals:
        if any("divid" in w or "endivid" in w for w in qwords): P["metrics"] = [k for k in P["metrics"] if k != "dlpl"]
        own = [k for k in P["metrics"] if k != RET and k not in {m[0] for _, _, m in quals}]
        for rx, f, m in quals:
            if own or len(quals) > 1: P["filters"] += [x for x in f if x[0] not in own]
            if not own and m[0] not in P["metrics"]: P["metrics"].insert(0, m[0])
    # --- ordem e quantidade
    if re.search(r"\b(maiores|maior|top|mais altos?|mais altas?|mais elevad[oa]s?|lideres|primeiros|mais)\b", nq): P["order"] = "desc"
    if re.search(r"\b(menores|menor|mais baix[oa]s?|menos)\b", nq): P["order"] = "asc" if P["order"] is None or re.search(r"\bmenor(es)?\b", nq) else P["order"]
    if re.search(r"\b(melhores|melhor)\b", nq): P["order"] = "best"
    if re.search(r"\b(piores|pior)\b", nq): P["order"] = "worst"
    if quals and len(quals) == 1 and P["metrics"] and P["metrics"][0] == quals[0][2][0]: P["order"] = quals[0][2][1]
    if RET in P["metrics"] and re.search(_QW("queda"), nq) and P["order"] != "asc":
        P["order"] = "worst"
    if not P["metrics"] and not P["tickers"] and re.search(r"\b(maiores|grandes|mais valiosas|gigantes)\s+(empresas|acoes|companhias)\b", nq):
        P["metrics"] = ["valmerc"]; P["order"] = "desc"
    m = re.search(r"\btop\s*(\d{1,3})\b", nq) or re.search(r"\b(\d{1,3})\s+(?:acoes|empresas|papeis|maiores|menores|melhores|piores|primeir\w*|mais|menos)\b", nq) \
        or re.search(r"\b(?:maiores|menores|melhores|piores|primeiras|primeiros)\s+(\d{1,3})\b", nq)
    if m: P["n"] = max(1, min(int(m.group(1)), 50))
    # --- flags de intenção
    P["complaint"] = any(re.search(r"\b" + w + r"\b", nq) for w in WRONG)
    P["howto"] = any(w in nq for w in HOWW)
    nqc = nq
    for rx, _, _ in quals: nqc = re.sub(rx, " ", nqc)  # qualificador entendido não pede análise
    P["complex"] = any(w in (" " + nqc + " ") for w in COMPLEX) and not P["howto"]
    if P["order"] in ("best", "worst") and not P["metrics"]: P["complex"] = True
    P["define"] = bool(re.search(r"\b(o que (e|sao|significa|quer dizer)|que e|significado|significa|defin[ae]|definicao|conceito)\b", nq))
    P["colors"] = bool(re.search(r"\b(cor|cores|colorid\w*)\b", nq)) or bool(re.search(
        r"\b(vermelh\w+|laranja|amarel\w+|azul|verde|cinza|violeta|roxo)\b.*\b(card|numero|valor|aparece|fica|esta|significa|quer dizer|por que|porque)\b|"
        r"\b(card|numero|valor|aparece|fica|esta|significa|por que|porque)\b.*\b(vermelh\w+|laranja|amarel\w+|azul|verde|cinza|violeta|roxo)\b", nq))
    # --- memória da conversa ("e o P/L?", "e a VALE3?")
    # ordem/período sem indicador: variação de preço ("piores em 5 anos", "maiores altas")
    if not P["metrics"] and P["period"] and (P["order"] or re.search(r"\b(altas?|quedas?)\b", nq)) and not P["tickers"]:
        P["metrics"] = [RET]
        P["complex"] = any(w in (" " + nq + " ") for w in COMPLEX) and not P["howto"]
    if hist and not P.get("unknown_tickers"):
        marker = bool(re.match(r"^(e|e o|e a|e os|e as|e quanto|e qual|e de|e do|e da|agora|tambem|e em|e no|e na|mesmo|dela|dele|dessa|desse|da mesma)\b", nq)
                      or re.search(r"\b(dela|dele|dessa|desse|delas|deles|a mesma|o mesmo|essa acao|essa empresa|ela|elas|tambem)\b", nq))
        dataq = bool(P["metrics"] or P["period"])
        follow = marker or (len(nq.split()) <= 4 and dataq and not P["tickers"] and not P["idx"])
        if follow and not (P["order"] or P["sector"] or P["filters"] or P["n"] or P["define"] or P["howto"] or P["colors"]):
            pq = [h for h in hist if h.get("r") == "u"]
            for h in reversed(pq[-3:]):
                PP = parse(h.get("t", ""), D, None)
                if not P["tickers"] and not P["idx"] and (PP["tickers"] or PP["idx"]) and not P["sector"]:
                    P["tickers"], P["idx"], P["from_hist"] = PP["tickers"], PP["idx"], True
                if marker and not P["metrics"] and not P["period"] and PP["metrics"] and (P["tickers"] or P["idx"]) and not P["define"]:
                    P["metrics"], P["from_hist"] = PP["metrics"], True
                if marker and not P["period"] and PP["period"] and (P["metrics"] == [RET] or not P["metrics"]): P["period"] = PP["period"]
                if P["tickers"] or P["idx"]: break
    # --- palavras não entendidas
    rest = re.sub(r"-?\d+(?:[.,]\d+)?%?", " ", work)
    P["left"] = [w for w in re.findall(r"[a-z][a-z']*", rest) if w not in STOP and w not in COMMON_WORDS and len(w) > 1 and w not in qwords
                 and not (P.get("ixf") and w in ("ibov", "ibovespa", "indice", "bovespa", "small", "smll", "caps", "cap", "idiv"))
                 and not any(w in x.split() for x in used) and w not in ("mi", "bi", "mil", "milhoes", "bilhoes", "reais", "rs")]
    return P


def _class(D, root, nq):
    """Raiz -> ticker: classe pedida (ON/PN/unit) ou a mais negociada."""
    ts = D["roots"][root]
    want = None
    if re.search(r"\b(on|ordinaria|ordinarias)\b", nq): want = "3"
    elif re.search(r"\b(pn|preferencial|preferenciais|pna)\b", nq): want = "4"
    elif re.search(r"\b(unit|units)\b", nq): want = "11"
    if want:
        for t in ts:
            if t[4:] == want: return t
        if want == "4":
            for t in ts:
                if t[4:] in ("5", "6"): return t
    return ts[0]


def _metric_positions(nq, metrics):
    out = []
    for w, k in SYN_LIST:
        if k not in metrics: continue
        for m in re.finditer(r"(?<![a-z0-9/])" + re.escape(w) + r"(?![a-z0-9/])", nq): out.append((m.start(), m.end(), k))
    return sorted(out)


def _metric_before(mpos, pos):
    best = None
    for s, e, k in mpos:
        if e <= pos and pos - e <= 30: best = k
    return best


def confident(P):
    """A regra local só responde quando entendeu tudo (nenhuma palavra sobrando e nada que peça análise)."""
    return not P["left"] and not P["complex"] and not P["complaint"]


# ============================================================ execução (dados reais do site)
def _rank_dir(D, k, order):
    """True = crescente."""
    d = (D["F"].get(k) or {}).get("dir")
    if order == "asc": return True
    if order == "desc": return False
    good_low = d == "low"
    if order == "worst": return not good_low
    return good_low  # best ou None: direção "boa" do indicador


def _sector_rows(D, s):
    rx = re.compile(SECTORS[s][1], re.I)
    out = []
    for r in D["rows"]:
        txt = " ".join(x for x in (r.get("setor"), r.get("subsetor"), D["seg"].get(r["ticker"][:4]), r.get("nome")) if x)
        if rx.search(norm(txt)) and not (s == "Bancos" and re.search(r"segur|insur", norm(txt))):
            out.append(r)
    return out


def _passes(D, r, filters):
    for k, op, x in filters:
        v = val(D, r, k)
        if v is None: return False
        if op == ">=" and not v >= x: return False
        if op == "<=" and not v <= x: return False
        if op == ">" and not v > x: return False
        if op == "<" and not v < x: return False
    return True


def _ops(op): return {">=": "≥", "<=": "≤", ">": ">", "<": "<"}[op]


def _rank_metric(k, P):
    """RET em ranking: usa as métricas pré-calculadas (1–5 anos ou ano-calendário)."""
    if k != RET: return k, None
    p = P.get("period")
    if not p: return "ret1", None
    di, df, lab, kind = p
    if kind == "dia": return "var", None
    yrs = (date.fromisoformat(df) - date.fromisoformat(di)).days / 365
    if di.endswith("-01-01") and (df.endswith("-12-31") or df == date.today().isoformat()) and di[:4] == df[:4]: return "anual", di[:4]
    r = round(yrs)
    if r in (1, 2, 3, 4, 5) and abs(yrs - r) < 0.1: return f"ret{r}", None
    return None, None


def ranking(P, D):
    k0 = P["metrics"][0]
    k, year = _rank_metric(k0, P)
    if k is None:
        return "Para ranking de valorização tenho 1, 2, 3, 4 ou 5 anos, o dia de hoje e anos fechados (ex.: “maiores altas em 2024”)."
    rows = _sector_rows(D, P["sector"]) if P["sector"] else list(D["rows"])
    crit = []
    if P["sector"]: crit.append(f"setor {P['sector']}")
    if P.get("ixf"): rows = [r for r in rows if (r.get("ix") or {}).get(P["ixf"])]; crit.append(f"índice {P['ixf']}")
    if not P["illiquid"]:
        rows = [r for r in rows if (val(D, r, "liq2m") or 0) >= 5e5]
        crit.append("liquidez ≥ R$ 500 mil/dia")
    if k == "dy" and not P["illiquid"]:
        rows = [r for r in rows if (val(D, r, "dy") or 0) < 40]; crit.append("DY < 40% (evita distorções, como nos grupos)")
    if P.get("only"): rows = [r for r in rows if P["only"][0](r)]; crit.append(P["only"][1])  # setor exigido pelo método
    if P["filters"]:
        rows = [r for r in rows if _passes(D, r, P["filters"])]
        crit += [f"{label(D, fk)} {_ops(op)} {fmt(D, fk, x)}" for fk, op, x in P["filters"]]

    def get(r):
        if k == "var": return r.get("var")
        if k == "anual": return ((D["M"].get(r["ticker"]) or {}).get("anual") or {}).get(year)
        return val(D, r, k)
    L = [(r, get(r)) for r in rows]
    L = [(r, x) for r, x in L if isinstance(x, (int, float))]
    if k == "anual" and not L:
        return f"Ainda não tenho a variação anual de {year} para montar o ranking. Tenho 1, 2, 3, 4 e 5 anos, o dia de hoje e anos fechados."
    asc = _rank_dir(D, k if k in D["F"] else k0, P["order"])
    if k in D["F"] and D["F"][k].get("neg") and asc: L = [(r, x) for r, x in L if x > 0]; crit.append(f"{label(D, k)} > 0")
    if not P["all_classes"]:  # 1 ticker por empresa (o mais negociado)
        seen, L2 = set(), []
        for r, x in sorted(L, key=lambda z: -D["liq"](z[0])):
            if r["ticker"][:4] in seen: continue
            seen.add(r["ticker"][:4]); L2.append((r, x))
        L = L2; crit.append("1 ticker por empresa")
    L.sort(key=lambda z: z[1], reverse=not asc)
    n = P["n"] or 10
    lab = label(D, k) if k not in ("var", "anual") else ("Variação no dia" if k == "var" else f"Variação em {year}")
    unit_k = k if k not in ("var", "anual") else "ret1"
    if not L:
        return f"Nenhuma ação atende: {lab}" + (" · " + " · ".join(crit) if crit else "") + "."
    if k0 == RET:
        per = {"var": "no dia", "anual": f"em {year}"}.get(k) or "em " + MX[k][0].split(" ", 1)[1]
        head = f"{'Maiores quedas' if asc else 'Maiores altas'} {per}" + (f" — {P['sector']}" if P["sector"] else "") + ":"
    else:
        head = f"{'Menores' if asc else 'Maiores'} {lab}" + (f" — {P['sector']}" if P["sector"] else "") + (f" — {P['ixf']}" if P.get("ixf") else "") + ":"
    lines = [f"{i + 1}. {r['ticker']} ({(r.get('nome') or '')[:30]}): {fmt(D, unit_k, x)}" for i, (r, x) in enumerate(L[:n])]
    tail = f"\nCritérios: {' · '.join(crit)}." if crit else ""
    if len(L) > n: tail += f" Mostrando {n} de {len(L)}."
    return head + "\n" + "\n".join(lines) + tail


def returns(P, D, ret_fn):
    ents = P["tickers"] + P["idx"]
    p = P["period"] or ((date.today() - timedelta(days=365)).isoformat(), date.today().isoformat(), "em 12 meses", "periodo")
    di, df, lab, kind = p
    if kind == "dia":
        out = []
        for t in P["tickers"]:
            v = D["by"][t].get("var")
            out.append((t, v))
        idx = [x for x in P["idx"]]
        R = ret_fn(di, df, []) if idx else {}
        out += [(IDXN[x], R.get(x)) for x in idx]
        lines = [f"• {a}: {_sgn(b)}" if b is not None else f"• {a}: sem dados" for a, b in sorted(out, key=lambda z: -(z[1] if z[1] is not None else -1e9))]
        return "Variação no dia:\n" + "\n".join(lines)
    R = ret_fn(di, df, P["tickers"])
    items = [(x if x in D["by"] else IDXN.get(x, x), R.get(x)) for x in ents]
    items.sort(key=lambda z: -(z[1] if z[1] is not None else -1e9))
    s = f"Variação de preço {lab} ({dbr(di)} a {dbr(df)}):\n" + "\n".join(f"• {a}: {_sgn(b)}" if b is not None else f"• {a}: sem dados" for a, b in items)
    if len(items) >= 2 and items[0][1] is not None and items[-1][1] is not None:
        s += f"\nMaior alta: {items[0][0]}."
    if any(x in D["by"] for x in ents): s += "\n(Variação do preço; proventos não incluídos.)"
    return s


def _sgn(x): return ("+" if x >= 0 else "") + br(x) + "%"


def values(P, D, ks=None):
    ks = ks or [k for k in P["metrics"] if k != RET] or ["preco"]
    lines, red = [], False
    for t in P["tickers"]:
        r = D["by"][t]
        st = r.get("st") or {}
        parts = []
        for k in ks:
            x = val(D, r, k)
            if k == "preco" and x is not None:
                parts.append(f"Cotação: R$ {br(x)}" + (f" ({_sgn(r['var'])} no dia)" if isinstance(r.get("var"), (int, float)) else ""))
                continue
            if x is None:
                parts.append(f"{label(D, k)}: o site não tem esse dado")
                continue
            note = {"red": " (fontes sem maioria)", "amb": " (maioria das fontes)"}.get(st.get(k), "")
            red = red or st.get(k) == "red"
            parts.append(f"{label(D, k)}: {fmt(D, k, x)}{note}")
        lines.append(f"{t} — " + " · ".join(parts) if len(parts) <= 2 else f"{t} ({(r.get('nome') or '')[:30]}):\n" + "\n".join("• " + p for p in parts))
    s = "\n".join(lines)
    if len(P["tickers"]) >= 2 and len(ks) == 1 and ks[0] != "preco":
        vs = [(t, val(D, D["by"][t], ks[0])) for t in P["tickers"] if val(D, D["by"][t], ks[0]) is not None]
        if len(vs) >= 2:
            want_low = bool(re.search(r"\bmenor\b", P["nq"]))
            best = (min if want_low else max)(vs, key=lambda z: z[1])
            s += f"\n{'Menor' if want_low else 'Maior'} {label(D, ks[0])}: {best[0]}."
    if red:
        s += "\n“Fontes sem maioria” = os sites de dados divergem; o valor exibido segue a regra de consenso (veja ⓘ no topo)."
    return s


CMP_KEYS = ["dy", "pl", "pvp", "roe", "mliq", "dlebit"]


def compare(P, D):
    """Ações lado a lado: valor de cada indicador, a melhor em cada um (direção do indicador) e um resumo."""
    T = P["tickers"][:4]; wins = {t: 0 for t in T}; n = 0; lines = []
    for k in CMP_KEYS:
        f = D["F"].get(k) or {}
        vs = [(t, val(D, D["by"][t], k)) for t in T]
        if all(x is None for _, x in vs): continue
        ok = [(t, x) for t, x in vs if x is not None and not (f.get("neg") and x <= 0)]
        best = None
        if len(ok) >= 2:
            best = (min if f.get("dir") == "low" else max)(ok, key=lambda z: z[1])[0]; wins[best] += 1; n += 1
        lines.append(f"• {label(D, k)}: " + " · ".join(f"{t} {fmt(D, k, x) if x is not None else '—'}" for t, x in vs) + (f" → melhor: {best}" if best else ""))
    rk = sorted(wins.items(), key=lambda z: -z[1])
    price = " · ".join(f"{t} R$ {br(val(D, D['by'][t], 'preco'))}" for t in T if val(D, D["by"][t], "preco") is not None)
    summ = f"Resumo: {rk[0][0]} se sai melhor em {rk[0][1]} de {n} indicadores" + "".join(f"; {t} em {w}" for t, w in rk[1:]) + ". Não é recomendação de compra."
    return "Comparação " + " x ".join(T) + ":\nCotação: " + price + "\n" + "\n".join(lines) + "\n" + summ


def fg_data():
    """Índice de Medo e Ganância (snapshot fg, scripts/build_fg.py) ou None."""
    try:
        import snapshots
        return snapshots.load("fg", max_mem_age=3 * 3600)[0]
    except Exception as e:
        log.info("fg: %s", e); return None


def fg_band(v, fx):
    return next((n for lim, n in fx if v <= lim), fx[-1][1])


def fg_answer():
    """'Como está o mercado?' -> índice de hoje, ontem/1 semana/1 mês e a explicação do Glossário do painel ⓘ."""
    d = fg_data()
    if not d or not d.get("v"): return "O Índice de Medo e Ganância ainda não foi calculado (sai na rotina diária de dados)."
    v, fx = d["v"], d["faixas"]
    ago = [(l, v[-1 - n]) for l, n in (("ontem", 1), ("1 semana", 5), ("1 mês", 21)) if len(v) > n]
    g = glossary().get("medo", "")  # "Medo e Ganância" no Glossário (o nome é dividido no " e ")
    return (f"Medo e Ganância (B3): **{v[-1]} — {fg_band(v[-1], fx)}** ({dbr(d['d'][-1])}). "
            + " · ".join(f"{l.capitalize()} {x} ({fg_band(x, fx)})" for l, x in ago) + (f"\n\n{g}" if g else ""))


def fair(D, r):
    """Barato/Caro com os valores de consenso: valor_justo.fair (a mesma conta de app.js → fairOf). -> (justo, %, preço, método) ou None"""
    import valor_justo
    j, pct, m = valor_justo.fair(r, lambda o, k: val(D, o, k), list(D["by"].values()))
    return (j, pct, val(D, r, "preco"), m) if j else None


def fair_answer(P, D):
    import valor_justo
    out = []
    for t in P["tickers"][:4]:
        f = fair(D, D["by"][t])
        if not f:
            v = lambda k: fmt(D, k, val(D, D["by"][t], k))
            _, why, _ = valor_justo.fair(D["by"][t], lambda o, k: val(D, o, k), list(D["by"].values()))
            out.append(f"{t}: sem Barato/Caro — {valor_justo.rotulo(why)[0]} ({why}; preço {v('preco')}, LPA {v('lpa')}, VPA {v('vpa')})."); continue
        j, pct, p, m = f
        out.append(f"{t}: " + ("0%: no valor justo" if pct == 0 else f"{'+' if pct >= 0 else '−'}{br(abs(pct), 0)}% {'até o' if pct >= 0 else 'acima do'} valor justo") + f" (valor justo ({m}) R$ {br(j)}; preço R$ {br(p)})")
        al = __import__("valor_justo").alertas(D["by"][t], val(D, D["by"][t], "dy"))  # ⚠️ do card (Glossário: Alertas)
        if al:
            nm = {"divida": lambda x: f"dívida líquida {br(x)}× o EBITDA", "dy": lambda x: f"DY de {br(x)}%", "payout": lambda x: f"payout de {br(x, 0)}%"}
            out[-1] += " ⚠️ " + "; ".join(nm[k](x) for k, x in al)
    g = glossary().get("barato/caro", "")
    return "\n".join(out) + (f"\n\n{g}" if g else "")


def day_move(P, D):
    """“Caiu/subiu hoje?”: só a variação do dia (o site não tem notícias para explicar o motivo)."""
    out = []
    for t in P["tickers"]:
        r = D["by"][t]; v, p = r.get("var"), val(D, r, "preco")
        out.append(f"{t}: {_sgn(v) + ' hoje' if v is not None else 'sem variação registrada hoje'}" + (f" (R$ {br(p)})" if p is not None else ""))
    s = "\n".join(out)
    if re.search(r"\b(por que|porque|motivo|razao)\b", P["nq"]):
        s += "\nO site não acompanha notícias, então não sabe o motivo da variação. Veja os fatos relevantes no site de RI da empresa ou na B3."
    return s


def quote(P, quote_fn):
    """Cotação atual de dólar, ouro e Ibovespa (mesmos dados dos gráficos)."""
    L = []
    for k in P["idx"]:
        x = quote_fn(k) if quote_fn else None
        if x: L.append(f"{IDXN[k]}: " + (f"R$ {br(x[1])}" + (" por onça" if k == "@gold" else "") if k in ("@usd", "@gold") else f"{br(x[1])} pts") + f" (fechamento de {dbr(x[0])})")
    return "\n".join(L) if L else None


def card(D, t):
    r = D["by"][t]; v = r.get("v") or {}; m = D["M"].get(t) or {}
    keys = [k for k in ("preco", "dy", "pl", "pvp", "roe", "roic", "mliq", "dlpl", "dlebit", "lpa", "vpa", "valmerc", "liq2m") if v.get(k) is not None]
    s = f"{t} — {r.get('nome', '')} · {r.get('setor') or ''}\n" + "; ".join(f"{label(D, k)}: {fmt(D, k, v[k])}" for k in keys)
    st = r.get("st") or {}
    if st: s += "\nDivergência entre fontes: " + ", ".join(f"{label(D, k)} ({'sem maioria' if x == 'red' else 'maioria'})" for k, x in st.items())
    if r.get("ix"): s += "\nÍndices B3: " + ", ".join(r["ix"].keys())
    if r.get("tags"): s += "\nEtiquetas: " + ", ".join(r["tags"])
    mm = [f"{MX[k][0]}: {fmt(D, k, m[k])}" for k in MX if m.get(k) is not None]
    if mm: s += "\n" + "; ".join(mm)
    if m.get("anual"): s += "\nVariação anual: " + "; ".join(f"{y}: {_sgn(x)}" for y, x in sorted(m["anual"].items())[-5:] if isinstance(x, (int, float)))
    if m.get("ytd"): s += "\nProventos no ano: " + "; ".join(f"{e[0]} R$ {br(e[1], 4)} ({e[2]})" for e in m["ytd"][:8])
    return s


def execute(P, D, ret_fn):
    """Responde com os dados do site a partir da interpretação. None = não sabe responder."""
    T, I, K = P["tickers"], P["idx"], P["metrics"]
    K2 = [k for k in K if k != RET]
    if P.get("unknown_tickers") and not T and not I:
        return " ".join(P["notes"])
    pre = ""
    if P["fixes"]: pre += "(Entendi: " + ", ".join(f"“{b}”" for a, b in P["fixes"]) + ")\n"
    if P["notes"]: pre += " ".join(P["notes"]) + "\n"
    if I and not T:
        if "preco" in K: pre += "O site não mostra a cotação de índices/dólar, só a variação no período.\n"
        return pre + returns(P, D, ret_fn)
    if T:
        if K2:
            s = values(P, D)
            if RET in K or I: s += "\n\n" + returns(P, D, ret_fn)
            return pre + s
        if RET in K or I or P["period"]:
            return pre + returns(P, D, ret_fn)
        if len(T) == 1: return pre + card(D, T[0])
        return pre + compare(P, D) + "\n\n" + returns(P, D, ret_fn)
    if K:
        listy = P["sector"] or P.get("ixf") or P["filters"] or P["order"] or P["n"] or re.search(r"\b(quais|qual|liste|lista|listar|ranking|top|acoes|empresas)\b", P["nq"])
        if listy: return pre + ranking(P, D)
        return None
    if P["sector"]:
        return pre + ranking(dict(P, metrics=["valmerc"], order="desc"), D)
    return None


# ============================================================ guia, glossário, cores, como usar
_GUIDE = None
_LABELS = None


def site_name():
    """Nome do site = parte antes de " — " no <title> do index.html (mesma fonte do nome do app instalável)."""
    try:
        return re.search(r"<title>(.*?)</title>", open(os.path.join(BASE, "index.html"), encoding="utf-8").read()).group(1).split(" — ")[0]
    except Exception:
        return ""


def guide():
    """Guia do site = painel ⓘ (#infoModal do index.html). Fonte única das explicações, do passo a passo e do glossário."""
    global _GUIDE
    if _GUIDE is None:
        try:
            s = open(os.path.join(BASE, "index.html"), encoding="utf-8").read()
            i = s.index('<div id="infoModal"'); j = s.index("<script", i); t = s[i:j]
            t = re.sub(r"<ol[^>]*>(.*?)</ol>", lambda m: "".join(f"\n{k}. {x}" for k, x in enumerate(re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.S), 1)), t, flags=re.S)
            t = re.sub(r"<(summary|h\d)[^>]*>", "\n## ", t); t = re.sub(r"<li[^>]*>|<p[^>]*>", "\n- ", t); t = re.sub(r"<[^>]+>", "", t)
            t = _html.unescape(t); t = re.sub(r"[ \t]+", " ", t); _GUIDE = re.sub(r"\n\s*\n+", "\n", t).replace("✕", "").strip()
        except Exception:
            _GUIDE = ""
    return _GUIDE


def guide_sections():
    out, cur = {}, None
    for l in guide().split("\n"):
        if l.startswith("## "): cur = l[3:].strip(); out[cur] = []
        elif cur: out[cur].append(l)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def glossary():
    """Termos da seção Glossário do painel ⓘ -> {termo normalizado: "Termo (sigla): definição"}."""
    out = {}
    for l in guide_sections().get("Glossário", "").split("\n"):
        l = l.strip("- ").strip()
        head, _, _ = l.partition(": ")
        if not head: continue
        m = re.match(r"^([^(]+?)\s*(?:\((.+)\))?$", head)
        names = re.split(r",\s*|\s+e\s+", m.group(1)) + ([m.group(2)] if m.group(2) else [])
        for n in names:
            if n.strip(): out[norm(n.strip())] = l
    return out


def ui_labels():
    """Nomes reais de botões, abas, campos e opções, lidos da interface (index.html e *.js) — nunca uma lista à parte."""
    global _LABELS
    if _LABELS is None:
        found = set()
        for fn in ["index.html"] + sorted(f for f in os.listdir(BASE) if f.endswith(".js") and f != "tailwind.config.js"):
            try: s = open(os.path.join(BASE, fn), encoding="utf-8").read()
            except OSError: continue
            if fn == "index.html": s = s[:s.find('<div id="infoModal"')] + s[s.find("</div>\n</div>", s.find('<div id="infoModal"')):]
            raw = re.findall(r"<(?:button|summary|option|label|h[1-4])\b[^>]*>(.*?)</(?:button|summary|option|label|h[1-4])>", s, re.S)
            raw += re.findall(r'(?:placeholder|aria-label)="([^"]{2,40})"', s)
            for x in raw:
                x = _html.unescape(re.sub(r"<[^>]+>", " ", x))
                if "$" in x or "{" in x or "=" in x: continue
                x = re.sub(r"[＋+⇅★☆↓↑⟳✕✓✏⠿▾▴…→←·]|^\W+|\W+$", " ", x).strip()
                x = re.sub(r"\s+", " ", x)
                if 2 <= len(x) <= 40 and re.search(r"[A-Za-zÀ-ú]", x): found.add(x)
        _LABELS = sorted(found, key=norm)
    return _LABELS


# palavra do usuário -> termo do Glossário do painel ⓘ (só o vocabulário; as definições ficam no painel)
GLOSS_SYN = VOC["glossario"]
# assunto da pergunta -> seções do painel ⓘ (títulos <h3>/<summary>); o texto fica só no painel
HOWTO_KEYS = [
    (("grupo simulacao", "grupo de simulacao", "carteira por modelo", "simulacao ate hoje", "desde a data inicial"), ["Grupos", "Modelos da Previsão"]),
    (("metodo de investimento", "metodos de investimento", "estrategia de investimento"), ["Métodos de investimento"]),
    (("carteira", "posicao", "posicoes", "preco medio"), ["Carteira"]),
    (("alerta", "sininho", "avisar", "aviso de preco", "notifica"), ["Favoritos"]),
    (("previsao aluguel", "previsao de aluguel", "aluguel", "alugar"), ["Previsão aluguel"]),
    (("acoes inteiras", "fracao de acao", "fracoes", "reserva da empresa", "jcp nos modelos", "movimentacoes do modelo", "aplicacao no cdi", "resgate do cdi", "preco medio", "aporte mensal no grupo simulacao", "retirada no grupo simulacao", "valor aportado", "origem/destino", "origem destino", "valor acao", "historico da empresa no modelo", "proventos recebidos"), ["Modelos da Previsão"]),
    (("modelos da previsao", "modelo de investimento", "modelos de investimento", "rodizio", "algoritmo", "comprar e segurar", "hibrido", "adaptativo", "aprende"), ["Modelos da Previsão"]),
    (("previsao rentab", "rentabilidade", "previsao", "simula", "simulacao", "projecao", "projecoes", "aporte"), ["Previsão rentabilidade"]),
    (("compar",), ["Comparar"]),
    (("favorit", "estrela"), ["Favoritos"]),
    (("reorganiz", "arrastar", "reordenar", "mudar a ordem", "trocar a ordem"), ["Reorganizar"]),
    (("widget", "widget grupo simulacao", "widget de simulacao", "carteira do widget", "planilha do grupo simulacao", "baixar planilha", "xlsx", "exportar excel", "atualizacao do app", "apk", "app android", "app do android", "aplicativo android", "logo da empresa", "logos das empresas", "logotipo"), ["App Android"]),
    (("instal", "aplicativo", "baixar o app", "baixar app", "tela inicial", "app no celular", "como app"), ["Instalar o app"]),
    (("importar", "exportar grupo", "exportar os grupos", "backup", "outro aparelho", "outro celular"), ["Grupos (criar e editar)"]),
    (("export", "csv", "baixar", "planilha", "excel", "download"), ["Exportar (CSV)"]),
    (("atualiz", "recarreg", "dados novos", "dados atualizados"), ["Atualizar dados"]),
    (("consenso",), ["Regras de mescla (modo “Todos”)", "Fontes e consenso"]),
    (("fonte", "fontes", "todos"), ["Fontes e consenso"]),
    (("pais", "paises", "eua", "estados unidos", "exterior"), ["País"]),
    (("grupo",), ["Grupos (criar e editar)"]),
    (("filtr", "ordenar", "ordena", "busca", "pesquis", "procurar"), ["Filtros e ordenação"]),
    (("chat",), ["Chat"]),
    (("acoes", "acao", "aba acoes", "aba mercado", "cards", "card"), ["Mercado"]),
]
_LN = None


def fake_label(q, P):
    """Se a pergunta cita um botão/opção/aba que não existe no site, devolve a resposta; senão None."""
    global _LN
    if P["tickers"] or P["metrics"] or P["sector"] or P["idx"]: return None
    nq = P["nq"]
    m = re.search(r"\b(?:botao|botoes|aba|abas|menu|icone|toggle|link)\s+(?:de |do |da |chamad[oa] |com o nome |com nome )?[\"'“]?([^\"'”?.,!]{2,40})", nq)
    if not m and re.search(r"\b(site|tela|app|aplicativo|clic|toc|aperto|apertar)\w*", nq):
        m = re.search(r"\b(?:opcao|opcoes|campo|funcao|recurso)\s+(?:de |do |da |chamad[oa] )?[\"'“]?([^\"'”?.,!]{2,40})", nq)
    if not m: return None
    labels = ui_labels()
    if _LN is None: _LN = [norm(x).strip() for x in labels]
    name = re.sub(r"\b(no|na|do|da|de|que|para|pra|onde|como|fica|esta|nao|existe|aparece|site|tela|app|aqui|ai|la)\b.*$", "", m.group(1)).strip()
    if len(name) < 2: return None
    sing = re.sub(r"(oes|aes)$", "ao", name); sing = re.sub(r"(?<=[rzl])es$", "", sing); sing = re.sub(r"(?<=[a-z])s$", "", sing)
    W = set(" ".join(_LN).split()) | {"o", "a", "os", "as", "e", "de"}
    g = norm(guide())
    if any(name in l or sing in l for l in _LN) or all(w in W for w in name.split()) or (len(sing) >= 4 and sing in g): return None
    for keys, _ in HOWTO_KEYS:
        if any(k in name for k in keys): return None
    near = difflib.get_close_matches(sing, _LN, 1, 0.55)
    sug = f" A opção real mais próxima parece ser \"{labels[_LN.index(near[0])]}\"." if near else ""
    return (f"Não encontrei a opção \"{m.group(1).strip()}\" no site. Pode olhar de novo e me descrever exatamente o que aparece na tela "
            f"(nome do botão/texto), ou contar passo a passo como chegou nesse lugar? Assim consigo verificar se há alguma divergência.{sug}")


def define(P):
    """Definição de um termo: Glossário do painel ⓘ; senão uma seção do painel com esse nome; senão as linhas que o citam."""
    nq = P["nq"]
    m = re.search(r"\b(?:o que (?:e|sao|significa|quer dizer)|que e|significado d[eoa]s?|significa|defin[ae]|definicao d[eoa]s?|conceito d[eoa]s?)\b\s*(?:o |a |os |as |um |uma )?(.+)$", nq)
    term = (m.group(1) if m else nq).strip(" ?")
    term = re.sub(r"\b(no site|aqui|na tela|no app)\b", "", term).strip()
    if not term: return None
    if re.search(r"\balertas? de preco|\bfavorit", term):  # alerta de preço dos Favoritos ≠ Alertas (⚠️) do Barato/Caro (Glossário)
        h = howto(dict(P, nq=term))
        if h: return h
    G = glossary()
    t = GLOSS_SYN.get(term, term)
    if t in G: return G[t]
    for g in sorted(G, key=len, reverse=True):
        if re.search(r"(?<![a-z])" + re.escape(g) + r"(?![a-z])", term): return G[g]
    for w in sorted(GLOSS_SYN, key=len, reverse=True):
        if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", term) and GLOSS_SYN[w] in G: return G[GLOSS_SYN[w]]
    for keys, titles in HOWTO_KEYS:  # assunto com seção própria no painel (ex.: consenso)
        if any(norm(term) == k or norm(term) == k + "s" for k in keys) and not keys[0] in ("acoes", "chat"):
            h = howto(dict(P, nq=term))
            if h: return h
    if len(term) >= 4:
        secs = guide_sections()
        for title, body in secs.items():
            if body and term in norm(title): return f"{title}:\n{body}"
        lines = [l.strip("- ").strip() for l in guide().split("\n") if term in norm(l) and not l.startswith("## ")]
        if lines: return "Do guia do site (ⓘ):\n" + "\n".join("• " + h for h in lines[:3])
    return None


def colors_text():
    c = guide_sections().get("Cores", "")
    return ("Cores (painel ⓘ):\n" + c) if c else None


def howto(P):
    nq = P["nq"]; secs = guide_sections()
    for keys, titles in HOWTO_KEYS:
        if any(w in nq for w in keys):
            parts = [f"{t}:\n{secs[t]}" for t in titles if secs.get(t)]
            if parts: return "\n\n".join(parts)
    return None


def suggestions(P, D):
    T, K = P["tickers"], [k for k in P["metrics"] if k != RET]
    if P["idx"] and not T:
        nm = IDXN[P["idx"][0]]
        return [f"{nm} rendeu quanto em 1 ano?", f"Quanto está o {nm} hoje?"] + ([f"{nm} vs Ibovespa em 2 anos"] if P["idx"][0] != "@ibov" else ["Ibovespa vs Dólar em 2 anos"])
    if T:
        t = T[0]
        return [f"DY e P/L da {t}", f"{t} rendeu quanto em 1 ano?", f"{t} vs Ibovespa em 2 anos", f"Resumo da {t}"]
    if K:
        lab = label(D, K[0])
        return [f"Maiores {lab}", f"{lab} dos bancos", f"Ações com {lab} acima de 10", f"O que é {lab}?"]
    if P["sector"]:
        return [f"Maiores DY — {P['sector']}", f"Menores P/L — {P['sector']}", f"Maior ROE — {P['sector']}"]
    return ["DY do BBAS3", "Maiores DY dos bancos", "PETR4 vs Ibovespa em 2024", "Ações com ROE acima de 20 e P/L abaixo de 8"]


# Métodos de investimento: texto no painel ⓘ (seção do método) + ações do site que passam em critérios aproximados do método
# setores perenes do Barsi: fonte única em modelos.PERENE_RX / PERENE_TXT
def _besst(r):
    import modelos
    return modelos.perene(r)
def _perene_txt():
    import modelos
    return "setores perenes (" + modelos.PERENE_TXT + ")"
PERENE = (_besst, _perene_txt())
METHODS = [(r"\bbarsi\b", "Método Barsi", [("dy", ">=", 6), ("roe", ">=", 10), ("dlebit", "<=", 3)], "dy", "desc", None, PERENE),
           (r"\bbazin\b", "Método Bazin", [("dy", ">=", 6), ("dlpl", "<=", 0.5), ("pl", ">", 0)], "dy", "desc", None, None),
           (r"\bgraham\b", "Método Graham", [("pl", ">", 0), ("pl", "<=", 15), ("pvp", ">", 0), ("pvp", "<=", 1.5)], "pvp", "asc", None, None),
           (r"\bbuff?ett?\b", "Método Buffett", [("roe", ">=", 15), ("mliq", ">=", 10), ("dlebit", "<=", 2)], "roe", "desc", None, None),
           (r"\b(formula magica|magic formula|greenblatt)\b", "Fórmula Mágica", [("evebit", ">", 0), ("evebit", "<=", 10), ("roic", ">=", 15)], "roic", "desc", None, None),
           (r"\bsmall ?caps?\b", "Small caps", [("roe", ">=", 10), ("dlebit", "<=", 3)], "roe", "desc", "SMLL", None),
           (r"\b(growth|crescimento)\b", "Dividendos x Crescimento", [("lucro5a", ">=", 15), ("pl", ">", 0)], "lucro5a", "desc", None, None)]


def method(P, D):
    """'como monto uma carteira pelo método X' / 'o que é o método X' -> seção do painel + ações que passam nos critérios."""
    nq = P["nq"]
    if not re.search(r"\b(metodos?|estrategias?|carteira|formula magica|magic formula|barsi|bazin|greenblatt)\b", nq): return None
    secs = guide_sections()
    if re.search(r"\b(metodos|estrategias)\b", nq) and not any(re.search(rx, nq) for rx, *_ in METHODS):
        return "Métodos de investimento (painel ⓘ):\n" + secs.get("Métodos de investimento", "") + "\n\nMétodos: " + ", ".join(t for _, t, *_ in METHODS) + "."
    for rx, title, filt, k, order, ixf, only in METHODS:
        if re.search(rx, nq):
            txt = f"{title}:\n{secs.get(title, '')}"
            if not re.search(r"\b(carteira|montar|monto|monte|quais|acoes|lista)\b", nq): return txt
            P2 = dict(P, metrics=[k], filters=filt, order=order, n=P["n"] or 10, sector=None, ixf=ixf or P.get("ixf"), only=only)
            return txt + "\n\nAções do site que passam em critérios aproximados do método (estudo, não recomendação):\n" + ranking(P2, D)
    return None


def local(q, D, ret_fn, cx, P=None, quote_fn=None):
    """Resposta sem IA quando a interpretação é confiável. -> texto ou None."""
    P = P or parse(q, D)
    nq = P["nq"]
    if P["complaint"]: return None
    today = not P["period"] or P["period"][3] == "dia"
    if P["tickers"] and today and re.search(r"\b(hoje|hj|no dia|agora)\b", nq) and re.search(r"\b(caiu|cai|caindo|subiu|sobe|subindo|variou|variacao|por que|motivo)\b", nq):
        return day_move(P, D)
    if P["idx"] and not P["tickers"] and today and not P["metrics"][1:] and re.search(r"\b(quanto|cotacao|valor|preco|hoje|esta|custa)\b", nq):
        a = quote(P, quote_fn)
        if a: return a
    if P.get("unknown_tickers") and not P["tickers"]: return " ".join(P["notes"])
    if re.fullmatch(r"(oi|ola|bom dia|boa tarde|boa noite|e ai|opa|hello|hi)( tudo bem| tudo bom)?", nq):
        return frase("ola", P["hist"])
    if re.fullmatch(r"(obrigad[oa]|valeu|beleza|ok|show|perfeito|otimo|blz|top)( mesmo)?", nq):
        return frase("obrigado", P["hist"])
    fk = fake_label(q, P)
    if fk: return fk
    if not P["tickers"] and re.search(r"\b(medo|ganancia|gananciosos?|sentimento do mercado|humor do mercado|como (esta|anda) o mercado|termometro do mercado)\b", nq):
        return fg_answer()
    if P["tickers"] and re.search(r"\b(barat[ao]s?|car[ao]s?|valor justo|preco justo|graham|subvalorizad\w*|sobrevalorizad\w*|descontad\w*)\b", nq):
        return fair_answer(P, D)
    m = method(P, D)
    if m: return m
    if P["colors"] and not P["tickers"]: return colors_text()
    if (P["howto"] or re.search(r"\baba\b", nq)) and not P["tickers"] and not P["idx"]:
        h = howto(P)
        if h: return h
        return None
    if P["define"] and not P["tickers"] and not re.search(r"\b(por que|porque|explique|explica|analis\w*|devo|vale a pena|compensa|opiniao|recomend\w*|investir|comprar|vender)\b", nq):
        d = define(P)
        if d: return d
        return None
    if not P["tickers"] and not P["idx"] and not P["sector"] and not P["order"] and not P["filters"] and not P["n"] and len(nq.split()) <= 3:
        d = define(dict(P, nq="o que e " + nq))  # termo solto: “ebitda?”
        if d: return d
    if cx.get("groups") and ("grupo" in nq or "quem esta" in nq or "quais estao" in nq):
        for line in str(cx["groups"]).split("\n"):
            name = norm(line.split(":")[0].split("[")[0]).strip()
            if name and name in nq: return line
    if not confident(P): return None
    return execute(P, D, ret_fn)


def rules(q, D, ret_fn, P=None):
    """Melhor esforço sem IA (quando a IA não está disponível)."""
    P = P or parse(q, D)
    try:
        a = execute(P, D, ret_fn)
    except Exception as e:
        log.info("rules: %s", e); a = None
    if a: return a
    if P["define"] or (P["metrics"] and not P["tickers"]):
        d = define(P)
        if d: return d
    h = howto(P) if (P["howto"] or "aba" in P["nq"]) else None
    if h: return h
    near = []
    for w in P["left"]:
        if len(w) >= 5: near += difflib.get_close_matches(w, list(D["alias"]) + list(D["tok"]), 1, 0.85)
    if not near and not P["tickers"]:
        f = search(P["nq"])
        if f:
            src, title, body = f
            body = f"{title}: {_sentences(body, 3)}" if src == "kb" else body if src == "glos" else f"{title}:\n{body[:900]}"
            return frase("busca", P["hist"]) + "\n" + body
    extra = f" Você quis dizer “{near[0]}”?" if near else ""
    return "Não consegui entender essa pergunta só com as regras do site." + extra + frase("nao_entendi", P["hist"])



# ============================================================ chat guiado (intencoes.json) e escrita livre por intenção
INT = json.load(open(os.path.join(BASE, "intencoes.json"), encoding="utf-8"))  # menu guiado e frases de exemplo (fonte única)


def menu(D):
    """Menu do chat guiado: intencoes.json + listas lidas do site (indicadores de /api/data, setores do chat, seções do painel ⓘ)."""
    ind = [[k, f["label"]] for k, f in D["F"].items() if k not in ("preco",)]
    secs = [k for k in guide_sections() if k and k not in ("Glossário",)]
    return dict(INT, listas={"ind": ind, "setor": list(SECTORS), "secao": secs})


def _P0(D, **kw):
    P = parse("", D); P.update(kw); return P


def _top(D, rows, k, n, asc=False, f=None):
    """[(linha, valor)] dos n primeiros por k (1 ticker por empresa, com liquidez), f = filtro extra."""
    L = [(r, val(D, r, k) if k != "var" else r.get("var")) for r in rows if (val(D, r, "liq2m") or 0) >= 5e5 and (f is None or f(r))]
    L = [(r, x) for r, x in L if isinstance(x, (int, float))]
    seen, out = set(), []
    for r, x in sorted(L, key=lambda z: z[1], reverse=not asc):
        if r["ticker"][:4] in seen: continue
        seen.add(r["ticker"][:4]); out.append((r, x))
        if len(out) >= n: break
    return out


def _linhas(D, L, k):
    return "\n".join(f"{i + 1}. {r['ticker']} ({(r.get('nome') or '')[:28]}): " + (_sgn(x) if k == "var" else fmt(D, k, x)) for i, (r, x) in enumerate(L))


def _fg_acao(D, t):
    v = (D["by"][t].get("fg") or [None])[0]
    if v is None: return f"{t}: sem Medo e Ganância da ação."
    d = fg_data(); fx = (d or {}).get("faixas")
    return f"{t}: Medo e Ganância da ação **{v}" + (f" — {fg_band(v, fx)}" if fx else "") + "**"


def _noticias(itens, a="todas", T=None, n=5):
    """Últimas n notícias (aba Notícias) do assunto a e que citam as empresas T (raízes) — None = todas."""
    rt = {t[:4] for t in T} if T is not None else None
    L = [x for x in itens or [] if (a == "todas" or a in (x.get("a") or [])) and (rt is None or any(t[:4] in rt for t in x.get("t") or []))]
    L.sort(key=lambda x: x.get("data") or "", reverse=True)
    if not L: return "Nenhuma notícia encontrada com esse filtro agora."
    return "\n".join(f"• {dbr(x.get('data'))} — {x.get('titulo')} ({x.get('fonte') or ''}) {x.get('url') or ''}" for x in L[:n])


def _pre_todas(pre, meses=121):
    """Comparar → Modelos pré-calculado (snapshot modelos_pre): o de Todas com o período pedido (121 meses = 10 anos)."""
    E = [x for x in ((pre or {}).get("e") or {}).values() if x.get("meses") == meses]
    return max(E, key=lambda x: x.get("pedidas") or 0) if E else None


def guiada(f, a, D, ret_fn=None, quote_fn=None, fx=None):
    """Resposta de um caminho do chat guiado (intencoes.json → f) com os dados do site. a: empresa (e), empresa2 (e2), indicador (k),
    período (per), escopo (esc: geral/empresa/fav), escopo2 (esc2: geral/setor/fav), setor, secao, favoritos (fav), carteira (cart) e os
    argumentos fixos do nó (o, i, a; de = empresa/setor nas notícias). -> texto."""
    import modelos
    fx = fx or {}; T = [t for t in (a.get("e") or []) if t in D["by"]]; FAV = [t for t in (a.get("fav") or []) if t in D["by"]]
    esc = a.get("esc") or ("empresa" if T else "geral")
    alvo = T if esc == "empresa" else FAV if esc == "fav" else None
    if esc == "fav" and not FAV: return "Você ainda não tem Favoritos (☆ nos cards da aba Mercado)."
    if f in ("resumo", "ind", "div", "ret", "cmp", "cmpidx", "modelos_emp") and not T: return "Escolha a empresa primeiro."
    P = _P0(D, tickers=T)
    if f == "resumo":
        r = D["by"][T[0]]
        return "\n".join(x for x in [values(_P0(D, tickers=T), D, ["preco", "dy", "pl", "pvp", "roe"]), fair_answer(P, D).split("\n\n")[0], _fg_acao(D, T[0])] if x)
    if f == "ind":
        k = a.get("k") if a.get("k") in D["F"] else "pl"
        return values(_P0(D, tickers=T, metrics=[k]), D, [k])
    if f == "div":
        m = D["M"].get(T[0]) or {}; r = D["by"][T[0]]
        s = values(P, D, ["dy"]) + "".join(f"\n{MX[k][0]}: {fmt(D, k, m[k])}" for k in ("dy1", "prov12") if m.get(k) is not None)
        if m.get("ytd"): s += "\nProventos no ano: " + "; ".join(f"{e[0]} R$ {br(e[1], 4)} ({e[2]})" for e in m["ytd"][:8])
        return s + "\n" + fair_answer(P, D).split("\n\n")[0]
    if f in ("ret", "cmpidx"):
        per = _period(norm(a.get("per") or "1 ano")) or _period("1 ano")
        return returns(_P0(D, tickers=T, idx=[a["i"]] if f == "cmpidx" else [], period=per), D, ret_fn)
    if f == "cmp":
        T2 = T + [t for t in (a.get("e2") or []) if t in D["by"] and t not in T]
        if len(T2) < 2: return "Escolha a outra empresa."
        P2 = _P0(D, tickers=T2[:4])
        return compare(P2, D) + "\n\n" + returns(dict(P2, period=_period("1 ano")), D, ret_fn)
    if f == "noticias":
        itens = (fx.get("news") or (lambda: []))()
        if a.get("de") == "setor" or (a.get("setor") and esc == "geral"): alvo = [r["ticker"] for r in _sector_rows(D, a.get("setor"))] if a.get("setor") else None
        if a.get("de") == "empresa": alvo = T
        return _noticias(itens, a.get("a") or "todas", alvo)
    if f == "destaques":
        if esc == "geral":
            rows = D["rows"]; up, dn = _top(D, rows, "var", 5), _top(D, rows, "var", 5, asc=True)
            d = fg_data(); fg = f"\n\nMedo e Ganância (B3): {d['v'][-1]} — {fg_band(d['v'][-1], d['faixas'])}" if d and d.get("v") else ""
            nw = (fx.get("news") or (lambda: []))()
            return "Maiores altas de hoje:\n" + _linhas(D, up, "var") + "\n\nMaiores baixas de hoje:\n" + _linhas(D, dn, "var") + fg + ("\n\nÚltimas notícias:\n" + _noticias(nw, n=3) if nw else "")
        L = sorted(((t, D["by"][t].get("var")) for t in alvo), key=lambda z: -(z[1] if z[1] is not None else -1e9))
        s = "Hoje:\n" + "\n".join(f"• {t}: {_sgn(x) if x is not None else 'sem variação'}" + (f" (R$ {br(val(D, D['by'][t], 'preco'))})" if val(D, D["by"][t], "preco") is not None else "") for t, x in L)
        nw = (fx.get("news") or (lambda: []))()
        return s + ("\n\nNotícias:\n" + _noticias(nw, T=alvo, n=3) if nw else "")
    if f == "fg":
        if esc == "geral": return fg_answer()
        return "\n".join(_fg_acao(D, t) for t in alvo)
    if f == "macro":
        s = quote(_P0(D, idx=["@ibov", "@usd", "@gold"]), quote_fn) or ""
        return (s + "\n\n" + returns(_P0(D, idx=["@ibov", "@usd"], period=_period("hoje")), D, ret_fn)).strip()
    if f in ("encontrar", "setor"):
        o = a.get("o"); sec = a.get("setor") if (f == "setor" or a.get("esc2") == "setor") else None
        rows = _sector_rows(D, sec) if sec else list(D["rows"])
        if f == "encontrar" and a.get("esc2") == "fav" or o == "fav":
            if not FAV: return "Você ainda não tem Favoritos (☆ nos cards da aba Mercado)."
            rows = [r for r in rows if r["ticker"] in FAV]
            if o == "fav": return f"Seus favoritos em {sec}:\n" + ("\n".join(f"• {r['ticker']}: R$ {br(val(D, r, 'preco'))} ({_sgn(r['var'])} hoje)" if r.get("var") is not None else f"• {r['ticker']}" for r in rows) or "nenhum.")
        tit = f" — {sec}" if sec else " — seus favoritos" if a.get("esc2") == "fav" else ""
        if o in ("bar",):
            L = []
            for r in rows:
                fr = fair(D, r)
                if fr and (val(D, r, "liq2m") or 0) >= 5e5: L.append((r, fr[1]))
            L = sorted(L, key=lambda z: -z[1])[:10]
            return (f"Mais baratas pelo valor justo{tit} (% até o valor justo):\n" + "\n".join(f"{i + 1}. {r['ticker']}: {'+' if x >= 0 else '−'}{br(abs(x), 0)}%" for i, (r, x) in enumerate(L))) if L else "Nenhuma com valor justo calculado."
        k, asc, fl = {"div": ("dy", False, lambda r: (val(D, r, "dy") or 0) < 40), "cre": ("cresc5a", False, lambda r: (val(D, r, "lpa") or 0) > 0), "qual": ("roe", False, lambda r: (val(D, r, "roe") or 0) > 0),
                      "divida": ("dlebit", True, None), "maiores": ("valmerc", False, None)}.get(o, ("dy", False, None))
        if k not in D["F"]: return "O site não tem esse indicador agora."
        L = _top(D, rows, k, 10, asc, fl)
        return (f"{'Menores' if asc else 'Maiores'} {label(D, k)}{tit}:\n" + _linhas(D, L, k) + "\n(1 ticker por empresa, liquidez ≥ R$ 500 mil/dia. Não é recomendação.)") if L else "Nenhuma empresa atende agora."
    if f == "carteira":
        C = [t for t in (a.get("cart") or []) if t in D["by"]]
        if not C: return "Sua Carteira está vazia (aba Carteira → registre suas compras)."
        if a.get("o") == "prov":
            out = []
            for t in C:
                m = D["M"].get(t) or {}
                out.append(f"• {t}: " + ("; ".join(f"{e[0]} R$ {br(e[1], 4)}" for e in (m.get("ytd") or [])[:6]) or "nenhum provento no ano"))
            return "Proventos por ação no ano (veja o total recebido na aba Carteira):\n" + "\n".join(out)
        return "Suas ações hoje:\n" + "\n".join(f"• {t}: {_sgn(D['by'][t]['var']) if D['by'][t].get('var') is not None else 'sem variação'}" for t in C)
    if f == "modelos_emp" or f == "modelos_rank":
        v = _pre_todas((fx.get("pre") or (lambda: None))())
        if not v: return "O resultado dos modelos ainda não foi calculado (rotina diária). Veja na aba Comparar → Modelos."
        nm = lambda m: (modelos.MOD.get(m) or {}).get("n", m)
        mes = lambda x: f"{x[5:7]}/{x[:4]}" if x and len(x) >= 7 else x  # AAAA-MM → MM/AAAA
        v = dict(v, ini=mes(v.get("ini")), fim=mes(v.get("fim")))
        ms = [m for m in v["m"] if not (modelos.MOD.get(m) or {}).get("ref")]
        if f == "modelos_rank" and esc == "geral":
            L = sorted((x for x in v.get("cart") or [] if x["m"] in ms), key=lambda x: -(x.get("pct") or -1e9))
            return f"Modelos numa carteira com todas as empresas, de {v['ini']} a {v['fim']} (valores padrão do Comparar):\n" + "\n".join(f"{i + 1}. {nm(x['m'])}: {_sgn(x['pct'])}" for i, x in enumerate(L)) + "\nNão é recomendação."
        alvo2 = T if f == "modelos_emp" else alvo
        ix = [v["t"].index(t) for t in alvo2 if t in v["t"]]
        if not ix: return "Essa empresa não está nos modelos pré-calculados (Comparar → Modelos com as empresas escolhidas calcula na hora)."
        res = []
        for j, m in enumerate(v["m"]):
            if m not in ms: continue
            xs = [v["p"][j][i] for i in ix if v["p"][j][i] is not None]
            if xs: res.append((m, sum(xs) / len(xs)))
        res.sort(key=lambda z: -z[1])
        quem = ", ".join(v["t"][i] for i in ix)
        return f"Rendimento de cada modelo em {quem} de {v['ini']} a {v['fim']}" + (" (média)" if len(ix) > 1 else "") + ":\n" + "\n".join(f"{i + 1}. {nm(m)}: {_sgn(x)}" for i, (m, x) in enumerate(res)) + "\nNão é recomendação."
    if f == "guia":
        sec = a.get("sec") or a.get("secao"); t = guide_sections().get(sec or "")
        return f"{sec}:\n{t}" if t else "Escolha a parte do site."
    return "Escolha uma opção."


# ---- escrita livre: a frase vira um caminho do menu (sem IA): radical das palavras, acentos/erros de digitação e nota por palavras em comum
_SUF = ("amentos", "imentos", "amento", "imento", "adoras", "adores", "idades", "idade", "mente", "acoes", "acao", "icoes", "icao", "eiras", "eiros",
        "eira", "eiro", "istas", "ista", "ivas", "ivos", "iva", "ivo", "oes", "aes", "ais", "eis", "em", "am", "es", "as", "os", "s", "a", "o", "e")


def stem(w):
    """Radical simples em português: “dividendos”, “dividendo” e “dividendeira” ficam parecidos."""
    if len(w) <= 3: return w
    for x in _SUF:
        if w.endswith(x) and len(w) - len(x) >= 3: return w[:-len(x)]
    return w


_IXI = {"k": None}
def _int_index(D):
    """Índice das intenções: rótulo + frases de exemplo de cada nó + palavras lidas do site (indicadores, setores, seções do ⓘ, assuntos)."""
    if _IXI["k"] is D: return _IXI
    docs = {}
    for nid, n in INT["nos"].items():
        txt = " ".join([n.get("l", "")] + n.get("ex", []))
        docs[nid] = txt
    docs["e_ind"] += " " + " ".join(f["label"] for f in D["F"].values())
    docs["setor"] += " " + " ".join(w for w, _ in SECT_WORDS)
    for k, nid in (("div", "n_div"), ("res", "n_res"), ("eco", "n_eco"), ("neg", "n_neg")):
        docs[nid] += " " + " ".join(VOC["noticias"].get("assuntos", {}).get(k, []))
    toks = {nid: [stem(w) for w in re.findall(r"[a-z0-9/]+", norm(t)) if w not in STOP] for nid, t in docs.items()}
    N = len(toks); df = {}
    for ts in toks.values():
        for w in set(ts): df[w] = df.get(w, 0) + 1
    import math
    _IXI.update(k=D, toks={k: set(v) for k, v in toks.items()}, idf={w: math.log(1 + N / c) for w, c in df.items()}, vocab=set(df))
    return _IXI


def intencao(q, D):
    """Frase -> [(nó, nota)] dos caminhos mais parecidos (nota 0–1: parte das palavras da frase que o nó explica, pesada pela raridade)."""
    X = _int_index(D)
    emp = lambda w: w in D["alias"] or w in D["tok"] or w.upper() in D["by"] or w.upper() in D["roots"]  # nome de empresa: é o “quem”, não o “quê”
    ws = [w for w in re.findall(r"[a-z0-9/]+", norm(q)) if w not in STOP and not emp(w)]
    ss = []
    for w in ws:
        s = stem(w)
        if s not in X["vocab"] and len(s) >= 4:
            c = [x for x in difflib.get_close_matches(s, X["vocab"], 3, 0.8) if x[0] == s[0] and abs(len(x) - len(s)) <= 2]  # erro de digitação
            s = c[0] if c else s  # (mesma 1ª letra: “lance” não vira “balanço”)
        ss.append(s)
    if not ss: return []
    tot = sum(X["idf"].get(s, 1.0) for s in ss) or 1
    # nota = parte da frase que o caminho explica (0–1) + um pouco de quão específico ele é (desempate: caminho com menos palavras soltas)
    sc = [(nid, sum(X["idf"].get(s, 1.0) for s in set(ss) if s in X["toks"][nid]) / tot) for nid in X["toks"]]
    sc = [(nid, x + .05 * x / (1 + len(X["toks"][nid]) / 20)) for nid, x in sc]
    return sorted([x for x in sc if x[1] > 0], key=lambda z: -z[1])


def intencao_resposta(q, D, P, ret_fn=None, quote_fn=None, fx=None, cx=None):
    """Escrita livre pelo menu: nota alta e tudo o que o caminho pede achado na frase -> responde; senão None. -> (texto, nó) ou None."""
    pai = {c: k for k, x in INT["nos"].items() for c in x.get("op") or []}
    def pede(nid):  # o que o caminho pede, com o que os nós de cima pedem
        out = []
        while nid: out = list(INT["nos"][nid].get("pede") or []) + out; nid = pai.get(nid)
        return out
    def da(nid):  # dá para responder com o que a frase tem?
        for pd in pede(nid):
            if pd == "empresa" and not P["tickers"] or pd == "empresa2" and len(P["tickers"]) < 2: return False
            if pd == "ind" and not [k for k in P["metrics"] if k in D["F"]] or pd == "setor" and not P["sector"] or pd == "secao": return False
        return True
    usa = lambda nid: any(x in ("empresa", "empresa2", "escopo") for x in pede(nid)) or (INT["nos"][nid].get("a") or {}).get("de") == "empresa"
    L = []
    for nid, sc in intencao(q, D):  # caminho com resposta (f); nó de menu vale pelo 1º filho com resposta
        n = INT["nos"][nid]
        if not n.get("f"): nid = next((c for c in n.get("op") or [] if INT["nos"][c].get("f")), None)
        if nid and INT["nos"][nid].get("f") not in ("livre", "sim") and da(nid) and nid not in [x[0] for x in L]: L.append((nid, sc))
    if P["tickers"] and L:  # citou empresa: só caminhos que usam a empresa (os só da empresa antes dos com “De quem?”); nenhum -> regras/IA
        L = [x for x in L if usa(x[0])]; so = [x for x in L if "empresa" in pede(x[0]) or (INT["nos"][x[0]].get("a") or {}).get("de") == "empresa"]
        if so: L = so
    if not L or L[0][1] < .5 or (len(L) > 1 and L[1][1] > L[0][1] - .1 and INT["nos"][L[1][0]].get("f") != INT["nos"][L[0][0]].get("f")): return None
    nid = L[0][0]; n = INT["nos"][nid]; f = n.get("f")
    a = dict(n.get("a") or {}); cx = cx or {}
    a["fav"] = cx.get("fav") or []; a["cart"] = cx.get("cart") or []
    for pd in pede(nid):
        if pd == "empresa":
            if not P["tickers"]: return None
            a["e"] = P["tickers"][:1]
        elif pd == "empresa2":
            if len(P["tickers"]) < 2: return None
            a["e"], a["e2"] = P["tickers"][:1], P["tickers"][1:2]
        elif pd == "ind":
            if not [k for k in P["metrics"] if k in D["F"]]: return None
            a["k"] = [k for k in P["metrics"] if k in D["F"]][0]
        elif pd == "setor":
            if not P["sector"]: return None
            a["setor"] = P["sector"]
        elif pd == "periodo": a["per"] = (P["period"] or (None, None, "1 ano"))[2].replace("em ", "")
        elif pd == "escopo": a["esc"] = "empresa" if P["tickers"] else "fav" if re.search(r"\bfavorit", P["nq"]) else "geral"; a["e"] = P["tickers"][:1]
        elif pd == "escopo2": a["esc2"] = "setor" if P["sector"] else "fav" if re.search(r"\bfavorit", P["nq"]) else "geral"; a["setor"] = P["sector"]
        elif pd == "secao": return None
    if f in ("resumo", "ind", "div", "ret", "cmp", "cmpidx", "modelos_emp") and not P["tickers"]: return None
    a.setdefault("e", P["tickers"][:1])
    return guiada(f, a, D, ret_fn, quote_fn, fx), nid


LOC_OK = {"e_resumo", "e_ind", "e_ret", "e_cmp_emp", "e_cmp_ibov", "e_cmp_cdb", "q_div", "q_cre", "q_qual", "q_divida", "s_maiores", "s_div", "m_macro", "site"}  # caminhos que as regras (local) já respondem


def sugestoes_menu(q, D, n=3):
    """“Você quis dizer:” os n caminhos do menu mais parecidos com a frase (botões que abrem o menu nesse ponto)."""
    out, seen = [], set()
    for nid, sc in intencao(q, D):
        lab = INT["nos"][nid].get("l")
        if nid in seen or not lab or nid == "outro": continue
        pai = next((k for k, x in INT["nos"].items() if nid in (x.get("op") or [])), None)
        out.append({"l": (INT["nos"][pai]["l"] + " → " if pai else "") + lab, "nav": nid}); seen.add(nid)
        if len(out) >= n: break
    return out + [{"l": "Abrir o menu", "nav": "inicio"}]


# ============================================================ IA (Gemini)
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


def _models():
    return [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-3.5-flash", "gemini-3.1-flash-lite"] if m]


def _sys(extra=""):
    return ("Você é o assistente do site " + site_name() + ". Responda em português do Brasil, de forma concisa, com números no formato brasileiro. "
            "Sobre botões/abas/opções do site, cite SOMENTE nomes que existem no GUIA DO SITE ou nesta lista de botões/opções reais: "
            + ", ".join(ui_labels()) + ". Nunca invente. Se o usuário citar um botão/opção que não existe, diga que essa opção não existe, peça que ele "
            "olhe de novo e descreva exatamente o que vê ou conte passo a passo como chegou ali, e sugira a opção real mais próxima, se houver. "
            "Você pode filtrar, ranquear e cruzar critérios na tabela de dados e deve explicar os critérios usados. Diga quais ações atendem "
            "aos critérios, sem recomendação personalizada de investimento. " + POP + extra)


# Base de contexto (conhecimento.json, fonte única): pessoas, futebol, filmes, animes, jogos, empresas e temas -> só os itens citados na pergunta
_KB = None


def kb():
    global _KB
    if _KB is None:
        try: _KB = json.load(open(os.path.join(BASE, "conhecimento.json"), encoding="utf-8"))
        except Exception as e: log.warning("conhecimento.json: %s", e); _KB = {}
    return _KB


_WIKI = {"t": 0.0, "d": None}


def _load_wiki():
    try:
        import snapshots
        p, _ = snapshots.load("kb", max_mem_age=43200)
        _WIKI["d"] = (p or {}).get("itens") or _WIKI["d"] or {}
    except Exception as e:
        log.info("kb: %s", e); _WIKI["d"] = _WIKI["d"] or {}


def wiki():
    """Resumos da Wikipedia dos itens do conhecimento.json (snapshot kb, scripts/build_kb.py) -> {"categoria|nome": {t, x, u}}.
    Baixa em segundo plano (a cada 12 h) para não atrasar a resposta; sem o snapshot, o chat segue só com o conhecimento.json."""
    if time.time() - _WIKI["t"] > 43200:
        _WIKI["t"] = time.time()
        import threading
        threading.Thread(target=_load_wiki, daemon=True).start()
    return _WIKI["d"] or {}


def _sentences(x, n=2, skip=0):
    s = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú0-9])", x or "")
    return " ".join(s[skip:skip + n]).strip()


# categorias da base (conhecimento.json) -> rótulo; também usadas por scripts/build_kb.py
KB_CATS = [("pessoas", "pessoa"), ("filmes", "filme"), ("series", "série"), ("animes", "anime"), ("jogos", "jogo"),
           ("estudios", "empresa/estúdio"), ("temas", "tema"), ("jogadores", "futebol")]
_NM = {"key": None}


def _nk(s):
    """Nome normalizado para casar com a pergunta: só letras e números separados por espaço."""
    return " ".join(re.findall(r"[a-z0-9]+", norm(s)))


def _ph(w):
    """Chave fonética para nomes estrangeiros: l = r (japonês), letras repetidas = uma (kulilin/krillin -> kuririn)."""
    return re.sub(r"(.)\1+", r"\1", w.replace("l", "r").replace("y", "i").replace("k", "c"))


def _kb_items():
    """-> {chave "categoria|nome": (categoria, item)} de toda a base."""
    K = kb(); out = {}
    for cat, _ in KB_CATS:
        lst = (K.get("futebol") or {}).get("jogadores", []) if cat == "jogadores" else K.get(cat, [])
        for it in lst: out[f"{cat}|{norm(it['n'])}"] = (cat, it)
    return out


def _names():
    """Índice nome -> [(chave, tipo, nome exibido, descrição)]: títulos e apelidos (conhecimento.json + Wikidata), personagens e elenco
    (snapshot kb). Recalculado só quando a base muda."""
    W = wiki(); key = (id(kb()), id(W), len(W))
    if _NM["key"] == key: return _NM
    skip = set(VOC.get("nomes_ignorados", [])) | STOP | COMMON_WORDS | METRIC_WORDS
    idx, items = {}, _kb_items()

    def add(name, k, kind, label, d=""):
        n = _nk(name)
        if len(n) < 3 or n in skip or (kind != "item" and (len(n) < 4 or n.isdigit())): return
        lst = idx.setdefault(n, [])
        if not any(x[0] == k and x[1] == kind for x in lst): lst.append((k, kind, label, d))
    for k, (cat, it) in items.items():
        w = W.get(k) or {}
        for n in [it["n"]] + it.get("a", []) + w.get("al", []): add(n, k, "item", it["n"])
        for p in w.get("p", []):
            for n in [p["n"]] + p.get("a", []):
                add(n, k, "personagem", p["n"], p.get("d", ""))
                parts = _nk(n).split()  # "Monkey D. Luffy" -> também "luffy"
                if len(parts) > 1 and len(parts[-1]) >= 5: add(parts[-1], k, "personagem", p["n"], p.get("d", ""))
        for p in w.get("c", []): add(p["n"], k, "elenco", p["n"], p.get("d", ""))
    ph = {}
    for n in idx:
        if " " not in n and len(n) >= 5: ph.setdefault(_ph(n), []).append(n)
    _NM.update(key=key, idx=idx, ph=ph, items=items)
    return _NM


def _find(q, fuzzy=True):
    """Nomes da base citados na pergunta (o trecho mais longo primeiro) -> [(trecho, entradas)]; sem nenhum, tenta grafia parecida."""
    N = _names(); w = _nk(q).split(); used, out = set(), []
    for size in (5, 4, 3, 2, 1):
        for i in range(len(w) - size + 1):
            if any(j in used for j in range(i, i + size)): continue
            n = " ".join(w[i:i + size])
            if n in N["idx"]: out.append((n, N["idx"][n])); used.update(range(i, i + size))
    if out or not fuzzy: return out
    keys = list(N["ph"])
    for x in w:
        if len(x) < 5 or x in STOP or x in COMMON_WORDS or x in METRIC_WORDS: continue
        m = difflib.get_close_matches(_ph(x), keys, 1, 0.85)
        if m: out += [(n, N["idx"][n]) for n in N["ph"][m[0]]]
    return out


def kb_resolve(q, force=None, fuzzy=True):
    """-> {"keys": itens da base ligados à pergunta, "who": [(tipo, nome, descrição, [chaves])], "amb": (nome, [chaves]) se o nome
    existe em obras diferentes e a pergunta não diz qual}. force = chave escolhida pela pessoa ("Está falando de qual?")."""
    keys, who, amb = [], [], None
    hits = _find(q, fuzzy)
    direct = {k for _, es in hits for k, kind, *_ in es if kind == "item"}
    for n, es in hits:
        for lvl in ("item", "personagem", "elenco"):
            sel = [e for e in es if e[1] == lvl and (not force or e[0] == force)]
            if sel: break
        if not sel: continue
        ks = list(dict.fromkeys(e[0] for e in sel))
        if lvl == "personagem" and len(ks) > 1 and not (direct & set(ks)) and not force:
            amb = amb or (sel[0][2], ks); continue
        if lvl == "personagem" and direct & set(ks): ks = [k for k in ks if k in direct]
        if lvl != "item": who.append((lvl, sel[0][2], next((e[3] for e in sel if e[3]), ""), ks))
        keys += ks
    if force and force not in keys: keys.insert(0, force)
    return {"keys": list(dict.fromkeys(keys)), "who": who, "amb": amb}


def kb_ambiguous(q, force=None):
    """Nome em mais de uma obra -> resposta perguntando qual (botões com cada obra); senão None."""
    R = kb_resolve(q, force)
    if not R["amb"]: return None
    name, ks = R["amb"]; items = _names()["items"]
    return {"a": f"“{name}” aparece em mais de uma obra. Está falando de qual?", "mode": "regras", "tok": 0,
            "sug": [{"l": items[k][1]["n"], "q": q, "topic": "kb:" + k} for k in ks[:8]], "sugl": "Escolha:"}


def _kb_hits(q, tickers=(), force=None, fuzzy=True):
    """Itens da base ligados à pergunta -> [{rot, n, d, e, w, k, who}] (w = resumo da Wikipedia; who = personagem/ator citado)."""
    K, nq, W = kb(), norm(q), wiki()
    if not K: return []
    R = kb_resolve(q, force, fuzzy); items = _names()["items"]; rot = dict(KB_CATS)
    out, emp = [], [t[:4] if t[:4].isalpha() else t for t in tickers]
    for k in R["keys"]:
        if k not in items: continue
        cat, it = items[k]
        out.append({"rot": rot[cat], "n": it["n"], "d": it["d"], "e": it.get("e", []), "w": (W.get(k) or {}).get("x", ""), "k": k,
                    "who": [w for w in R["who"] if k in w[3]]})
        emp += [x.split(":")[0] for x in it.get("e", [])]
    F = K.get("futebol") or {}
    if re.search(r"\b(copa|copas|campeao|campeoes|campea|selecao|mundial)\b", nq):
        out += [{"rot": "futebol", "n": "", "d": F.get(k, ""), "e": [], "w": "", "k": "", "who": []} for k in ("campeoes", "copas")]
    E = K.get("empresas", {})
    for t in dict.fromkeys(emp):
        k = next((x for x in (t, t[:4], re.sub(r"\d+$", "", t)) if x in E), None)
        if k: out.append({"rot": "empresa", "n": t, "d": E[k], "e": [], "w": (W.get(f"empresas|{k}") or {}).get("x", ""), "k": "", "who": []})
    return out


def _who_txt(w, H):
    """'Kuririn: personagem de Dragon Ball (…)' / 'Tom Holland: ator (…); atuou em A, B'."""
    kind, name, d, ks = w; items = _names()["items"]
    obras = ", ".join(items[k][1]["n"] for k in ks if k in items)
    if kind == "personagem": return f"{name}: personagem de {obras}" + (f" ({d})" if d else "")
    return f"{name}" + (f": {d}" if d else "") + f"; atuou em {obras}"


def kb_context(q, tickers=(), cap=6000, force=None, fuzzy=True):
    """Itens da base ligados à pergunta (nomes, apelidos, personagens, elenco) + o que fazem as empresas ligadas a eles e às ações citadas."""
    H = _kb_hits(q, tickers, force, fuzzy)
    if not H: return ""
    lines = []
    for h in H:
        lines += [f"- [{'personagem' if w[0] == 'personagem' else 'elenco'}] " + _who_txt(w, H) for w in h["who"]]
        lines.append(f"- [{h['rot']}] " + (f"{h['n']}: " if h["n"] else "") + h["d"] + (f" (empresas: {', '.join(h['e'])})" if h["e"] else "")
                     + (f" | Wikipedia: {_sentences(h['w'], 3)}" if h["w"] else ""))
    return ("CONTEXTO (base do site, dados até " + str(kb().get("atualizado", "")) + "; confira na web o que pode ter mudado):\n"
            + "\n".join(dict.fromkeys(lines)))[:cap]


def _kb_text(h, hist):
    """Descrição do item sem repetir o que a conversa já mostrou: base do site -> 1º trecho da Wikipedia -> trecho seguinte."""
    used = " ".join(str(x.get("t", "")) for x in (hist or []) if x.get("r") != "u")
    opts = [h["d"]] + [s for s in (_sentences(h["w"], 2), _sentences(h["w"], 2, 2)) if s]
    for o in opts:
        if o[:60] not in used: return o + (" (Wikipédia)" if o != h["d"] else "")
    return random.choice(opts)


def kb_answer(q, ext_fn=None, hist=None, force=None):
    """Sem a IA (fora do ar ou sem chave): responde com a base — quem é/o que é, depois a empresa ligada com os dados do site,
    depois o aviso de sites especializados."""
    H = [h for h in _kb_hits(q, (), force) if h["rot"] != "empresa"]
    if not H: return None
    lines = []
    for h in H[:3]:
        lines += ["• " + _who_txt(w, H) + "." for w in h["who"]]
        lines.append("• " + (f"{h['n']}: " if h["n"] else "") + _kb_text(h, hist))
    e = next((h["e"][0] for h in H if h["e"]), None)
    return link_ext({"a": "\n".join(dict.fromkeys(lines)) + "\n[[FORA]]" + ("\n[[EMPRESA:" + e + "]]" if e else "")}, q, ext_fn, hist)["a"]


# busca por relevância (BM25) no painel ⓘ e na base, para perguntas que nenhuma regra entendeu
_IX = {"key": None}


def _toks(s):
    return [w for w in re.findall(r"[a-z0-9]{3,}", norm(s)) if w not in STOP]


def _index():
    W = wiki(); key = (len(guide()), len(W))
    if _IX["key"] != key:
        docs = [("guia", t, b) for t, b in guide_sections().items() if b and t != "Glossário"]
        docs += [("glos", l.split(":")[0].strip("- "), l.strip("- ")) for l in guide_sections().get("Glossário", "").split("\n") if ":" in l]
        for k, (cat, it) in _kb_items().items():
            docs.append(("kb", it["n"], it["d"] + " " + (W.get(k) or {}).get("x", "")))
        T = [_toks(d[1] + " " + d[1] + " " + d[2]) for d in docs]  # título conta em dobro
        df = {}
        for t in T:
            for w in set(t): df[w] = df.get(w, 0) + 1
        _IX.update(key=key, docs=docs, T=T, df=df, avg=sum(map(len, T)) / max(1, len(T)))
    return _IX


def search(q, k1=1.5, b=0.75):
    """-> (origem, título, texto) do trecho mais relevante, ou None se nada casa o bastante."""
    I = _index(); qs = list(dict.fromkeys(_toks(q)))
    if not qs or not I["docs"]: return None
    N, best = len(I["docs"]), (0.0, None, 0)
    for i, t in enumerate(I["T"]):
        tf = {}
        for w in t: tf[w] = tf.get(w, 0) + 1
        s, hit = 0.0, 0
        for w in qs:
            if w in tf:
                idf = math.log(1 + (N - I["df"][w] + 0.5) / (I["df"][w] + 0.5)); hit += 1
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(t) / I["avg"]))
        if s > best[0]: best = (s, i, hit)
    s, i, hit = best
    if i is None or s < 4 or hit < 2: return None  # pouca semelhança: melhor dizer que não entendeu
    return I["docs"][i]


# assuntos fora do mercado: a IA só aponta a empresa ligada (marcador); preço e dados vêm do site (link_ext)
POP = ("O site é para investimentos. Se a pergunta for sobre algo fora do mercado (pessoa, esporte, política, celebridade, filme, série, música, "
       "jogo, marca, produto, evento ou atualidade), diga em uma ou duas frases quem é ou o que é (use o CONTEXTO, se houver), indique procurar "
       "sites especializados no assunto (esporte, política, notícias ou entretenimento) e, se houver informação que afete alguma empresa da bolsa, "
       "inclua. Se houver empresa de capital aberto ligada (dona, fabricante, distribuidora, patrocinadora), diga qual e em que bolsa, sem escrever "
       "preço, e termine com uma linha só com [[EMPRESA:TICKER:PAIS]] (PAIS = br, us, gb, de, pt ou jp; ex.: [[EMPRESA:TTWO:us]]). "
       "Se você não souber do que se trata, peça para a pessoa escolher o tema e termine com uma linha só com [[ASSUNTO]]. ")
TOPICS = ["Cinema", "Música", "Esporte", "Jogos", "Política", "Atualidades", "Outros"]
_MK = re.compile(r"\[\[EMPRESA:([A-Za-z0-9.\-]+):([a-z]{2})\]\]")


_FORA = re.compile(r"[^.!?\n]*sites? especializad[^.!?\n]*[.!?]?")


def link_ext(out, q, ext_fn, hist=None):
    """Troca os marcadores da IA: empresa ligada -> dados do site (qualquer país); assunto incerto -> botões de tema.
    Ordem da resposta fora do mercado: quem é/o que é -> empresa ligada (bolsa e índice do país) -> sites especializados -> pergunta final."""
    a = out["a"]; m = _MK.search(a); ask = "[[ASSUNTO]]" in a; fora = "[[FORA]]" in a
    a = _MK.sub("", a).replace("[[ASSUNTO]]", "").replace("[[FORA]]", "")
    s = _FORA.search(a)
    if s: fora = s.group(0).strip(); a = a.replace(s.group(0), "")
    elif fora: fora = frase("fora_do_site", hist)
    a = re.sub(r"\n{3,}", "\n\n", a).strip()
    r = ext_fn(m.group(1).upper(), m.group(2)) if m and ext_fn else None
    if r:
        cur, big = r.get("cur") or "", lambda x: f"{br(x / 1e9, 1)} bi" if abs(x) >= 1e9 else f"{br(x / 1e6, 1)} mi"
        var = r.get("var")
        onde = " · ".join(x for x in (r["pais"], r.get("bolsa"), f"índice {r['indice']}" if r.get("indice") else "") if x)
        a += (f"\n\n**{r.get('nome') or r['ticker']} ({r['ticker']})** — {onde}: preço {br(r.get('preco'))} {cur}"
              + (f" ({'+' if var >= 0 else ''}{br(var)}% hoje)" if var is not None else "")
              + (f" · valor de mercado {big(r['valmerc'])} {cur}" if r.get("valmerc") else "")
              + (f" · P/L {br(r['pl'])}" if r.get("pl") else ""))
    if fora: a += "\n\n" + fora
    if r: a += "\n\nDeseja mais alguma informação sobre ela?"
    out = dict(out, a=a)
    if ask: out["sug"], out["sugl"] = [{"l": t, "q": q, "topic": t} for t in TOPICS], "Está falando sobre:"  # refaz a mesma pergunta com o tema
    return out


def _post(model, body, deadline, cap=15):
    left = deadline - time.time()
    if left < 4: raise TimeoutError("sem tempo")
    if time.time() < _DOWN.get(model, 0): raise _Pula(model + " fora do ar")  # tenta o próximo modelo
    try:
        r = requests.post(API.format(model), headers={"x-goog-api-key": os.environ.get("GEMINI_API_KEY", ""), "Content-Type": "application/json"},
                          json=body, timeout=min(cap, left))
    except requests.RequestException as e:
        AI_ST.update(t=time.time(), ok=False, m=model, e=type(e).__name__); raise
    if r.status_code in (429, 503): _DOWN[model] = time.time() + 120
    AI_ST.update(t=time.time(), ok=r.status_code == 200, m=model, e="" if r.status_code == 200 else _ai_err(r))
    return r


class _Pula(requests.RequestException):
    """Modelo pulado por estar fora do ar há pouco (503/429): quem chama passa ao próximo modelo."""


AI_ST = {}  # última chamada à IA (Gemini): quando, deu certo, modelo, motivo do erro — mostrado no chat e no ⓘ (ai_status)
_AI_CHK = {"t": 0.0, "d": None}


def _ai_err(r):
    """Motivo curto de uma resposta de erro do Gemini (sem a chave)."""
    try: m = str(((r.json() or {}).get("error") or {}).get("message") or "")
    except Exception: m = ""
    c = r.status_code
    why = ("chave inválida" if c == 400 and "key" in m.lower() else "chave sem permissão ou bloqueada" if c in (401, 403)
           else "modelo não existe" if c == 404 else "limite de uso esgotado (cota)" if c == 429 else "serviço do Google fora do ar" if c in (500, 503) else "erro")
    return f"{why} (http {c})" + (f": {m[:120]}" if m else "")


def ai_status():
    """A IA está funcionando? Chave configurada + última chamada; sem chamada nos últimos 30 min, confere os modelos no Google (cache de 10 min).
    -> {chave, ok, t, m, e}"""
    if not os.environ.get("GEMINI_API_KEY"): return {"chave": False, "ok": False, "e": "chave da IA não configurada no servidor"}
    if AI_ST.get("t") and time.time() - AI_ST["t"] < 1800: return dict(AI_ST, chave=True)
    if time.time() - _AI_CHK["t"] > 600:
        _AI_CHK["t"] = time.time(); d = None
        for model in _models():  # leitura do cadastro do modelo: não gasta cota de respostas
            try:
                r = requests.get(API.format(model).rsplit(":", 1)[0], headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=8)
                d = {"t": time.time(), "ok": r.status_code == 200, "m": model, "e": "" if r.status_code == 200 else _ai_err(r)}
            except requests.RequestException as e:
                d = {"t": time.time(), "ok": False, "m": model, "e": type(e).__name__}
            if d["ok"]: break
        _AI_CHK["d"] = d
    return dict(_AI_CHK["d"] or AI_ST or {"ok": False, "e": "sem conferência"}, chave=True)


def _contents(q, hist, n=4):
    c = [{"role": "user" if h.get("r") == "u" else "model", "parts": [{"text": str(h.get("t", ""))[:1500]}]} for h in (hist or [])[-n:]]
    c.append({"role": "user", "parts": [{"text": q[:1000]}]})
    return c


def _text(j):
    c = j["candidates"][0]
    return "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", []) if not p.get("thought")).strip(), c


INTERP = """Converta a pergunta do usuário (sobre ações da bolsa brasileira) em JSON, sem comentários. Hoje é {hoje}.
Campos:
"tipo": "valor" (indicador de ações citadas), "ranking" (listar/filtrar/ordenar ações), "retorno" (variação de preço/rentabilidade de ações ou índices no período),
        "definicao" (o que significa um termo), "como_usar" (como usar o site), "analise" (opinião, explicação, por que, cenário, recomendação) ou "outro";
"acoes": tickers ou nomes de empresas citados (ex.: ["PETR4","Itaú"]); se a pergunta continua a conversa, use a empresa da conversa;
"indices": entre {idx};
"indicadores": chaves entre {keys};
"setor": entre {sect} ou null;
"filtros": lista de {{"ind": chave, "op": ">=", "<=", ">" ou "<", "valor": número}} (percentuais como número: 8% = 8; R$ em reais);
"ordem": "desc", "asc" ou null; "n": quantidade pedida ou null;
"inicio" e "fim": datas AAAA-MM-DD do período pedido, ou null.
Use "ret" como indicador para variação de preço/rentabilidade. Responda só o JSON."""


def interpret(q, hist, D, deadline):
    """IA só para entender a pergunta (JSON). -> dict parse-compatível ou None."""
    if not os.environ.get("GEMINI_API_KEY"): return None
    keys = ", ".join(f"{k} ({label(D, k)})" for k in list(D["F"]) + ["ret1", "ret5", "prov12", RET] if k in D["F"] or k in MX or k == RET)
    sys_t = INTERP.format(hoje=date.today().isoformat(), idx=", ".join(f"{k} ({v})" for k, v in IDXN.items()), keys=keys,
                          sect=", ".join(SECTORS))
    body = {"systemInstruction": {"parts": [{"text": sys_t}]}, "contents": _contents(q, hist, 4),
            "generationConfig": {"temperature": 0, "maxOutputTokens": 500, "responseMimeType": "application/json", "thinkingConfig": {"thinkingBudget": 0}}}
    for model in list(reversed(_models()[-2:])) + ([os.environ["GEMINI_MODEL"]] if os.environ.get("GEMINI_MODEL") else []):  # o leve primeiro
        try:
            r = _post(model, body, deadline, cap=12)
            if r.status_code != 200: continue
            t, _ = _text(r.json())
            t = re.sub(r"^```(?:json)?|```$", "", t.strip()).strip()
            return json.loads(t)
        except Exception as e:
            log.info("interpret %s: %s", model, str(e)[:80])
    return None


def from_interp(J, q, D, base):
    """JSON da IA -> estrutura P (mesma do parse), resolvendo nomes de empresas com o próprio dicionário do site."""
    P = dict(base)
    T = []
    for a in J.get("acoes") or []:
        a = str(a)
        if a.upper() in D["by"]: T.append(a.upper()); continue
        sub = parse(a, D)
        T += sub["tickers"]
    P["tickers"] = list(dict.fromkeys(T))
    P["idx"] = [x for x in (J.get("indices") or []) if x in IDXN]
    ks = []
    for k in J.get("indicadores") or []:
        k = str(k)
        if k in ("ret", "ret1", "ret2", "ret3", "ret5") and J.get("tipo") == "retorno": k = RET
        if k in D["F"] or k in MX or k == RET: ks.append(k)
    P["metrics"] = list(dict.fromkeys(ks))
    P["sector"] = J.get("setor") if J.get("setor") in SECTORS else None
    P["filters"] = [(f["ind"], f["op"], float(f["valor"])) for f in (J.get("filtros") or [])
                    if isinstance(f, dict) and (f.get("ind") in D["F"] or f.get("ind") in MX)
                    and f.get("op") in (">=", "<=", ">", "<") and isinstance(f.get("valor"), (int, float))]
    P["order"] = J.get("ordem") if J.get("ordem") in ("asc", "desc") else P.get("order")
    P["n"] = J.get("n") if isinstance(J.get("n"), int) and 0 < J["n"] <= 50 else P.get("n")
    di, df = J.get("inicio"), J.get("fim")
    try:
        if di:
            date.fromisoformat(di); df = df or date.today().isoformat(); date.fromisoformat(df)
            kind = "dia" if (date.fromisoformat(df) - date.fromisoformat(di)).days <= 1 else "periodo"
            P["period"] = (di, df, f"de {dbr(di)} a {dbr(df)}" if kind == "periodo" else "no dia", kind)
    except ValueError:
        pass
    if J.get("tipo") == "ranking" and not P["metrics"] and P["sector"]: P["metrics"] = ["valmerc"]
    P["tipo"] = J.get("tipo")
    return P


def rel_context(q, D, ret_fn, cx, P):
    """Só o contexto necessário à pergunta."""
    nq = P["nq"]; T = P["tickers"]; I = P["idx"]; parts = []
    screen = not (T or I) or P["sector"] or P["filters"]
    if screen:
        parts.append("TABELA DE TODAS AS AÇÕES (CSV; vazio = sem dado):\n" + table(D, cx))
    else:
        tb = table(D, cx).split("\n"); parts.append("AÇÕES CITADAS (CSV):\n" + "\n".join([tb[0]] + [l for l in tb[1:] if l.split(",")[0] in T]))
        for t in T[:4]: parts.append("DETALHE " + card(D, t))
    if cx.get("groups") and (screen or "grupo" in nq): parts.append("GRUPOS PRONTOS DO SITE (top 10):\n" + str(cx["groups"])[:8000])
    if T or I or "indice" in nq or "ibov" in nq:
        p = P["period"] or ((date.today() - timedelta(days=365)).isoformat(), date.today().isoformat(), "em 12 meses", "periodo")
        R = ret_fn(p[0], p[1], T)
        parts.append(f"Variação de preço no período pedido ({p[0]} a {p[1]}): " + "; ".join(f"{IDXN.get(x, x)} {br(R.get(x))}%" for x in T + list(IDXN) if x in R))
    for kk, lab, ws in (("prev", "PREVISÃO RENTABILIDADE (entradas, JSON)", ("previs", "simula", "aporte", "minha", "meu")),
                        ("prevRes", "PREVISÃO RENTABILIDADE (resultado na tela)", ("previs", "simula", "aporte", "minha", "meu")),
                        ("alug", "PREVISÃO ALUGUEL (entradas, JSON)", ("aluguel", "alugar", "btc")),
                        ("alugRes", "PREVISÃO ALUGUEL (resultado na tela)", ("aluguel", "alugar", "btc")),
                        ("comp", "COMPARAR (seleção, JSON)", ("compar", "rendeu mais", "rendeu menos")),
                        ("compRes", "COMPARAR (resultado na tela)", ("compar", "rendeu mais", "rendeu menos"))):
        if cx.get(kk) and any(w in nq for w in ws): parts.append(lab + ":\n" + str(cx[kk])[:5000])
    if any(w in nq for w in ("como", "aba", "funciona", "significa", "regra", "cor", "calcul", "fonte", "previs", "aluguel", "compar", "grupo", "etiqueta", "consenso", "app", "aplicativo", "instal", "celular")):
        parts.append("GUIA DO SITE (painel ⓘ):\n" + guide())
    return "\n\n".join(parts)


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


def gemini2(q, ctx, hist, deadline, topic=None):
    if not os.environ.get("GEMINI_API_KEY"): raise RuntimeError("sem chave")
    tp = (f"A pessoa indicou que a pergunta é sobre o tema {topic}: interprete-a nesse contexto e responda à pergunta em si "
          "(não explique o tema). Não peça para escolher o tema de novo. ") if topic else ""
    sys_t = _sys(tp + "Use SOMENTE os dados abaixo. Se um dado não estiver aqui, diga que o site não tem.\n\nDADOS DO SITE:\n" + ctx)
    err = None
    for model, th in [(m, True) for m in _models()] + [("gemini-flash-latest", False)]:
        body = {"systemInstruction": {"parts": [{"text": sys_t}]}, "contents": _contents(q, hist),
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3000, **({"thinkingConfig": {"thinkingBudget": 0}} if th else {})}}
        try:
            r = _post(model, body, deadline)
        except TimeoutError:
            break
        except requests.RequestException as e:
            err = type(e).__name__; continue
        if r.status_code != 200: err = f"http {r.status_code}"; continue
        j = r.json(); t, _ = _text(j)
        if t: return t, (j.get("usageMetadata") or {}).get("promptTokenCount")
        err = "vazio"
    raise RuntimeError(f"gemini {err}")


TRUST = ("Ao pesquisar na web, prefira fontes confiáveis: B3 (b3.com.br), CVM (gov.br/cvm, rad.cvm.gov.br), sites de RI das empresas, "
         "Status Invest, Fundamentus. Diga claramente o que veio da web e o que veio do site.")


def ground(q, ctx, hist, deadline):
    """Gemini com busca Google. -> (texto com fontes, tokens) ou erro. Uma tentativa por modelo, dentro do prazo."""
    if not os.environ.get("GEMINI_API_KEY"): raise RuntimeError("sem chave")
    sys_t = _sys("Use os DADOS DO SITE e, quando faltarem ou parecerem errados, a busca na web. " + TRUST + "\n\nDADOS DO SITE:\n" + ctx[:60000])
    err = None
    for model in _models():
        body = {"systemInstruction": {"parts": [{"text": sys_t}]}, "contents": _contents(q, hist), "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3000, "thinkingConfig": {"thinkingBudget": 0}}}
        try:
            r = _post(model, body, deadline)
        except TimeoutError:
            break
        except requests.RequestException as e:
            err = type(e).__name__; continue
        if r.status_code != 200: err = r.status_code; continue
        j = r.json(); t, c = _text(j)
        src = [(x.get("web") or {}) for x in (c.get("groundingMetadata") or {}).get("groundingChunks", [])]
        src = [w for w in src if w.get("uri")][:6]
        if src: t += "\n\nFontes da web:\n" + "\n".join(f"• {w.get('title') or 'fonte'}: {w['uri']}" for w in src)
        if t: return t, (j.get("usageMetadata") or {}).get("promptTokenCount")
    raise RuntimeError(f"busca {err}")


# ============================================================ orquestração
_QA = {}  # mesma pergunta no mesmo dia (sem histórico)
QA_MAX = 500


def answer2(q, hist, D, ret_fn, cx=None, ext_fn=None, quote_fn=None, topic=None, fx=None):
    t0 = time.time(); deadline = t0 + DEADLINE_S
    cx = cx or {}
    P = parse(q, D, hist)
    nq = P["nq"]
    rel = "|".join(str(cx.get(k, ""))[:3000] for k in ("prev", "alug", "comp") if any(w in nq for w in ("previs", "aluguel", "compar", "minha", "meu")))
    kbk = topic[3:] if (topic or "").startswith("kb:") and topic[3:] in _names()["items"] else None  # obra escolhida em "Está falando de qual?"
    topic = _names()["items"][kbk][1]["n"] if kbk else topic if topic in TOPICS else None  # tema escolhido em "Está falando sobre:": a mesma pergunta vai à IA com o contexto
    key = date.today().isoformat() + "|" + hashlib.sha1((nq + "|" + rel + "|" + (topic or "")).encode()).hexdigest()
    if key in _QA and not hist:
        out = dict(_QA[key], cached=True); _log(q, out, P, t0); return out
    has_ai = bool(os.environ.get("GEMINI_API_KEY"))
    loc = None
    try: loc = None if topic else local(q, D, ret_fn, cx, P, quote_fn)
    except Exception as e: log.info("local: %s", e)
    out = None
    plain = not (P["tickers"] or P["metrics"] or P["sector"] or P["idx"])  # sem ação/indicador: pode ser assunto fora do mercado
    gi = None
    if not topic and not P["complaint"]:  # escrita livre pelo menu guiado (intencoes.json), sem IA
        try: gi = intencao_resposta(q, D, P, ret_fn, quote_fn, fx, cx)
        except Exception as e: log.info("intencao: %s", e)
        if gi and loc and (gi[1] in LOC_OK or P["define"] or P["howto"] or P["colors"]): gi = None  # as regras já respondem bem esses caminhos
    if gi: loc = None
    if loc:
        out = {"a": loc, "mode": "regras", "tok": 0}
    elif gi:
        out = {"a": gi[0], "mode": "guia", "tok": 0, "nav": gi[1]}
    elif plain and not kbk and kb_ambiguous(q):  # nome em mais de uma obra: pergunta qual antes de responder
        out = kb_ambiguous(q)
    elif not has_ai:
        out = {"a": kb_answer(q, ext_fn, hist, kbk) or rules(q, D, ret_fn, P), "mode": "regras", "tok": 0}
    else:
        # (1) IA interpreta, o Python calcula — só para perguntas objetivas
        if not P["complex"] and not P["complaint"] and not topic:
            J = interpret(q, hist, D, deadline)
            if J and J.get("tipo") in ("valor", "ranking", "retorno"):
                P2 = from_interp(J, q, D, P)
                try: a = execute(P2, D, ret_fn)
                except Exception as e: log.info("execute interp: %s", e); a = None
                if a: out = {"a": a, "mode": "ia+dados", "tok": 0}
                P = P2 if (P2["tickers"] or P2["idx"]) else P
            elif J and J.get("tipo") in ("definicao", "como_usar"):
                a = define(P) or howto(P)
                if a: out = {"a": a, "mode": "regras", "tok": 0}
        if out is None:
            ctx = rel_context(q, D, ret_fn, cx, P)
            k = kb_context(q, P["tickers"], force=kbk, fuzzy=plain)
            if k: ctx = k + "\n\n" + ctx
            red_asked = any(((D["by"].get(t) or {}).get("st") or {}).get(k) == "red" for t in P["tickers"] for k in P["metrics"])
            want = P["complaint"] or red_asked
            if not want:
                try:
                    a, tok = gemini2(q, ctx, hist, deadline, topic)
                    out = {"a": a, "mode": "gemini", "tok": tok}
                    if any(w in norm(a) for w in MISSING) and deadline - time.time() > 20: want = True
                except Exception as e:
                    log.info("chat fallback: %s", str(e)[:80])
            if want:  # (a) usuário diz que está errado, (b) indicador perguntado sem maioria, (c) IA diz que falta o dado
                try:
                    a, tok = ground(q, ctx, hist, deadline); out = {"a": a, "mode": "gemini+web", "tok": tok}
                except Exception as e:
                    log.info("busca web indisponível (cota do Gemini?): %s", str(e)[:60])
                    if out is None:
                        try: a, tok = gemini2(q, ctx, hist, deadline); out = {"a": a, "mode": "gemini", "tok": tok}
                        except Exception: kb_a = kb_answer(q, ext_fn, hist, kbk); out = {"a": kb_a or rules(q, D, ret_fn, P), "mode": "regras", "tok": 0}
            if out is None:
                kb_a = kb_answer(q, ext_fn, hist, kbk)
                out = {"a": kb_a, "mode": "regras", "tok": 0} if kb_a else {"a": rules(q, D, ret_fn, P), "mode": "regras", "tok": 0}
    if out["mode"].startswith("gemini"):
        out = link_ext(out, q, ext_fn, hist)
        if not out.get("sug") and (P["tickers"] or P["metrics"] or P["sector"] or P["idx"]): out["sug"] = suggestions(P, D)[:3]
    if out["a"].startswith("Não consegui entender") or out["mode"] == "regras" and out["a"].startswith("Não encontrei"):
        sm = sugestoes_menu(q, D)  # “Você quis dizer:” os caminhos do menu guiado mais parecidos
        if sm and out["a"].startswith("Não consegui entender"): out["a"], out["sug"], out["sugl"] = "Não entendi direito. Você quis dizer:", sm, None
        else: out["sug"] = suggestions(P, D)
    elif out["mode"] in ("regras", "ia+dados") and (P["tickers"] or P["metrics"] or P["sector"]):
        out["sug"] = suggestions(P, D)[:3]
    if (out["mode"] in ("gemini", "ia+dados") or loc) and not hist:
        day = key[:10]
        for k in [k for k in _QA if not k.startswith(day)]: del _QA[k]  # só o dia de hoje
        while len(_QA) >= QA_MAX: del _QA[next(iter(_QA))]  # no máximo QA_MAX (sai a mais antiga)
        _QA[key] = out
    _log(q, out, P, t0)
    return out


def _log(q, out, P, t0):
    """Registro de perguntas (para ver o que os usuários perguntam e o que ficou sem resposta)."""
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 3_000_000:
            os.replace(LOG_FILE, LOG_FILE + ".1")
        a = out.get("a") or ""
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "q": q[:500], "mode": out.get("mode"),
               "cached": bool(out.get("cached")), "ms": int((time.time() - t0) * 1000),
               "sem_resposta": a.startswith(("Não consegui entender", "Não encontrei a opção", "Não entendi direito")) or any(w in norm(a) for w in MISSING),
               "reclamacao": bool(P.get("complaint")), "entendeu": {"tickers": P.get("tickers"), "idx": P.get("idx"), "ind": P.get("metrics"),
               "setor": P.get("sector"), "filtros": P.get("filters"), "periodo": (P.get("period") or [None, None, None])[:3], "sobrou": P.get("left")},
               "a": a[:400]}
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        sync_log()
    except Exception as e:
        log.info("chat log: %s", e)


# Registro preservado: o disco do Render zera a cada publicação. Com GITHUB_TOKEN (variável do Render), as perguntas novas vão
# para data/chat_log.jsonl na branch `data` (no máximo a cada 6 h) e read_log junta o que já estava lá.
_SYNC = {"t": 0.0, "remote": None, "rt": 0.0}


def sync_log(force=False):
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok or not os.path.exists(LOG_FILE) or (not force and time.time() - _SYNC["t"] < 6 * 3600): return
    _SYNC["t"] = time.time()

    def run():
        import snapshots
        old, sha = snapshots.gh_get("data/chat_log.jsonl")
        old = old or ""; seen = set(old.splitlines())  # sem o arquivo (ou sem resposta): sem sha, o GitHub só aceita se ele não existir
        new = [l for l in open(LOG_FILE, encoding="utf-8").read().splitlines() if l and l not in seen]
        if not new: return
        lines = (old.splitlines() + new)[-20000:]
        snapshots.gh_put("data/chat_log.jsonl", "\n".join(lines) + "\n", sha, "Registro do chat")
    import threading
    threading.Thread(target=run, daemon=True).start()


def _remote_log():
    if time.time() - _SYNC["rt"] > 3600:
        _SYNC["rt"] = time.time()
        try:
            import snapshots
            r = requests.get(snapshots.RAW + "/chat_log.jsonl", timeout=20)
            _SYNC["remote"] = r.text.splitlines() if r.status_code == 200 else []
        except Exception: _SYNC["remote"] = _SYNC["remote"] or []
    return _SYNC["remote"] or []


def read_log(n=200, only=None):
    lines = list(_remote_log())
    for fn in (LOG_FILE + ".1", LOG_FILE):
        if os.path.exists(fn):
            with open(fn, encoding="utf-8") as fh: lines += fh.read().splitlines()
    out = []
    for l in dict.fromkeys(lines):  # sem repetir o que já foi salvo no GitHub
        try: out.append(json.loads(l))
        except ValueError: pass
    if only == "sem_resposta": out = [r for r in out if r.get("sem_resposta")]
    elif only == "reclamacao": out = [r for r in out if r.get("reclamacao")]
    return out[-n:][::-1]
