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
    models = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-flash-latest", "gemini-3.5-flash", "gemini-flash-lite-latest"] if m]
    sys_t = ("Você é o assistente do site Screener B3. Responda em português do Brasil, de forma concisa, usando SOMENTE os dados abaixo "
             "(dados do site: tabela de todas as ações, grupos, índices e o que o usuário preencheu em Previsão e Comparar). "
             "Você pode filtrar, ranquear e cruzar critérios na tabela (ex.: P/L baixo + LPA positivo + crescimento) e deve explicar os critérios usados. "
             "Diga quais ações atendem aos critérios, sem recomendação personalizada de investimento. Se um dado não estiver aqui, diga que o site não tem. "
             "Números no formato brasileiro.\n\nDADOS DO SITE:\n" + ctx)
    contents = [{"role": "user" if h.get("r") == "u" else "model", "parts": [{"text": str(h.get("t", ""))[:1500]}]} for h in (hist or [])[-6:]]
    contents.append({"role": "user", "parts": [{"text": q[:1000]}]})
    err = None
    for model in models:  # modelo indisponível/sobrecarregado: tenta o próximo
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                              json={"systemInstruction": {"parts": [{"text": sys_t}]}, "contents": contents,
                                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}}, timeout=45)
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
