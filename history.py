"""Histórico de preços/dividendos (Previsão e Gráfico) e índices do Banco Central.
Ordem de fontes para ações/Ibovespa: Yahoo chart API -> brapi.dev -> snapshot da branch `data`
(data/history/{TICKER}.json, gerado na máquina da rotina diária por scripts/fetch_history.py).
Formato: {"t": [epoch s], "c": [fechamento], "div": [[epoch s, valor/ação], ...], "source": str}"""
import gzip, json, logging, os, time
from datetime import datetime, timedelta
import requests

log = logging.getLogger("screener.hist")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
RAW = os.environ.get("SNAPSHOT_RAW_BASE",
                     "https://raw.githubusercontent.com/jjeffersongirotto-star/Mercado-de-a-es-/data/data")
KINDS = {"m": ("max", "1mo", 6 * 3600), "d": ("5y", "1d", 3 * 3600), "i": ("1d", "5m", 120)}
_mem = {}

def _ysym(t):
    t = t.upper()
    return "^BVSP" if t in ("IBOV", "^BVSP") else t + ".SA"

def yahoo(t, kind, rng=None):
    rng0, itv, _ = KINDS[kind]; rng = rng or rng0
    last = None
    for host in ("query1", "query2"):
        try:
            r = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{_ysym(t)}",
                             params={"range": rng, "interval": itv, "events": "div,split"}, headers={"User-Agent": "Mozilla/5.0"}, timeout=(6, 20))
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            ts, cl = res.get("timestamp") or [], res["indicators"]["quote"][0]["close"]
            pts = [(a, b) for a, b in zip(ts, cl) if b is not None]
            if not pts:
                raise ValueError("vazio")
            divs = sorted([int(k), float(v["amount"])] for k, v in (res.get("events", {}).get("dividends") or {}).items())
            return {"t": [p[0] for p in pts], "c": [round(p[1], 4) for p in pts], "div": divs, "source": "Yahoo Finance"}
        except Exception as e:
            last = e
    raise RuntimeError(f"Yahoo: {last}")

def brapi(t, kind, rng=None):
    rng0, itv, _ = KINDS[kind]; rng = rng or rng0
    sym = "^BVSP" if t.upper() in ("IBOV", "^BVSP") else t.upper()
    p = {"range": rng, "interval": itv, "dividends": "true"}
    tok = os.environ.get("BRAPI_TOKEN")
    if tok:
        p["token"] = tok
    r = requests.get(f"https://brapi.dev/api/quote/{sym}", params=p, headers=UA, timeout=(6, 25))
    r.raise_for_status()
    d = r.json()["results"][0]
    pts = [(x["date"], x["close"]) for x in d.get("historicalDataPrice") or [] if x.get("close") is not None]
    if not pts:
        raise RuntimeError("brapi: sem histórico")
    pts.sort()
    divs = []
    for x in (d.get("dividendsData") or {}).get("cashDividends") or []:
        try:
            dt = x.get("lastDatePrior") or x.get("paymentDate")
            divs.append([int(datetime.fromisoformat(dt.replace("Z", "+00:00")).timestamp()), float(x["rate"])])
        except Exception:
            pass
    return {"t": [p[0] for p in pts], "c": [p[1] for p in pts], "div": sorted(divs), "source": "brapi.dev"}

def snapshot(t, kind, rng=None):
    if kind == "i":
        raise RuntimeError("snapshot sem intradiário")
    r = requests.get(f"{RAW}/history2/{t.upper()}.json.gz", timeout=(6, 30))
    r.raise_for_status()
    d = json.loads(gzip.decompress(r.content))[kind]
    d["source"] = "cópia diária (Yahoo, " + d.get("at", "?") + ")"
    return d

DISK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "hist")
os.makedirs(DISK, exist_ok=True)
INC = {"d": "1mo", "m": "1y"}

def _dload(name):
    try:
        with open(os.path.join(DISK, name + ".json")) as f:
            return json.load(f)
    except Exception:
        return None

def _dsave(name, d):
    try:
        p = os.path.join(DISK, name + ".json")
        with open(p + ".tmp", "w") as f:
            json.dump(d, f, separators=(",", ":"))
        os.replace(p + ".tmp", p)
    except Exception as e:
        log.warning("disco: %s", e)

def _merge(old, new):
    """Junta séries: pontos novos substituem os do mesmo período (mês/dia) a partir do 1º ponto novo."""
    cut = new["t"][0]
    t = [x for x in old["t"] if x < cut]
    c = old["c"][:len(t)]
    divs = {d[0]: d[1] for d in old.get("div", [])}
    divs.update({d[0]: d[1] for d in new.get("div", [])})
    return {"t": t + new["t"], "c": c + new["c"], "div": sorted([k, v] for k, v in divs.items()), "source": new["source"]}

def get(t, kind):
    t = t.upper().strip()
    if t == "^BVSP":
        t = "IBOV"
    if kind not in KINDS or not t.replace("^", "").isalnum() or len(t) > 12:
        raise ValueError("parâmetros inválidos")
    key, name = (t, kind), f"{t}_{kind}v2"
    c = _mem.get(key)
    if c and time.time() - c[0] < KINDS[kind][2]:
        return c[1]
    base = c[1] if c else (_dload(name) if kind != "i" else None)
    if base and kind != "i" and time.time() - base.get("_at", 0) < KINDS[kind][2]:
        _mem[key] = (base["_at"], base); return base
    errs = []
    for f in (yahoo, brapi) if base else (yahoo, brapi, snapshot):
        try:
            if base and base.get("t"):
                d = _merge(base, f(t, kind, INC[kind]))   # incremental: só os últimos dias/meses
            else:
                d = f(t, kind)
            d["_at"] = time.time()
            if len(_mem) > 600:
                _mem.clear()
            _mem[key] = (time.time(), d)
            if kind != "i":
                _dsave(name, d)
            return d
        except Exception as e:
            errs.append(f"{f.__name__}: {str(e)[:80]}")
    log.warning("histórico %s/%s falhou: %s", t, kind, errs)
    if base:
        return base
    raise RuntimeError("; ".join(errs))

def chart(t, kind):
    """Uma requisição por período: ação + Ibovespa + índices BCB (exceto intradiário)."""
    out = {"stock": get(t, kind)}
    try:
        out["ibov"] = get("IBOV", kind)
    except Exception as e:
        out["ibov"] = {"error": str(e)[:120]}
    if kind != "i":
        for n in SGS:
            try:
                b = bcb(n)
                t0 = out["stock"]["t"][0] if out["stock"].get("t") else 0
                cut = datetime.fromtimestamp(t0 - 40 * 86400).strftime("%Y-%m-%d")
                i0 = next((i for i, x in enumerate(b["d"]) if x >= cut), len(b["d"]))
                out[n] = {"d": b["d"][i0:], "v": b["v"][i0:]}
            except Exception as e:
                out[n] = {"error": str(e)[:120]}
        try:
            b = gold()
            t0 = out["stock"]["t"][0] if out["stock"].get("t") else 0
            cut = datetime.fromtimestamp(t0 - 40 * 86400).strftime("%Y-%m-%d")
            i0 = next((i for i, x in enumerate(b["d"]) if x >= cut), len(b["d"]))
            out["gold"] = {"d": b["d"][i0:], "v": b["v"][i0:]}
        except Exception as e:
            out["gold"] = {"error": str(e)[:120]}
    return out

# ---------- Ouro em reais (Yahoo GC=F em US$/onça × dólar PTAX do BCB) ----------
_gold = {}

def gold():
    c = _gold.get("g")
    if c and time.time() - c[0] < 6 * 3600:
        return c[1]
    base = _dload("gold")
    if not base:
        try:
            r = requests.get(f"{RAW}/history/gold.json", timeout=(6, 20))
            if r.status_code == 200:
                base = r.json()
        except Exception:
            pass
    out = dict(zip(base["d"], base["v"])) if base else {}
    try:
        usd = bcb("usd"); ud = dict(zip(usd["d"], usd["v"])); keys = usd["d"]
        import bisect
        for rng, itv in ((("5d", "1d"),) if out else (("max", "1mo"), ("5y", "1d"))):
            for host in ("query1", "query2"):
                q = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/GC=F", params={"range": rng, "interval": itv}, headers={"User-Agent": "Mozilla/5.0"}, timeout=(6, 25))
                if q.status_code == 200:
                    break
            q.raise_for_status()
            x = q.json()["chart"]["result"][0]
            for ts, cl in zip(x.get("timestamp") or [], x["indicators"]["quote"][0]["close"]):
                if not cl:
                    continue
                d = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                i = bisect.bisect_right(keys, d) - 1
                if i >= 0:
                    out[d] = round(cl * ud[keys[i]], 2)
    except Exception as e:
        if not out:
            raise
        log.warning("ouro incremental falhou: %s", e)
    s2 = sorted(out.items())
    res = {"d": [a for a, _ in s2], "v": [b for _, b in s2]}
    _gold["g"] = (time.time(), res)
    _dsave("gold", res)
    return res

# ---------- Banco Central (SGS) ----------
SGS = {"cdi": 12, "ipca": 433, "poup": 25, "usd": 1}
_bcb = {}

def _bcb_fetch(code, a, b):
    r = requests.get(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados",
                     params={"formato": "json", "dataInicial": a.strftime("%d/%m/%Y"), "dataFinal": b.strftime("%d/%m/%Y")},
                     headers=UA, timeout=(6, 40))
    r.raise_for_status()
    return r.json()

def bcb(name):
    """~20 anos (consultas de 5 anos). Guardado em disco; depois só busca os últimos 60 dias."""
    c = _bcb.get(name)
    if c and time.time() - c[0] < 6 * 3600:
        return c[1]
    code, end = SGS[name], datetime.now()
    base = c[1] if c else _dload("bcb_" + name)
    if not base:
        try:
            r = requests.get(f"{RAW}/history/bcb_{name}.json", timeout=(6, 20))
            if r.status_code == 200:
                base = r.json()
        except Exception:
            pass
    out = dict(zip(base["d"], base["v"])) if base else {}
    windows = [(end - timedelta(days=60), end)] if out else \
        [(end - timedelta(days=1826 * (k + 1) - 1), end - timedelta(days=1826 * k)) for k in range(4)]
    try:
        for a, b in windows:
            for x in _bcb_fetch(code, a, b):
                d, m, y = x["data"].split("/")
                if name == "poup" and d != "01":
                    continue
                out[f"{y}-{m}-{d}"] = float(x["valor"])
    except Exception as e:
        if not out:
            raise
        log.warning("BCB %s incremental falhou: %s", name, e)
    if not out:
        raise RuntimeError("BCB vazio")
    s = sorted(out.items())
    res = {"d": [a for a, _ in s], "v": [b for _, b in s]}
    _bcb[name] = (time.time(), res)
    _dsave("bcb_" + name, res)
    return res
