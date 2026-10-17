#!/usr/bin/env python3
"""JG Investing — backend FastAPI.
Fonte primária: Fundamentus (resultado.php). Complemento: Status Invest (ao vivo; fallback snapshot diário do GitHub Actions).
Nomes/setores (opcional): brapi.dev /api/quote/list (público, sem token).
"""
import io, json, os, threading, time, logging, math, gzip, hashlib, re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests

import statusinvest
import tiebreak
import tradingview
import fundamentus
import valor_justo
import snapshots
from snapshots import br_num
import consensus
import history
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
import universe  # regra do universo exibido (scripts/universe.py)
from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE, "cache", "data.json")
os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
REFRESH_SECONDS = 30 * 60
TZ = ZoneInfo("America/Sao_Paulo")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
log = logging.getLogger("screener")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Definição dos indicadores
# key, rótulo, unidade, direção (high/low/None), exclui negativos no filtro "≤",
# coluna Fundamentus, coluna Status Invest, Fundamentus "0 = sem dado", limiar absoluto p/ divergência, comparar?
# ---------------------------------------------------------------------------
FIELDS = [
    # key        label                 unit  dir    exclNeg fund_col            si_col                    zero_na absThr cmp
    ("preco",    "Cotação",            "R$", None,  False, "Cotação",          "PRECO",                  True,  0.05, True),
    ("dy",       "Div. Yield",         "%",  "high",False, "Div.Yield",        "DY",                     False, 1.0,  True),
    ("pl",       "P/L",                "x",  "low", True,  "P/L",              "P/L",                    True,  1.0,  True),
    ("pvp",      "P/VP",               "x",  "low", True,  "P/VP",             "P/VP",                   True,  0.2,  True),
    ("psr",      "PSR",                "x",  "low", True,  "PSR",              "PSR",                    True,  0.2,  True),
    ("evebitda", "EV/EBITDA",          "x",  "low", True,  "EV/EBITDA",        None,                     True,  1.0,  True),
    ("evebit",   "EV/EBIT",            "x",  "low", True,  "EV/EBIT",          "EV/EBIT",                True,  1.0,  True),
    ("pebit",    "P/EBIT",             "x",  "low", True,  "P/EBIT",           "P/EBIT",                 True,  1.0,  True),
    ("pativo",   "P/Ativo",            "x",  "low", True,  "P/Ativo",          "P/ATIVOS",               True,  0.2,  True),
    ("roe",      "ROE",                "%",  "high",False, "ROE",              "ROE",                    True,  2.0,  True),
    ("roic",     "ROIC",               "%",  "high",False, "ROIC",             "ROIC",                   True,  2.0,  True),
    ("roa",      "ROA",                "%",  "high",False, None,               "ROA",                    False, 2.0,  True),
    ("mbruta",   "Marg. Bruta",        "%",  "high",False, "Mrg Bruta",        "MARGEM BRUTA",           True,  2.0,  True),
    ("mebit",    "Marg. EBIT",         "%",  "high",False, "Mrg Ebit",         "MARGEM EBIT",            True,  2.0,  True),
    ("mliq",     "Marg. Líquida",      "%",  "high",False, "Mrg. Líq.",        "MARG. LIQUIDA",          True,  2.0,  True),
    ("liqcorr",  "Liq. Corrente",      "x",  "high",False, "Liq. Corr.",       "LIQ. CORRENTE",          True,  0.2,  True),
    ("dlpl",     "Dív.Líq/Patrim.",    "x",  "low", False, "Dív.Líq/ Patrim.", "DIV. LIQ. / PATRI.",     True,  0.2,  True),
    ("dlebit",   "Dív.Líq/EBIT",       "x",  "low", False, None,               "DIVIDA LIQUIDA / EBIT",  False, 0.5,  True),
    # volume financeiro médio por dia (moeda do país). Brasil em "Todos": B3 (COTAHIST, snapshot metrics); fonte escolhida: o valor dela
    ("voldia",   "Volume dia",         "$",  "high",False, None,               None,                     False, 0,    False),
    ("vol10",    "Volume 10 pregões",  "$",  "high",False, None,               None,                     False, 0,    False),
    ("vol30",    "Volume 1 mês",       "$",  "high",False, None,               None,                     False, 0,    False),
    ("liq2m",    "Volume 2 meses",     "$",  "high",False, "Liq.2meses",       " LIQUIDEZ MEDIA DIARIA", False, 0,    False),
    ("vol90",    "Volume 3 meses",     "$",  "high",False, None,               None,                     False, 0,    False),
    ("vol6m",    "Volume 6 meses",     "$",  "high",False, None,               None,                     False, 0,    False),
    ("vol9m",    "Volume 9 meses",     "$",  "high",False, None,               None,                     False, 0,    False),
    ("vol12m",   "Volume 12 meses",    "$",  "high",False, None,               None,                     False, 0,    False),
    # crescimento médio por ano (CAGR): 5 anos por consenso das fontes; 1 a 4 anos só a CVM tem
    ("cresc1a",  "Cresc. Receita 1a",  "%",  "high",False, None,               None,                     False, 3.0,  False),
    ("cresc2a",  "Cresc. Receita 2a",  "%",  "high",False, None,               None,                     False, 3.0,  False),
    ("cresc3a",  "Cresc. Receita 3a",  "%",  "high",False, None,               None,                     False, 3.0,  False),
    ("cresc4a",  "Cresc. Receita 4a",  "%",  "high",False, None,               None,                     False, 3.0,  False),
    ("cresc5a",  "Cresc. Receita 5a",  "%",  "high",False, "Cresc. Rec.5a",    "CAGR RECEITAS 5 ANOS",   False, 3.0,  True),
    ("lucro1a",  "Cresc. Lucro 1a",    "%",  "high",False, None,               None,                     False, 3.0,  False),
    ("lucro2a",  "Cresc. Lucro 2a",    "%",  "high",False, None,               None,                     False, 3.0,  False),
    ("lucro3a",  "Cresc. Lucro 3a",    "%",  "high",False, None,               None,                     False, 3.0,  False),
    ("lucro4a",  "Cresc. Lucro 4a",    "%",  "high",False, None,               None,                     False, 3.0,  False),
    ("lucro5a",  "Cresc. Lucro 5a",    "%",  "high",False, None,               "CAGR LUCROS 5 ANOS",     False, 3.0,  True),
    ("vpa",      "VPA",                "R$", "high",False, "__VPA",            " VPA",                   False, 0.10, True),
    ("lpa",      "LPA",                "R$", "high",False, "__LPA",            " LPA",                   False, 0.10, True),
    ("peg",      "PEG",                "x",  "low", True,  None,               " PEG Ratio",             False, 0.3,  True),
    ("patrliq",  "Patrimônio Líq.",    "R$", None,  False, "Patrim. Líq",      None,                     True,  0,    False),
    ("valmerc",  "Valor de Mercado",   "R$", None,  False, None,               " VALOR DE MERCADO",      False, 0,    False),
]
FIELD_KEYS = [f[0] for f in FIELDS]
# Campos agrupados nos filtros (um campo com Período): grp = grupo, per = período, sub = subtipo; scale = digitado em milhões.
VOL_PER = {"voldia": "dia", "vol10": "10 pregões", "vol30": "1 mês", "liq2m": "2 meses", "vol90": "3 meses",
           "vol6m": "6 meses", "vol9m": "9 meses", "vol12m": "12 meses"}
GROWTH_KEYS = [f"{k}{n}a" for k in ("cresc", "lucro") for n in range(1, 6)]
# Ordenar: posição de cada indicador (os demais ficam só em Mais filtros)
SORT_POS = {k: i for i, k in enumerate(("dy", "pl", "pvp", "roe", "valmerc", "dlebit", "mliq", "evebit", "roic", "peg"), 1)}
FIELD_EXTRA = {**{k: {"grp": "vol", "per": p, "scale": 1e6} for k, p in VOL_PER.items()},
               **{k: {"grp": "cres", "sub": "Receita" if k.startswith("cresc") else "Lucro",
                      "per": f"{k[5]} ano" + ("s" if k[5] != "1" else "")} for k in GROWTH_KEYS},
               **{k: {"sort": i} for k, i in SORT_POS.items()}}
# Termo do Glossário (painel ⓘ) de cada indicador cujo rótulo é diferente do título no Glossário (botão ⓘ dos cards e filtros)
GLOSS_TERM = {"dy": "DY", "mbruta": "Margem bruta", "mebit": "Margem EBIT", "mliq": "Margem líquida", "liqcorr": "Liquidez corrente",
              "dlpl": "Dív.Líq/PL", "patrliq": "Patrimônio líquido", "valmerc": "Valor de mercado",
              **{k: "Volume (média diária)" for k in VOL_PER}, **{k: "CAGR" for k in GROWTH_KEYS}}
for _k, _g in GLOSS_TERM.items(): FIELD_EXTRA.setdefault(_k, {})["gl"] = _g
REL_THR = 0.30  # 30%

def divergente(a, b, abs_thr):
    """Divergência grosseira: (sinais opostos e ambos |v| ≥ limiar) OU
    (diferença relativa > 30% E diferença absoluta > limiar do indicador)."""
    if a is None or b is None:
        return False
    d = abs(a - b)
    if d <= abs_thr:
        return False
    if (a > 0 > b) or (a < 0 < b):
        return True
    m = max(abs(a), abs(b))
    return m > 0 and d / m > REL_THR

# ---------------------------------------------------------------------------
def http_get(url, params=None, tries=4, timeout=(10, 45)):
    wait = 2
    last = None
    for i in range(1, tries + 1):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = type(e).__name__
        log.warning("GET %s falhou (%s), tentativa %d/%d", url, last, i, tries)
        if i < tries:
            time.sleep(wait); wait = min(wait * 2, 20)
    raise RuntimeError(f"{url}: {last}")

def num(x):
    if x is None: return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def fetch_fundamentus():
    """-> (dados, descrição). Ao vivo; se falhar, a cópia diária da branch data (snapshot `fundamentus`)."""
    try:
        return fundamentus.parse(http_get(fundamentus.URL).content), "ao vivo"
    except Exception as e:
        p, desc = snapshots.load("fundamentus")
        if not (p and p.get("rows")): raise RuntimeError(f"Fundamentus ao vivo: {e}; cópia: {desc}")
        log.warning("Fundamentus ao vivo falhou (%s); usando %s", e, desc)
        return p["rows"], desc

SI_FALLBACK_URL = os.environ.get("SI_FALLBACK_URL", f"{snapshots.RAW}/statusinvest.csv")
SI_LOCAL_FILE = os.path.join(BASE, "data", "statusinvest.csv")

def fetch_statusinvest():
    """Ordem: ao vivo (export CSV -> JSON paginado, com headers de navegador e cookies)
    -> snapshot do GitHub Actions (raw.githubusercontent, branch data) -> arquivo local data/.
    Retorna (dados, descrição da fonte usada)."""
    errs = []
    try:
        text, method = statusinvest.fetch_live()
        return statusinvest.parse_csv(text, br_num), f"ao vivo ({method})"
    except Exception as e:
        errs.append(f"ao vivo: {e}")
        log.warning("Status Invest ao vivo falhou: %s", e)
    try:
        r = http_get(SI_FALLBACK_URL, tries=2, timeout=(10, 30))
        data = statusinvest.parse_csv(r.content.decode("utf-8", errors="replace"), br_num)
        when = "?"
        try:
            m = http_get(SI_FALLBACK_URL.replace("statusinvest.csv", "statusinvest.meta.json"), tries=1).json()
            when = snapshots.when_sp(m.get("fetched_at"))
        except Exception:
            pass
        return data, f"snapshot GitHub de {when} (ao vivo bloqueado: {errs[0][9:][:80]})"
    except Exception as e:
        errs.append(f"snapshot GitHub: {e}")
    if os.path.exists(SI_LOCAL_FILE):
        with open(SI_LOCAL_FILE, encoding="utf-8") as fh:
            data = statusinvest.parse_csv(fh.read(), br_num)
        when = "?"
        try:
            with open(SI_LOCAL_FILE.replace(".csv", ".meta.json"), encoding="utf-8") as fh:
                when = snapshots.when_sp(json.load(fh).get("fetched_at"))
        except Exception:
            pass
        return data, f"arquivo local de {when}"
    raise RuntimeError(" | ".join(errs))

def fetch_brapi_names():
    out = {}
    for typ in ("stock",):
        r = http_get("https://brapi.dev/api/quote/list", params={"type": typ, "limit": 2000}, tries=2, timeout=(10, 30))
        for s in r.json().get("stocks", []):
            out[s["stock"].upper()] = {"nome": s.get("name"), "setor": s.get("sector"), "subsetor": s.get("subsector"),
                                       "var": s.get("change"), "preco_brapi": s.get("close")}
    return out

SOURCES = [  # id, nome, logo, países
    ("fund", "Fundamentus", "fundamentus.png", {"br"}),
    ("si", "Status Invest", "statusinvest.png", {"br"}),
    ("cvm", "CVM (oficial)", "cvm.png", {"br"}),
    ("i10", "Investidor10", "investidor10.png", {"br"}),
    ("tv", "TradingView", "tradingview.png", set(tradingview.COUNTRIES)),
    ("ddm", "Dados de Mercado", "dadosdemercado.png", {"br"}),
    ("yf", "Yahoo Finance", "yahoo.png", {"br"}),
]
SRC_NAME = {s[0]: s[1] for s in SOURCES}
CMP_FIELDS = [(f[0], f[8], f[9]) for f in FIELDS]

def _r4(x):
    x = num(x)
    return None if x is None else round(x, 4)

def load_tv(country):
    """TradingView ao vivo -> fallback snapshot. -> (dados, descrição)"""
    try:
        d = tradingview.fetch(country)
        return d, f"ao vivo ({len(d)} papéis)"
    except Exception as e:
        log.warning("TradingView %s ao vivo falhou: %s", country, e)
        snap, desc = snapshots.load(f"tradingview_{country}")
        if snap and snap.get("rows"):
            return snap["rows"], f"{desc} ({len(snap['rows'])} papéis; ao vivo falhou: {str(e)[:60]})"
        return {}, f"falhou: {str(e)[:80]}; {desc}"

def cvm_values(c, price, fund_pvp):
    """Indicadores da CVM para um ticker; múltiplos de preço com cotação × total de ações (como o Fundamentus)."""
    if not c: return {}, {}, None
    v = {k: c[k] for k in ("roe", "roa", "mbruta", "mebit", "mliq", "liqcorr", "dlpl", "dlebit", "roic", *GROWTH_KEYS, "lpa", "vpa") if k in c}
    a = {k: c[k] for k in ("mebit_adj", "roic_adj") if k in c}
    sh = c.get("_shares")
    # algumas empresas informam a quantidade de ações em milhares (sem coluna de escala): detecta pelo VPA implícito
    if sh and v.get("vpa") and price and fund_pvp:
        ratio = v["vpa"] / (price / fund_pvp)
        if 300 < ratio < 3000:
            sh *= 1000; v["vpa"] = round(v["vpa"] / 1000, 4)
            if "lpa" in v: v["lpa"] = round(v["lpa"] / 1000, 4)
    if sh and price:
        mc = price * sh
        q = lambda a_, b_: round(a_ / b_, 4) if a_ is not None and b_ else None
        nd = c.get("_netdebt")
        v.update({"pl": q(mc, c.get("_ni")), "pvp": q(mc, c.get("_eq")) if (c.get("_eq") or 0) > 0 else None,
                  "psr": q(mc, c.get("_rev")) if (c.get("_rev") or 0) > 0 else None,
                  "pativo": q(mc, c.get("_assets")),
                  "pebit": q(mc, c.get("_ebit")), "evebit": q(mc + nd, c.get("_ebit")) if nd is not None else None})
        a.update({"pebit_adj": q(mc, c.get("_ebit_adj")),
                  "evebit_adj": q(mc + nd, c.get("_ebit_adj")) if nd is not None else None})
    return {k: x for k, x in v.items() if x is not None}, {k: x for k, x in a.items() if x is not None}, sh

def lucro_pl(fd, n=3):
    """Barato/Caro (Brasil, DFP da CVM, snapshot fund): ln3 = lucro médio de n anos com teto (valor_justo.lucro_medio) ÷ patrimônio
    do último balanço (o site faz LPA = ln3 × VPA do card: sem depender da quantidade de ações da CVM) e roe3 = ROE médio (%)
    dos n anos (Gordon, bancos e seguradoras)."""
    fd = fd or {}
    m = valor_justo.lucro_medio(fd.get("ni"), n)
    eq = [x for x in (fd.get("eq") or [])[-n:]]
    if m is None or len(eq) != n or not eq[-1] or eq[-1] <= 0: return {}
    ni = (fd.get("ni") or [])[-n:]
    return {"ln3": round(m / eq[-1], 6), "roe3": round(sum(ni) / sum(eq) * 100, 2) if sum(eq) > 0 else None}

def build():
    t0 = time.time()
    status = {}
    fund, fsrc = fetch_fundamentus()  # obrigatório (ao vivo ou cópia diária)
    status["fundamentus"] = f"ok ({len(fund)} papéis) — {fsrc}"
    try:
        si, si_src = fetch_statusinvest(); status["statusinvest"] = f"ok ({len(si)} papéis) — {si_src}"
    except Exception as e:
        si = {}; status["statusinvest"] = f"falhou: {e}"; log.error("Status Invest: %s", e)
    try:
        names = fetch_brapi_names(); status["brapi_nomes"] = f"ok ({len(names)})"
    except Exception as e:
        names = {}; status["brapi_nomes"] = f"falhou: {e}"
    tv, status["tradingview"] = load_tv("br")
    snaps = {}
    snapshots.invalidate()
    for sid, name in (("i10", "investidor10"), ("ddm", "dadosdemercado"), ("cvm", "cvm")):
        p, desc = snapshots.load(name)
        snaps[sid] = (p or {}).get("rows") or {}
        status[name] = f"{desc} ({len(snaps[sid])} papéis)" if p else desc
    fda = ((snapshots.load("fund")[0]) or {}).get("a") or {}  # lucro e patrimônio anuais (scripts/build_fund.py) -> ln3
    pv_ = (snapshots.load("b3_proventos")[0]) or {}  # dividendo por ação por ano (B3) -> dpsm (Barsi)
    prov, pv_y1 = pv_.get("a") or {}, (pv_.get("anos") or [0, 0])[1]

    rows, n_red = [], 0
    for t, f in fund.items():
        s = si.get(t, {})
        price = f.get("Cotação")
        S = {"fund": {}, "si": {}}
        div = {}
        for key, label, unit, d, excl, fcol, scol, zero_na, absthr, cmp in FIELDS:
            fv = None
            if fcol == "__VPA":
                pvp = f.get("P/VP"); fv = round(price / pvp, 4) if price and pvp else None
            elif fcol == "__LPA":
                pl = f.get("P/L"); fv = round(price / pl, 4) if price and pl else None
            elif fcol:
                fv = f.get(fcol)
                if fv is not None and zero_na and fv == 0: fv = None
            sv = _r4(s.get(scol)) if scol else None
            if fv is not None: S["fund"][key] = _r4(fv)
            if sv is not None: S["si"][key] = sv
            if cmp and fv is not None and sv is not None and divergente(fv, sv, absthr):
                div[key] = [fv, sv]
        n_red += len(div)
        A = {}
        if t in tv: S["tv"] = {k: x for k, x in tv[t]["v"].items() if k != "peg"}  # PEG do TV é calculado por nós: não vota
        if t in snaps["i10"]: S["i10"] = snaps["i10"][t]
        dd = snaps["ddm"].get(t)
        if dd:
            S["ddm"] = {k: x for k, x in dd.items() if not k.endswith("_adj") and not k.startswith("_")}
            A["ddm"] = {k: x for k, x in dd.items() if k.endswith("_adj")}
        cv, ca, sh = cvm_values(snaps["cvm"].get(t), price, f.get("P/VP"))
        if cv: S["cvm"] = cv
        if ca: A["cvm"] = ca
        S = {k: x for k, x in S.items() if x}
        ex = {}  # Barato/Caro: dividendo médio por ação (B3) e dados dos alertas (CVM)
        dm = valor_justo.dps_medio(prov.get(t), pv_y1)
        if dm is not None: ex["dpsm"] = dm
        c_ = snaps["cvm"].get(t) or {}
        al = {k: c_[k] for k in ("dlebitda", "payout") if c_.get(k) is not None}
        if al: ex["al"] = al
        nm = names.get(t) or names.get(t[:4] + "3") or names.get(t[:4] + "4") or {}
        if not nm.get("nome") and (s.get("NOME") or s.get("SETOR")):
            nm = {"nome": s.get("NOME"), "setor": s.get("SETOR")}
        if not nm.get("nome") and t in tv:
            nm = {"nome": tv[t]["m"].get("nome"), "setor": tv[t]["m"].get("setor"), "subsetor": tv[t]["m"].get("subsetor")}
        var = names.get(t, {}).get("var")
        if var is None and t in tv: var = tv[t]["m"].get("var")
        rows.append({"ticker": t, "nome": nm.get("nome"), "setor": nm.get("setor"), "subsetor": nm.get("subsetor"),
                     "insi": bool(s), "var": var, "cur": "BRL", "S": S, "A": A, "div": div, **lucro_pl(fda.get(t)), **ex})
    rows.sort(key=lambda r: -((r["S"].get("tv") or {}).get("liq2m") or 0))
    now = datetime.now(timezone.utc)
    return {
        "country": "br", "currency": "BRL",
        "updated_at": now.isoformat(),
        "updated_at_sp": now.astimezone(TZ).strftime("%d/%m/%Y %H:%M:%S"),
        "took_s": round(time.time() - t0, 1),
        "status": status,
        "rule": {"rel": REL_THR, "abs": {f[0]: f[8] for f in FIELDS if f[9]}},
        "fields": [{"key": k, "label": l, "unit": u, "dir": d, "excludeNeg": e, "compared": c, **FIELD_EXTRA.get(k, {})}
                   for k, l, u, d, e, fc, sc, z, a, c in FIELDS],
        "counts": {"tickers": len(rows), "red_before": n_red},
        "rows": rows,
    }

def finalize(base, yf_store=None):
    """Aplica consenso; retorna payload para o cliente."""
    rows = []
    cnt = {"red": 0, "amb": 0, "adj": 0}
    src_count = {}
    FIN = consensus.financial_tickers(base["rows"])
    # Prioridade B3: papéis fora da lista oficial negociada (COTAHIST, 90 dias) saem; composição oficial dos índices
    isbr = base.get("country", "br") == "br"
    b3l, _ = snapshots.load("b3_listed", max_mem_age=6 * 3600) if isbr else (None, None)
    listed = set((b3l or {}).get("tickers") or [])
    if len(listed) < 200: listed = None
    b3i, _ = snapshots.load("b3_indices", max_mem_age=6 * 3600) if isbr else (None, None)
    IXC = {}
    for ix, comp in ((b3i or {}).get("indices") or {}).items():
        for cod, part in comp.items():
            IXC.setdefault(cod[:4], {}).setdefault(ix, (cod, part))
    CAD = (((snapshots.load("b3_cad", max_mem_age=12 * 3600)[0] or {}).get("c")) or {}) if isbr else {}
    V30 = (((snapshots.load("b3_vol30", max_mem_age=12 * 3600)[0] or {}).get("v")) or {}) if isbr else {}
    MXB = (((snapshots.load("metrics", max_mem_age=6 * 3600)[0] or {}).get("metrics")) or {}) if isbr else {}
    FGA = (snapshots.load("fg_acoes", max_mem_age=6 * 3600)[0] or {}) if isbr else {}  # Medo e Ganância de cada ação (build_fg.acoes)
    for r in base["rows"]:
        if listed is not None and r["ticker"] not in listed and r["ticker"][-1:].isdigit():
            continue
        S = dict(r.get("S") or {})
        if yf_store is not None:
            y = yf_store.get(r["ticker"])
            if y: S["yf"] = {k: x for k, x in y.items() if x is not None}
        nr = {k: r.get(k) for k in ("ticker", "nome", "setor", "subsetor", "var", "cur")}
        if not isbr and r.get("ipo"): nr["ipo"] = r["ipo"]  # data de listagem no exterior (TradingView); no Brasil vem da B3 (metrics.ftd)
        nr["S"] = S
        if r.get("A"): nr["A"] = r["A"]
        for k in ("ln3", "roe3", "dpsm", "al"):
            if r.get(k) is not None: nr[k] = r[k]
        fga = (FGA.get("a") or {}).get(r["ticker"])
        if fga: nr["fg"] = fga  # [hoje, 1 pregão antes, 5 antes, 21 antes]
        if r["ticker"] in FIN: nr["fin"] = True
        ixs = IXC.get(r["ticker"][:4])
        if ixs:  # índices da empresa (qualquer classe; mostra a classe quando diferente da exibida)
            nr["ix"] = {k: ([p, c] if c != r["ticker"] else [p]) for k, (c, p) in ixs.items()}
        consensus.apply_row(nr, CMP_FIELDS, divergente)
        if isbr:  # volume em "Todos": B3 (prioridade, todos os períodos); com uma fonte escolhida o site mostra o valor dela (S)
            mv = (MXB.get(r["ticker"]) or {}).get("vol") or {}
            nr["v"].update({k: mv.get(k) for k in VOL_PER})
            for k in VOL_PER: (nr.get("src") or {}).pop(k, None)
        if isbr:  # cadastro oficial da B3 completa nome/setor; sem nome ou sem nenhum fundamento, o papel sai
            cd = CAD.get(r["ticker"][:4])
            if cd and cd[1] in valor_justo.FAIR["barsi_seg"]: nr["seg"] = cd[1]  # Barato/Caro: Barsi pelo segmento oficial da B3
            if cd and not nr.get("nome"): nr["nome"] = cd[0]
            if cd and not nr.get("setor") and cd[1] and cd[1] != "Não Classificados": nr["setor"] = cd[1]
            vv = nr.get("v") or {}
            if not nr.get("nome") or all(vv.get(k) is None for k in ("pl", "pvp", "roe", "lpa", "vpa")):
                continue
        bkk = set(nr.get("bk") or [])
        cnt["two"] = cnt.get("two", 0) + sum(1 for k_, m in (nr.get("cm") or {}).items() if m.get("t") == "pri" and k_ not in bkk and k_ not in nr["st"])
        cnt["bank"] = cnt.get("bank", 0) + sum(1 for k_ in bkk if k_ not in nr["st"])
        for k_, x in nr["st"].items():
            if k_ in bkk: cnt["bank"] = cnt.get("bank", 0) + 1
            else: cnt[x] += 1
        for s in S: src_count[s] = src_count.get(s, 0) + 1
        rows.append(nr)
    if isbr:  # ilíquidas e 1 ticker por empresa: regra única em scripts/universe.py (B3, 30 pregões)
        universe.mark(rows, V30)
    d = {k: v for k, v in base.items() if k != "rows"}
    d["rows"] = rows
    if b3i: d["b3_ix_date"] = b3i.get("date")
    c = dict(base.get("counts") or {})
    c.update(cnt)
    c["adj"] = sum(1 for r in rows for m in (r.get("cm") or {}).values() if m.get("aj"))
    c["tickers"] = len(rows)
    c["liquidas"] = sum(1 for r in rows if (r["v"].get("liq2m") or 0) > 0)
    c["sources"] = src_count
    d["counts"] = c
    country = base.get("country", "br")
    d["sources"] = [{"id": i, "name": n, "logo": f"/static/logos/{l}", "count": src_count.get(i, 0)}
                    for i, n, l, cs in SOURCES if country in cs and src_count.get(i)]
    keys_with_data = {k for r in rows for k, x in r["v"].items() if x is not None}
    d["fields"] = [{**f, **FIELD_EXTRA.get(f["key"], {})} for f in base["fields"] if f["key"] in keys_with_data]
    d["fair"] = valor_justo.FAIR  # Barato/Caro: configuração (app.js → fairOf)
    fga = snapshots.load("fg_acoes", max_mem_age=6 * 3600)[0] if country == "br" else None
    if fga: d["fga"] = {"faixas": fga.get("faixas"), "d": fga.get("d")}  # faixas e data do índice de cada ação (card)
    return d

def build_foreign(country):
    tv, desc = load_tv(country)
    rows = []
    for t, x in tv.items():
        m = x["m"]
        rows.append({"ticker": t, "nome": m.get("nome"), "setor": m.get("setor"), "subsetor": m.get("subsetor"),
                     "var": m.get("var"), "cur": m.get("cur"), "ipo": m.get("ipo"), "S": {"tv": x["v"]}})
    rows.sort(key=lambda r: -(r["S"]["tv"].get("valmerc") or 0))
    now = datetime.now(timezone.utc)
    base = {"country": country, "currency": tradingview.COUNTRIES[country][2],
            "updated_at": now.isoformat(), "updated_at_sp": now.astimezone(TZ).strftime("%d/%m/%Y %H:%M:%S"),
            "status": {"tradingview": desc}, "rule": {"rel": REL_THR, "abs": {f[0]: f[8] for f in FIELDS if f[9]}},
            "fields": [{"key": k, "label": l, "unit": ("" if u == "R$" else u), "dir": d, "excludeNeg": e, "compared": c, **FIELD_EXTRA.get(k, {})}
                       for k, l, u, d, e, fc, sc, z, a, c in FIELDS],
            "counts": {"red_before": 0}, "rows": rows}
    d = finalize(base)
    for r in d["rows"]:  # fonte única: não precisa repetir os valores em S (guarda só o volume em ações)
        tvv = r.pop("S", {}).get("tv", {})
        q = {k: x for k, x in tvv.items() if k.startswith("q_")}
        if q: r["q"] = q
    d["single_source"] = "tv"
    return d

# ---------------------------------------------------------------------------
YF_FILE = os.path.join(BASE, "cache", "yfinance.json")
# Yahoo ao vivo: o Yahoo bloqueia IPs de nuvem (401 "Invalid Crumb" em cada ticker, enchendo o log).
# No Render (variável RENDER, definida pelo próprio Render) usa só o snapshot diário; YF_LIVE=1/0 força ligar/desligar.
YF_LIVE = os.environ.get("YF_LIVE", "0" if os.environ.get("RENDER") else "1") not in ("0", "false", "no", "")
ABS_THR = {f[0]: f[8] for f in FIELDS if f[9]}

class Cache:
    """base = dados brutos por fonte (Brasil); data = consenso aplicado (inclui Yahoo)."""
    def __init__(self):
        self.base = None
        self.data = None
        self.lock = threading.Lock()
        self.refreshing = False
        self.last_error = None
        self.yf = tiebreak.YFStore(YF_FILE)
        self.foreign = {}       # país -> payload
        self.foreign_lock = threading.Lock()
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, encoding="utf-8") as fh:
                    b = json.load(fh)
                if b.get("rows") and "S" in b["rows"][0]:
                    self.base = b
                    self.ensure_snapshot()
                    self.reapply()
                    log.info("cache de disco carregado (%s)", self.base.get("updated_at_sp"))
            except Exception as e:
                log.warning("cache de disco inválido: %s", e)

    def age(self):
        if not self.base: return 1e12
        return (datetime.now(timezone.utc) - datetime.fromisoformat(self.base["updated_at"])).total_seconds()

    def ensure_snapshot(self):
        """Carrega o snapshot do Yahoo JÁ (antes de tentar ao vivo) para tickers sem dado real."""
        try:
            need = tiebreak.tickers_needing(self.base["rows"])
            missing = [t for t in need if not self.yf.get(t)]
            if missing:
                snap = self.yf.load_snapshot()
                if snap:
                    self.yf.snapshot_msg = snap
                    if not self.yf.running:
                        self.yf.status = f"{snap} — ao vivo em segundo plano"
        except Exception as e:
            log.warning("snapshot yfinance: %s", e)

    def reapply(self):
        if not self.base: return
        try:
            d = finalize(self.base, self.yf)
        except Exception:
            log.exception("consenso falhou"); return
        d["status"] = dict(d.get("status") or {}); d["status"]["yfinance"] = self.yf.status
        self.data = d
        try:  # grupos prontos do rodízio: histórico sempre em memória (history.PIN)
            import modelos
            history.pin([], keep={t for g in modelos.ready_groups(universe.universe(d.get("rows") or [])) for t in g["t"]})
        except Exception as e:
            log.warning("grupos fixos do histórico: %s", e)

    def refresh(self):
        with self.lock:
            if self.refreshing: return False
            self.refreshing = True
        try:
            d = build()
            tmp = CACHE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False)
            os.replace(tmp, CACHE_FILE)
            self.base = d; self.last_error = None
            self.ensure_snapshot()
            self.reapply()
            log.info("atualizado: %s", {k: v for k, v in self.data["counts"].items() if k != "sources"})
            self.tiebreak_async()
            return True
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            log.exception("falha na atualização")
            return False
        finally:
            self.refreshing = False

    def refresh_async(self):
        if not self.refreshing:
            threading.Thread(target=self.refresh, daemon=True).start()

    def get_foreign(self, country):
        c = self.foreign.get(country)
        if c and time.time() - c[0] < REFRESH_SECONDS * 4:
            return c[1]
        with self.foreign_lock:
            c = self.foreign.get(country)
            if c and time.time() - c[0] < REFRESH_SECONDS * 4:
                return c[1]
            d = build_foreign(country)
            if d["rows"]:
                self.foreign[country] = (time.time(), d)
            return d

    def tiebreak_async(self):
        if self.yf.running or not self.base: return
        threading.Thread(target=self._tiebreak, daemon=True).start()

    def _tiebreak(self):
        self.yf.running = True
        try:
            need = tiebreak.tickers_needing(self.base["rows"])
            pend = len(self.yf.stale(need))
            snap = getattr(self.yf, "snapshot_msg", None)
            if not YF_LIVE:
                snap = self.yf.load_snapshot() or snap
                self.yf.status = (f"{snap} (ao vivo desligado neste servidor: o Yahoo bloqueia IPs de nuvem)" if snap
                                  else "sem snapshot (ao vivo desligado neste servidor)")
                self.yf.save()
                return
            if time.time() >= self.yf.blocked_until and pend:
                self.yf.status = (f"{snap} — " if snap else "") + f"tentando ao vivo em segundo plano ({pend} tickers)…"
                self.reapply()
            if time.time() < self.yf.blocked_until:
                ok, fail, blocked, msg = 0, 0, True, "ao vivo pausado após bloqueio recente"
            else:
                ok, fail, blocked, msg = tiebreak.run_fetch(self.yf, need, on_progress=self.reapply)
            if blocked:
                self.yf.blocked_until = max(self.yf.blocked_until, time.time() + 6 * 3600)
                snap = self.yf.load_snapshot() or snap
                self.yf.status = (f"ao vivo falhou: {msg} → {snap}" if snap else f"ao vivo falhou: {msg}; sem snapshot")
            else:
                live = sum(1 for t in need if (self.yf.data.get(t) or {}).get("src") == "live")
                self.yf.status = f"ao vivo ok — {live}/{len(need)} tickers (cache 24 h; {msg})"
            self.yf.save()
        except Exception as e:
            log.exception("thread yfinance")
            self.yf.status = f"erro: {type(e).__name__}: {e}"
        finally:
            self.yf.running = False
            self.reapply()

cache = Cache()

def scheduler():
    while True:
        if cache.age() >= REFRESH_SECONDS:
            cache.refresh()
        time.sleep(60)

app = FastAPI(title="JG Investing")

# Registro de erros: todo erro (500 e log ERROR) fica guardado com a causa; consulta em /api/errors (some ao reiniciar; o log do Render guarda mais)
import collections, traceback
ERRS = collections.deque(maxlen=300)

class _ErrLog(logging.Handler):
    def emit(self, rec):
        if rec.name.startswith(("yfinance", "urllib3")): return  # avisos esperados de fontes externas
        ERRS.append({"ts": datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S"), "onde": rec.name, "msg": rec.getMessage()[:500],
                     "causa": "".join(traceback.format_exception(*rec.exc_info))[-1500:] if rec.exc_info else ""})

logging.getLogger().addHandler(_ErrLog(level=logging.ERROR))

@app.exception_handler(Exception)
async def _erro(request: Request, exc: Exception):
    log.error("erro em %s %s", request.method, request.url.path, exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse({"error": "erro interno; tente de novo em instantes"}, status_code=500)

@app.get("/api/errors")
def api_errors(n: int = 50):
    return JSONResponse(list(ERRS)[-max(1, min(n, 300)):][::-1], headers={"Cache-Control": "no-store"})
app.add_middleware(GZipMiddleware, minimum_size=2000)
app.mount("/static/logos", StaticFiles(directory=os.path.join(BASE, "static", "logos")), name="logos")
app.mount("/static/flags", StaticFiles(directory=os.path.join(BASE, "static", "flags")), name="flags")
app.mount("/static/icons", StaticFiles(directory=os.path.join(BASE, "static", "icons")), name="icons")
app.mount("/static/brand", StaticFiles(directory=os.path.join(BASE, "static", "brand")), name="brand")

@app.on_event("startup")
def _start():
    threading.Thread(target=scheduler, daemon=True).start()
    if cache.base is not None:
        cache.tiebreak_async()

@app.get("/api/countries")
def api_countries():
    return [{"id": k, "name": v[1], "currency": v[2], "flag": f"/static/flags/{k}.png", "index": tradingview.YAHOO[k][2],
             "sources": [{"id": i, "name": n, "logo": f"/static/logos/{l}"} for i, n, l, cs in SOURCES if k in cs]}
            for k, v in tradingview.COUNTRIES.items()]

_JSON_CACHE = {}  # id(payload) -> (payload, json bytes, gzip bytes)

def _json_fast(request, d, extra=None):
    """Payload grande (~1,3 MB): converte para JSON e comprime UMA vez por versão dos dados (antes: a cada visita,
    ~2 s de CPU no plano gratuito). `extra` = campos pequenos que mudam (refreshing/last_error), emendados no início."""
    c = _JSON_CACHE.get(id(d))
    if not c or c[0] is not d:
        raw = json.dumps(d, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        c = (d, raw, None)
        if len(_JSON_CACHE) > 6: _JSON_CACHE.clear()  # só as versões atuais (pouca RAM no plano gratuito)
        _JSON_CACHE[id(d)] = c
    raw = c[1]
    if extra:
        head = json.dumps(extra, ensure_ascii=False, separators=(",", ":")).encode()[:-1]
        raw = head + (b"," + raw[1:] if len(raw) > 2 else b"}")
    gz = "gzip" in (request.headers.get("accept-encoding") or "")
    if gz:
        key = (id(d), raw[:200] if extra else b"")
        hit = _JSON_CACHE.get(("gz",) + key)
        if hit is None or hit[0] is not d:
            hit = (d, gzip.compress(raw, 6)); _JSON_CACHE[("gz",) + key] = hit
        return Response(hit[1], media_type="application/json", headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
    return Response(raw, media_type="application/json")

@app.get("/api/data")
def api_data(request: Request, country: str = "br"):
    country = (country or "br").lower()
    if country != "br" and country in tradingview.COUNTRIES:
        d = cache.get_foreign(country)
        if not d["rows"]:
            return JSONResponse({"loading": False, "error": d["status"].get("tradingview")}, status_code=502)
        return _json_fast(request, d)
    if cache.data is None:
        if not cache.refreshing:
            cache.refresh_async()
        return JSONResponse({"loading": True, "error": cache.last_error}, status_code=503)
    return _json_fast(request, cache.data, {"refreshing": cache.refreshing, "last_error": cache.last_error})

@app.post("/api/refresh")
def api_refresh():
    started = not cache.refreshing
    cache.refresh_async()
    cache.foreign.clear()
    return {"started": started, "refreshing": True}

@app.get("/api/status")
def api_status():
    d = cache.data or {}
    return {"refreshing": cache.refreshing, "updated_at": d.get("updated_at"),
            "updated_at_sp": d.get("updated_at_sp"), "counts": d.get("counts"),
            "status": d.get("status"), "last_error": cache.last_error,
            "foreign": {k: {"rows": len(v[1]["rows"]), "status": v[1]["status"]} for k, v in cache.foreign.items()}}

@app.get("/api/history/{ticker}")
def api_history(ticker: str, kind: str = "m"):
    try:
        return JSONResponse(history.get(ticker, kind), headers={"Cache-Control": "public, max-age=300"})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": "histórico indisponível: " + str(e)[:200]}, status_code=502)

@app.get("/api/chart/{ticker}")
def api_chart(ticker: str, kind: str = "d", country: str = "br"):
    try:
        if country not in tradingview.COUNTRIES or kind not in history.KINDS: raise ValueError("parâmetros inválidos")
        return JSONResponse(history.chart(ticker, kind, country), headers={"Cache-Control": "public, max-age=120"})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": "histórico indisponível: " + str(e)[:200]}, status_code=502)

@app.get("/api/profiles")
def api_profiles():
    import chat
    d, _ = snapshots.load("profiles", max_mem_age=6 * 3600)
    # + o que faz cada empresa (conhecimento.json, fonte única também do chat): ⓘ ao lado do nome no card
    return JSONResponse(dict(d or {}, empresas=chat.kb().get("empresas") or {}), headers={"Cache-Control": "public, max-age=3600"})

def _idx_returns(di, df):
    """Mesmo cálculo do gráfico (grafico.js pricePts/ratePts) para Ibovespa, dólar, CDB 100% CDI, IPCA, poupança e ouro."""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    st = _dt.strptime(di, "%Y-%m-%d").replace(tzinfo=_tz.utc).timestamp(); en = _dt.strptime(df, "%Y-%m-%d").replace(tzinfo=_tz.utc).timestamp() + 86399
    def price(ts, cs):
        b = e = None
        for t, c in zip(ts, cs):
            if c is None: continue
            if t <= st: b = c
            elif t <= en:
                if b is None: b = c
                e = c
        return None if b is None else ((e if e is not None else b) / b - 1) * 100
    def rate(d, v):
        cum = 1.0
        if len(d) < 1000:
            sm = di[:7] + "-01"
            for x, y in zip(d, v):
                if x < sm: continue
                n = _dt.strptime(x, "%Y-%m-%d"); nx = (n.replace(day=1) + _td(days=32)).replace(day=1).replace(tzinfo=_tz.utc).timestamp()
                if nx > en + 86400: break
                cum *= 1 + y / 100
        else:
            for x, y in zip(d, v):
                if di <= x <= df: cum *= 1 + y / 100
        return (cum - 1) * 100
    dts = lambda d: [_dt.strptime(x, "%Y-%m-%d").replace(tzinfo=_tz.utc).timestamp() for x in d]
    out = {}
    for k, f in (("@ibov", lambda: (lambda h: price(h["t"], h["c"]))(history.get("IBOV", "d"))),
                 ("@usd", lambda: (lambda b: price(dts(b["d"]), b["v"]))(history.bcb("usd"))),
                 ("@gold", lambda: (lambda b: price(dts(b["d"]), b["v"]))(history.gold())),
                 ("@cdi", lambda: (lambda b: rate(b["d"], b["v"]))(history.bcb("cdi"))),
                 ("@ipca", lambda: (lambda b: rate(b["d"], b["v"]))(history.bcb("ipca"))),
                 ("@poup", lambda: (lambda b: rate(b["d"], b["v"]))(history.bcb("poup")))):
        try:
            v = f()
            if v is not None: out[k] = round(v, 4)
        except Exception as e:
            log.warning("retorno %s: %s", k, e)
    return out

_retw = {"busy": False}

@app.get("/api/idxret")
def api_idxret(di: str, df: str):
    """Só os índices (Ibovespa, CDB, IPCA…) entre di e df: aba Carteira (leve, sem as ações)."""
    try: return JSONResponse(_idx_returns(di, df), headers={"Cache-Control": "public, max-age=3600"})
    except ValueError: return JSONResponse({"error": "datas inválidas"}, status_code=400)

@app.get("/api/returns")
def api_returns(di: str, df: str):
    """Variação % de todas as ações mantidas + índices entre di e df. Se o histórico ainda está aquecendo
    (servidor recém-iniciado), responde 202 {warming} na hora e aquece em segundo plano; o app tenta de novo."""
    rows = (cache.data or {}).get("rows") or []
    if not rows:
        return JSONResponse({"warming": True}, status_code=202, headers={"Cache-Control": "no-store"})
    rows = universe.tradable(rows)
    tick = [r["ticker"] for r in rows]
    miss = [t for t in tick if t not in history._allc["d"]]
    if len(miss) > 20:
        if not _retw["busy"]:
            _retw["busy"] = True
            def _bg():
                try: history.all_closes(tick)
                finally: _retw["busy"] = False
            threading.Thread(target=_bg, daemon=True).start()
        return JSONResponse({"warming": True, "faltam": len(miss)}, status_code=202, headers={"Cache-Control": "no-store"})
    return JSONResponse(period_returns(di, df, tick), headers={"Cache-Control": "public, max-age=600"})

def period_returns(di, df, tickers):
    """Variação % do preço entre di e df (AAAA-MM-DD) de cada ticker + índices. Fonte única: aba Comparar e chat.
    Base = último fechamento até di; fim = último fechamento até df ou o preço atual da aba Ações."""
    from datetime import datetime as _dt
    s0 = _dt.strptime(di, "%Y-%m-%d").timestamp() - 1
    e0 = _dt.strptime(df, "%Y-%m-%d").timestamp() + 86399
    live = {r["ticker"]: (r.get("v") or {}).get("preco") for r in (cache.data or {}).get("rows") or []}
    H = history.all_closes(list(tickers)) if tickers else {}
    out = {t: history.period_return(H.get(t), s0, e0, live.get(t)) for t in tickers}
    out = {k: v for k, v in out.items() if v is not None}
    try: out.update(_idx_returns(di, df))
    except Exception as e: log.warning("índices %s..%s: %s", di, df, e)
    return out

@app.post("/api/chat")
def api_chat(body: dict):
    import chat
    q = str((body or {}).get("q") or "").strip()[:1000]
    if not q: return JSONResponse({"a": "Escreva uma pergunta.", "mode": "regras"})
    rows = [r for r in ((cache.data or {}).get("rows") or [])]
    if not rows: return JSONResponse({"a": "Os dados ainda estão carregando; tente de novo em instantes.", "mode": "regras"})
    MX = ((snapshots.load("metrics", max_mem_age=6 * 3600)[0] or {}).get("metrics")) or {}
    def ret_fn(di, df, T):  # mesmo cálculo da aba Comparar
        try: return period_returns(di, df, T)
        except Exception as e: log.warning("chat ret: %s", e); return {}
    CAD = ((snapshots.load("b3_cad", max_mem_age=12 * 3600)[0] or {}).get("c")) or {}
    key = ((cache.data or {}).get("updated_at"), id(MX), len(CAD))
    if _chat_D.get("key") != key:  # índice de nomes/apelidos: recalcula só quando os dados mudam
        _chat_D.update(key=key, D=chat.build(rows, FIELDS, MX, CAD))
    chat_D = _chat_D["D"]
    def ext_fn(t, c):  # empresa ligada a um assunto (qualquer país do site): mesmos dados das abas
        try:
            if c != "br" and c not in tradingview.COUNTRIES: return None
            rows_c = rows if c == "br" else (cache.get_foreign(c) or {}).get("rows") or []
            r = next((x for x in rows_c if x["ticker"].upper() == t), None)
            if not r: return None
            v = r.get("v") or {}
            return {"ticker": r["ticker"], "nome": r.get("nome"), "var": r.get("var"), "cur": r.get("cur"), "pais": tradingview.COUNTRIES[c][1],
                    "bolsa": tradingview.BOLSA.get(c), "indice": tradingview.YAHOO[c][2],
                    "preco": v.get("preco"), "valmerc": v.get("valmerc"), "pl": v.get("pl")}
        except Exception as e:
            log.warning("chat ext %s/%s: %s", c, t, e); return None
    def quote_fn(k):  # cotação atual de dólar, ouro e Ibovespa (mesmos dados dos gráficos)
        try:
            if k == "@usd": b = history.bcb("usd"); return b["d"][-1], b["v"][-1]
            if k == "@gold": b = history.gold(); return b["d"][-1], b["v"][-1]
            if k == "@ibov": h = history.get("IBOV", "d"); return datetime.utcfromtimestamp(h["t"][-1]).strftime("%Y-%m-%d"), h["c"][-1]
        except Exception as e:
            log.warning("chat cotação %s: %s", k, e)
        return None
    try:
        out = chat.answer2(q, (body or {}).get("hist") or [], chat_D, ret_fn, (body or {}).get("ctx") or {}, ext_fn, quote_fn, (body or {}).get("topic"))
    except Exception:  # nunca devolve erro 500 ao usuário: registra a causa e responde com uma mensagem
        log.exception("chat: erro na pergunta %r", q[:200])
        out = {"a": "Tive um problema para responder agora. Tente de novo em instantes ou reformule a pergunta.", "mode": "regras"}
    return JSONResponse(out, headers={"Cache-Control": "no-store"})

_chat_D = {}

@app.get("/api/chat/log")
def api_chat_log(n: int = 200, only: str = ""):
    """Perguntas feitas ao chat (mais recentes primeiro). only=sem_resposta | reclamacao."""
    import chat
    return JSONResponse(chat.read_log(max(1, min(n, 2000)), only or None), headers={"Cache-Control": "no-store"})

@app.get("/api/metrics")
def api_metrics():
    d, _ = snapshots.load("metrics", max_mem_age=3 * 3600)
    return JSONResponse(d or {}, headers={"Cache-Control": "public, max-age=1800"})

@app.get("/api/noticias")
def api_noticias():
    """Aba Notícias: repassa o snapshot noticias (scripts/fetch_noticias.py); nada é buscado por visita."""
    d, _ = snapshots.load("noticias", max_mem_age=3 * 3600)
    return JSONResponse(d or {"itens": []}, headers={"Cache-Control": "public, max-age=1800"})

@app.get("/api/fg")
def api_fg(full: int = 0):
    """Índice de Medo e Ganância da B3 (snapshot fg, scripts/build_fg.py). Sem full: só os últimos 30 pregões."""
    d, _ = snapshots.load("fg", max_mem_age=3 * 3600)
    if not d: return JSONResponse({}, headers={"Cache-Control": "no-store"})
    if not full: d = dict(d, d=d["d"][-30:], v=d["v"][-30:])
    return JSONResponse(d, headers={"Cache-Control": "public, max-age=1800"})

@app.get("/api/fgcmp")
def api_fgcmp(t: str, di: str, df: str):
    """Comparar → Medo e Ganância: comportamento da ação em cada faixa do índice (medo.analyze)."""
    import medo
    t = t.upper().strip()
    if not history.is_br(t) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", di) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", df):
        return JSONResponse({"error": "parâmetros inválidos"}, status_code=400)
    try:
        return JSONResponse(medo.analyze(t, di, df), headers={"Cache-Control": "public, max-age=1800"})
    except Exception as e:
        log.warning("fgcmp %s: %s", t, e)
        return JSONResponse({"error": "Sem dados para esta análise agora."}, status_code=502)

@app.get("/api/modelos")
def api_modelos():
    """Previsão → Modelos: lista de modelos e meses com dados (modelos.py, snapshot modelos)."""
    import modelos
    try: return JSONResponse(modelos.meta(modelos.data()), headers={"Cache-Control": "public, max-age=1800"})
    except Exception as e:
        log.warning("modelos: %s", e)  # sem snapshot ainda: estado normal (card mostra "indisponível"), não erro do servidor
        return JSONResponse({"error": "Modelos indisponíveis agora."}, headers={"Cache-Control": "no-store"})

@app.post("/api/pin")
def api_pin(body: dict):
    """Favoritos e grupos do usuário (app.js -> sendPins): o histórico dessas ações fica em memória (history.pin, limitado)."""
    history.pin([str(t) for t in ((body or {}).get("t") or [])[:200]])
    return Response(status_code=204)

@app.get("/api/widget")
def api_widget(t: str = ""):
    """Widget de Favoritos do app Android (android/): preço, variação do dia e Barato/Caro (valor_justo.fair, a mesma conta do card)
    só dos tickers pedidos, a partir dos dados já em memória (/api/data). Leve: nada é baixado nem recalculado por pedido."""
    d = cache.data or {}
    rows = d.get("rows") or []
    if not rows: return JSONResponse({"loading": True, "r": []}, status_code=503, headers={"Cache-Control": "no-store"})
    want = [x.strip().upper() for x in (t or "").split(",") if x.strip()][:40]
    by = {r["ticker"]: r for r in rows}
    v = lambda o, k: (o.get("v") or {}).get(k)
    out = []
    for tk in want:
        r = by.get(tk)
        if not r: out.append({"t": tk}); continue
        j, pct, m = valor_justo.fair(r, v, rows)
        out.append({"t": tk, "n": r.get("nome"), "p": v(r, "preco"), "v": r.get("var"),
                    "f": round(pct, 1) if j else None, "m": m if j else None})
    return JSONResponse({"u": d.get("updated_at_sp"), "r": out}, headers={"Cache-Control": "no-store"})

@app.post("/api/modelos")
def api_modelos_sim(body: dict):
    """Simulação dos modelos (Desempenho) ou a tabela mês a mês de uma empresa (tab). Grupos prontos + grupos do usuário."""
    import modelos
    rows = universe.universe((cache.data or {}).get("rows") or [])
    if not rows: return JSONResponse({"warming": True}, status_code=202, headers={"Cache-Control": "no-store"})
    body = dict(body or {})
    body["universo"] = [r["ticker"] for r in rows]
    if body.get("ticker") == "top5": body["ticker"], body["universo"] = "*", modelos.top_sector(rows)  # 5 maiores de cada setor
    user = [{"n": str(g.get("n") or "")[:40], "t": [str(t).upper() for t in (g.get("t") or [])][:30]} for g in (body.get("grupos") or [])[:9]]
    history.pin([t for g in user for t in g["t"]] + [str(t) for t in (body.get("fav") or [])[:60]])  # grupos e Favoritos do usuário: histórico fica em memória
    body["grupos"] = modelos.ready_groups(rows) + user
    try:
        D = modelos.data(); modelos.set_setores(D, rows, _cad())  # setores perenes (Método Barsi)
        out = modelos.run(D, body)
    except Exception:
        log.exception("modelos: simulação"); return JSONResponse({"error": "Não foi possível simular agora."}, status_code=502)
    return JSONResponse(out, status_code=400 if out.get("error") else 200, headers={"Cache-Control": "no-store"})

def _cad():
    """Cadastro oficial da B3 {raiz: [nome, segmento]} (snapshot b3_cad)."""
    return ((snapshots.load("b3_cad", max_mem_age=12 * 3600)[0] or {}).get("c")) or {}

_PRE_T = [0.0]
def _pre():
    """Comparar → Modelos já calculados na rotina diária (snapshot modelos_pre); confere de novo a cada 30 min."""
    import modelos
    if time.time() - _PRE_T[0] < 1800: return
    _PRE_T[0] = time.time()
    try: modelos.set_pre(snapshots.load("modelos_pre", max_mem_age=60)[0]); snapshots.drop("modelos_pre")
    except Exception as e: log.warning("modelos_pre: %s", e)

@app.post("/api/modelos/comparar")
def api_modelos_comparar(body: dict):
    """Comparar → Modelos: empresas escolhidas, todas (1 ticker por empresa) ou as 5 maiores de cada setor."""
    import modelos
    rows = universe.universe((cache.data or {}).get("rows") or [])
    if not rows: return JSONResponse({"warming": True}, status_code=202, headers={"Cache-Control": "no-store"})
    b = body or {}
    u = b.get("u") or "sel"
    tick = [r["ticker"] for r in rows] if u == "all" else modelos.top_sector(rows) if u == "top5" else [str(t).upper() for t in (b.get("t") or [])][:60]
    try:
        # aportes: lista mês a mês da Previsão (ap, w, tx) ou valor inicial + aporte fixo do Comparar (ini, ap)
        if isinstance(b.get("ap"), list): aps, wd, tx = b["ap"], b.get("w") or [], b.get("tx")
        else: aps, wd, tx = [max(0.0, float(b.get("ini") or 0))] + [max(0.0, float(b.get("ap") or 0))] * 600, [], None
        tx = None if tx is None else max(0.0, min(100.0, float(tx)))
        grupos = None
        if b.get("rod"):  # rodízio: grupos prontos + grupos do usuário
            grupos = modelos.ready_groups(rows) + [{"n": str(g.get("n") or "")[:40], "t": [str(t).upper() for t in (g.get("t") or [])][:30]} for g in (b.get("grupos") or [])[:9]]
        history.pin([t for g in (grupos or []) for t in g["t"]] + [str(t) for t in (b.get("fav") or [])[:60]])  # grupos e Favoritos do usuário: histórico fica em memória
        D = modelos.data(); modelos.set_setores(D, rows, _cad()); _pre()
        out = modelos.compare(D, tick, str(b.get("di") or "")[:7], str(b.get("df") or "")[:7], aps, wd, tx, grupos)
    except Exception:
        log.exception("modelos: comparar"); return JSONResponse({"error": "Não foi possível comparar agora."}, status_code=502)
    return JSONResponse(out, status_code=400 if out.get("error") else 200, headers={"Cache-Control": "no-store"})

@app.get("/api/indices/{name}")
def api_indices(name: str):
    if name not in history.SGS:
        return JSONResponse({"error": "índice desconhecido"}, status_code=404)
    try:
        return JSONResponse(history.bcb(name), headers={"Cache-Control": "public, max-age=3600"})
    except Exception as e:
        return JSONResponse({"error": "Banco Central indisponível: " + str(e)[:200]}, status_code=502)

@app.get("/api/btb")
def api_btb():
    """Aluguel de ações (B3): saldo em aberto, taxas médias doador/tomador (% a.a.)."""
    d, _ = snapshots.load("b3_btb", max_mem_age=3 * 3600)
    return JSONResponse(d or {}, headers={"Cache-Control": "public, max-age=1800"})

@app.get("/api/flow")
def api_flow():
    """Fluxo diário por tipo de investidor (B3, R$ mil): compras, vendas, saldo."""
    d, _ = snapshots.load("b3_flow", max_mem_age=3 * 3600)
    return JSONResponse({k: v for k, v in (d or {}).items() if k != "mtd"}, headers={"Cache-Control": "public, max-age=1800"})

with open(os.path.join(BASE, "index.html"), encoding="utf-8") as _fh:  # fonte única: as tags <script> do index.html
    JS_FILES = tuple(re.findall(r'src="/static/(\w+)\.js', _fh.read()))
TW_CSS = os.path.join(BASE, "static", "tw.css")  # gerado no build do Render (scripts/build_css.sh); sem ele usa o CDN
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}
_INDEX = {}

def _hash(path):
    with open(path, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()[:10]

def _index_html():
    """index.html com ?v=<hash do arquivo> em cada JS/CSS: o navegador guarda os arquivos por 1 ano e baixa de novo
    só quando o conteúdo muda. Com static/tw.css, troca o Tailwind do CDN (compila no navegador) pelo CSS pronto."""
    files = [os.path.join(BASE, "index.html"), TW_CSS] + [os.path.join(BASE, n + ".js") for n in JS_FILES]
    key = tuple(os.path.getmtime(f) if os.path.exists(f) else 0 for f in files)
    if _INDEX.get("key") != key:
        with open(files[0], encoding="utf-8") as fh:
            h = fh.read()
        h = re.sub(r'/static/(\w+)\.js(\?v=[^"]*)?"',
                   lambda m: f'/static/{m.group(1)}.js?v={_hash(os.path.join(BASE, m.group(1) + ".js"))}"'
                   if m.group(1) in JS_FILES else m.group(0), h)
        if os.path.exists(TW_CSS) and os.path.getsize(TW_CSS) > 1000 and not os.environ.get("TW_CDN"):  # TW_CDN=1 volta ao CDN
            h = re.sub(r'<script src="https://cdn\.tailwindcss\.com"></script>\s*<script src="/tailwind\.config\.js"></script>',
                       f'<link rel="stylesheet" href="/static/tw.css?v={_hash(TW_CSS)}">', h, count=1)
        h = h.replace('<script src="/static/', f'<script>window.INDICES={json.dumps(history.INDICES, ensure_ascii=False)}</script><script src="/static/', 1)
        _INDEX.update(key=key, html=h.encode("utf-8"))
    return _INDEX["html"]

@app.get("/manifest.webmanifest")
def manifest():
    """Manifesto do app instalável. Nome = <title> e cor = <meta name="theme-color"> do index.html (fonte única)."""
    h = open(os.path.join(BASE, "index.html"), encoding="utf-8").read()
    title = re.search(r"<title>(.*?)</title>", h).group(1)
    color = re.search(r'<meta name="theme-color" content="([^"]+)"', h).group(1)
    icon = lambda f, s, p="any": {"src": f"/static/icons/{f}", "sizes": s, "type": "image/png", "purpose": p}
    m = {"name": title, "short_name": title.split(" — ")[0], "start_url": "/", "scope": "/", "display": "standalone",
         "lang": "pt-BR", "background_color": color, "theme_color": color,
         "icons": [icon("icon-192.png", "192x192"), icon("icon-512.png", "512x512"), icon("maskable-512.png", "512x512", "maskable")]}
    return JSONResponse(m, media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})

@app.get("/sw.js")
def service_worker():
    return FileResponse(os.path.join(BASE, "sw.js"), media_type="application/javascript", headers={"Cache-Control": "no-cache"})

@app.get("/tailwind.config.js")
def tw_config():  # mesma configuração do build (tailwind.config.js), usada só quando o CSS gerado não existe
    return FileResponse(os.path.join(BASE, "tailwind.config.js"), media_type="application/javascript", headers={"Cache-Control": "no-cache"})

@app.get("/static/tw.css")
def tw_css(v: str = ""):
    if not os.path.exists(TW_CSS):
        return JSONResponse({"error": "não encontrado"}, status_code=404)
    return FileResponse(TW_CSS, media_type="text/css", headers=IMMUTABLE if v else {"Cache-Control": "no-cache"})

@app.get("/static/{name}.js")
def extra_js(name: str, v: str = ""):
    if name not in JS_FILES:
        return JSONResponse({"error": "não encontrado"}, status_code=404)
    return FileResponse(os.path.join(BASE, name + ".js"), media_type="application/javascript",
                        headers=IMMUTABLE if v else {"Cache-Control": "no-cache"})

@app.get("/")
def index():
    return Response(_index_html(), media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})
