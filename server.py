#!/usr/bin/env python3
"""Screener B3 — backend FastAPI.
Fonte primária: Fundamentus (resultado.php). Complemento: Status Invest (ao vivo; fallback snapshot diário do GitHub Actions).
Nomes/setores (opcional): brapi.dev /api/quote/list (público, sem token).
"""
import io, json, os, threading, time, logging, math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests

import statusinvest
import tiebreak
import tradingview
import snapshots
import consensus
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
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
    ("liq2m",    "Liquidez 2 meses",   "R$", "high",False, "Liq.2meses",       " LIQUIDEZ MEDIA DIARIA", False, 0,    False),
    ("voldia",   "Volume dia",         "$",  "high",False, None,               None,                     False, 0,    False),
    ("vol10",    "Volume médio 10d (≈semana)", "$", "high", False, None,       None,                     False, 0,    False),
    ("vol30",    "Volume médio 30d (≈mês)", "$", "high", False, None,          None,                     False, 0,    False),
    ("vol90",    "Volume médio 90d",   "$",  "high",False, None,               None,                     False, 0,    False),
    ("cresc5a",  "Cresc. Receita 5a",  "%",  "high",False, "Cresc. Rec.5a",    "CAGR RECEITAS 5 ANOS",   False, 3.0,  True),
    ("lucro5a",  "Cresc. Lucro 5a",    "%",  "high",False, None,               "CAGR LUCROS 5 ANOS",     False, 3.0,  True),
    ("vpa",      "VPA",                "R$", "high",False, "__VPA",            " VPA",                   False, 0.10, True),
    ("lpa",      "LPA",                "R$", "high",False, "__LPA",            " LPA",                   False, 0.10, True),
    ("peg",      "PEG",                "x",  "low", True,  None,               " PEG Ratio",             False, 0.3,  True),
    ("patrliq",  "Patrimônio Líq.",    "R$", None,  False, "Patrim. Líq",      None,                     True,  0,    False),
    ("valmerc",  "Valor de Mercado",   "R$", None,  False, None,               " VALOR DE MERCADO",      False, 0,    False),
]
FIELD_KEYS = [f[0] for f in FIELDS]
VOL_KEYS = ("voldia", "vol10", "vol30", "vol90")
VOL_SHORT = {"voldia": "Vol. dia", "vol10": "Vol. méd. 10d", "vol30": "Vol. méd. 30d", "vol90": "Vol. méd. 90d"}
VOL_EXTRA = {k: {"scale": 1e6, "only": "tv", "short": VOL_SHORT[k]} for k in VOL_KEYS}  # filtro digitado em milhões da moeda local
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

def br_num(s):
    """'1.234,56' / '7,12%' -> float"""
    if s is None: return None
    s = str(s).strip().rstrip("%")
    if s in ("", "-", "nan"): return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None

def fetch_fundamentus():
    r = http_get("https://www.fundamentus.com.br/resultado.php")
    html = r.content.decode("latin-1")
    df = pd.read_html(io.StringIO(html), decimal=",", thousands=".")[0]
    out = {}
    for _, row in df.iterrows():
        t = str(row["Papel"]).strip().upper()
        rec = {}
        for c in df.columns:
            if c == "Papel": continue
            v = row[c]
            if isinstance(v, str):
                v = br_num(v) if "%" in v else num(v.replace(",", ".")) if v.count(".") <= 1 else br_num(v)
            rec[c] = num(v)
        out[t] = rec
    return out

SI_FALLBACK_URL = os.environ.get(
    "SI_FALLBACK_URL",
    "https://raw.githubusercontent.com/jjeffersongirotto-star/Mercado-de-a-es-/data/data/statusinvest.csv")
SI_LOCAL_FILE = os.path.join(BASE, "data", "statusinvest.csv")

def _fmt_sp(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso or "?"

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
            when = _fmt_sp(m.get("fetched_at"))
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
                when = _fmt_sp(json.load(fh).get("fetched_at"))
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
    if not c: return {}, {}
    v = {k: c[k] for k in ("roe", "roa", "mbruta", "mebit", "mliq", "liqcorr", "dlpl", "dlebit", "roic", "cresc5a", "lucro5a", "lpa", "vpa") if k in c}
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
    return {k: x for k, x in v.items() if x is not None}, {k: x for k, x in a.items() if x is not None}

def build():
    t0 = time.time()
    status = {}
    fund = fetch_fundamentus()  # obrigatório
    status["fundamentus"] = f"ok ({len(fund)} papéis) — ao vivo"
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
        cv, ca = cvm_values(snaps["cvm"].get(t), price, f.get("P/VP"))
        if cv: S["cvm"] = cv
        if ca: A["cvm"] = ca
        S = {k: x for k, x in S.items() if x}
        nm = names.get(t) or names.get(t[:4] + "3") or names.get(t[:4] + "4") or {}
        if not nm.get("nome") and (s.get("NOME") or s.get("SETOR")):
            nm = {"nome": s.get("NOME"), "setor": s.get("SETOR")}
        if not nm.get("nome") and t in tv:
            nm = {"nome": tv[t]["m"].get("nome"), "setor": tv[t]["m"].get("setor"), "subsetor": tv[t]["m"].get("subsetor")}
        var = names.get(t, {}).get("var")
        if var is None and t in tv: var = tv[t]["m"].get("var")
        rows.append({"ticker": t, "nome": nm.get("nome"), "setor": nm.get("setor"), "subsetor": nm.get("subsetor"),
                     "insi": bool(s), "var": var, "cur": "BRL", "S": S, "A": A, "div": div})
    rows.sort(key=lambda r: -((r["S"].get("fund") or {}).get("liq2m") or 0))
    now = datetime.now(timezone.utc)
    return {
        "country": "br", "currency": "BRL",
        "updated_at": now.isoformat(),
        "updated_at_sp": now.astimezone(TZ).strftime("%d/%m/%Y %H:%M:%S"),
        "took_s": round(time.time() - t0, 1),
        "status": status,
        "rule": {"rel": REL_THR, "abs": {f[0]: f[8] for f in FIELDS if f[9]}},
        "fields": [{"key": k, "label": l, "unit": u, "dir": d, "excludeNeg": e, "compared": c, **VOL_EXTRA.get(k, {})}
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
    for r in base["rows"]:
        S = dict(r.get("S") or {})
        if yf_store is not None:
            y = yf_store.get(r["ticker"])
            if y: S["yf"] = {k: x for k, x in y.items() if x is not None}
        nr = {k: r.get(k) for k in ("ticker", "nome", "setor", "subsetor", "var", "cur")}
        nr["S"] = S
        if r.get("A"): nr["A"] = r["A"]
        if r["ticker"] in FIN: nr["fin"] = True
        consensus.apply_row(nr, CMP_FIELDS, divergente)
        bkk = set(nr.get("bk") or [])
        cnt["two"] = cnt.get("two", 0) + sum(1 for k_, m in (nr.get("cm") or {}).items() if m.get("t") == "pri" and k_ not in bkk and k_ not in nr["st"])
        cnt["bank"] = cnt.get("bank", 0) + sum(1 for k_ in bkk if k_ not in nr["st"])
        for k_, x in nr["st"].items():
            if k_ in bkk: cnt["bank"] = cnt.get("bank", 0) + 1
            else: cnt[x] += 1
        for s in S: src_count[s] = src_count.get(s, 0) + 1
        rows.append(nr)
    d = {k: v for k, v in base.items() if k != "rows"}
    d["rows"] = rows
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
    d["fields"] = [{**f, **VOL_EXTRA.get(f["key"], {})} for f in base["fields"] if f["key"] in keys_with_data]
    return d

def build_foreign(country):
    tv, desc = load_tv(country)
    rows = []
    for t, x in tv.items():
        m = x["m"]
        rows.append({"ticker": t, "nome": m.get("nome"), "setor": m.get("setor"), "subsetor": m.get("subsetor"),
                     "var": m.get("var"), "cur": m.get("cur"), "S": {"tv": x["v"]}})
    rows.sort(key=lambda r: -(r["S"]["tv"].get("valmerc") or 0))
    now = datetime.now(timezone.utc)
    base = {"country": country, "currency": tradingview.COUNTRIES[country][2],
            "updated_at": now.isoformat(), "updated_at_sp": now.astimezone(TZ).strftime("%d/%m/%Y %H:%M:%S"),
            "status": {"tradingview": desc}, "rule": {"rel": REL_THR, "abs": {f[0]: f[8] for f in FIELDS if f[9]}},
            "fields": [{"key": k, "label": l, "unit": ("" if u == "R$" else u), "dir": d, "excludeNeg": e, "compared": c, **VOL_EXTRA.get(k, {})}
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

app = FastAPI(title="Screener B3")
app.add_middleware(GZipMiddleware, minimum_size=2000)
app.mount("/static/logos", StaticFiles(directory=os.path.join(BASE, "static", "logos")), name="logos")
app.mount("/static/flags", StaticFiles(directory=os.path.join(BASE, "static", "flags")), name="flags")

@app.on_event("startup")
def _start():
    threading.Thread(target=scheduler, daemon=True).start()
    if cache.base is not None:
        cache.tiebreak_async()

@app.get("/api/countries")
def api_countries():
    return [{"id": k, "name": v[1], "currency": v[2], "flag": f"/static/flags/{k}.png",
             "sources": [{"id": i, "name": n, "logo": f"/static/logos/{l}"} for i, n, l, cs in SOURCES if k in cs]}
            for k, v in tradingview.COUNTRIES.items()]

@app.get("/api/data")
def api_data(country: str = "br"):
    country = (country or "br").lower()
    if country != "br" and country in tradingview.COUNTRIES:
        d = cache.get_foreign(country)
        if not d["rows"]:
            return JSONResponse({"loading": False, "error": d["status"].get("tradingview")}, status_code=502)
        return d
    if cache.data is None:
        if not cache.refreshing:
            cache.refresh_async()
        return JSONResponse({"loading": True, "error": cache.last_error}, status_code=503)
    d = dict(cache.data); d["refreshing"] = cache.refreshing; d["last_error"] = cache.last_error
    return d

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

@app.get("/static/app.js")
def app_js():
    return FileResponse(os.path.join(BASE, "app.js"), media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})

@app.get("/")
def index():
    return FileResponse(os.path.join(BASE, "index.html"),
                        headers={"Cache-Control": "no-cache"})
