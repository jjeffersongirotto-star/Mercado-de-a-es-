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
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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
    ("cresc5a",  "Cresc. Receita 5a",  "%",  "high",False, "Cresc. Rec.5a",    "CAGR RECEITAS 5 ANOS",   False, 3.0,  True),
    ("lucro5a",  "Cresc. Lucro 5a",    "%",  "high",False, None,               "CAGR LUCROS 5 ANOS",     False, 3.0,  True),
    ("vpa",      "VPA",                "R$", "high",False, "__VPA",            " VPA",                   False, 0.10, True),
    ("lpa",      "LPA",                "R$", "high",False, "__LPA",            " LPA",                   False, 0.10, True),
    ("peg",      "PEG",                "x",  "low", True,  None,               " PEG Ratio",             False, 0.3,  True),
    ("patrliq",  "Patrimônio Líq.",    "R$", None,  False, "Patrim. Líq",      None,                     True,  0,    False),
    ("valmerc",  "Valor de Mercado",   "R$", None,  False, None,               " VALOR DE MERCADO",      False, 0,    False),
]
FIELD_KEYS = [f[0] for f in FIELDS]
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

def build():
    t0 = time.time()
    status = {}
    fund = fetch_fundamentus()  # obrigatório
    status["fundamentus"] = f"ok ({len(fund)} papéis)"
    try:
        si, si_src = fetch_statusinvest(); status["statusinvest"] = f"ok ({len(si)} papéis) — {si_src}"
    except Exception as e:
        si = {}; status["statusinvest"] = f"falhou: {e}"; log.error("Status Invest: %s", e)
    try:
        names = fetch_brapi_names(); status["brapi_nomes"] = f"ok ({len(names)})"
    except Exception as e:
        names = {}; status["brapi_nomes"] = f"falhou: {e}"

    rows, n_red, n_bold = [], 0, 0
    for t, f in fund.items():
        s = si.get(t, {})
        price = f.get("Cotação")
        vals, src, div = {}, {}, {}
        for key, label, unit, d, excl, fcol, scol, zero_na, absthr, cmp in FIELDS:
            fv = None
            if fcol == "__VPA":
                pvp = f.get("P/VP"); fv = round(price / pvp, 4) if price and pvp else None
            elif fcol == "__LPA":
                pl = f.get("P/L"); fv = round(price / pl, 4) if price and pl else None
            elif fcol:
                fv = f.get(fcol)
                if fv is not None and zero_na and fv == 0:
                    fv = None
            sv = s.get(scol) if scol else None
            if fcol in ("__VPA", "__LPA"):
                # VPA/LPA não existem como coluna no Fundamentus: usa Status Invest; se faltar, calcula
                if sv is not None:
                    vals[key] = sv; src[key] = "si"
                elif fv is not None:
                    vals[key] = fv; src[key] = "calc"
                else:
                    vals[key] = None
            elif fv is not None:
                vals[key] = fv
            elif sv is not None:
                vals[key] = sv; src[key] = "si"
            else:
                vals[key] = None
            if cmp and fv is not None and sv is not None and divergente(fv, sv, absthr):
                div[key] = [fv, sv]
        n_red += len(div); n_bold += sum(1 for v in src.values() if v == "si")
        nm = names.get(t) or names.get(t[:4] + "3") or names.get(t[:4] + "4") or {}
        if not nm.get("nome") and (s.get("NOME") or s.get("SETOR")):
            nm = {"nome": s.get("NOME"), "setor": s.get("SETOR")}
        rows.append({"ticker": t, "nome": nm.get("nome"), "setor": nm.get("setor"),
                     "subsetor": nm.get("subsetor"), "insi": bool(s),
                     "var": names.get(t, {}).get("var"),
                     "v": vals, "src": src, "div": div})
    rows.sort(key=lambda r: -(r["v"].get("liq2m") or 0))
    now = datetime.now(timezone.utc)
    data = {
        "updated_at": now.isoformat(),
        "updated_at_sp": now.astimezone(TZ).strftime("%d/%m/%Y %H:%M:%S"),
        "took_s": round(time.time() - t0, 1),
        "status": status,
        "rule": {"rel": REL_THR, "abs": {f[0]: f[8] for f in FIELDS if f[9]}},
        "fields": [{"key": k, "label": l, "unit": u, "dir": d, "excludeNeg": e,
                    "fund": bool(fc), "si": bool(sc), "compared": c}
                   for k, l, u, d, e, fc, sc, z, a, c in FIELDS],
        "counts": {"tickers": len(rows), "liquidas": sum(1 for r in rows if (r["v"].get("liq2m") or 0) > 0),
                   "red": n_red, "bold": n_bold, "si_matched": sum(1 for r in rows if r["insi"])},
        "rows": rows,
    }
    return data

# ---------------------------------------------------------------------------
class Cache:
    def __init__(self):
        self.data = None
        self.lock = threading.Lock()
        self.refreshing = False
        self.last_error = None
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, encoding="utf-8") as fh:
                    self.data = json.load(fh)
                log.info("cache de disco carregado (%s)", self.data.get("updated_at_sp"))
            except Exception as e:
                log.warning("cache de disco inválido: %s", e)

    def age(self):
        if not self.data: return 1e12
        return (datetime.now(timezone.utc) - datetime.fromisoformat(self.data["updated_at"])).total_seconds()

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
            self.data = d; self.last_error = None
            log.info("atualizado: %s", d["counts"])
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

cache = Cache()

def scheduler():
    while True:
        if cache.age() >= REFRESH_SECONDS:
            cache.refresh()
        time.sleep(60)

app = FastAPI(title="Screener B3")

@app.on_event("startup")
def _start():
    threading.Thread(target=scheduler, daemon=True).start()

@app.get("/api/data")
def api_data():
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
    return {"started": started, "refreshing": True}

@app.get("/api/status")
def api_status():
    d = cache.data or {}
    return {"refreshing": cache.refreshing, "updated_at": d.get("updated_at"),
            "updated_at_sp": d.get("updated_at_sp"), "counts": d.get("counts"),
            "status": d.get("status"), "last_error": cache.last_error}

@app.get("/static/app.js")
def app_js():
    return FileResponse(os.path.join(BASE, "app.js"), media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})

@app.get("/")
def index():
    return FileResponse(os.path.join(BASE, "index.html"),
                        headers={"Cache-Control": "no-cache"})
