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
KINDS = {"m": ("20y", "1mo", 6 * 3600), "d": ("5y", "1d", 3 * 3600), "i": ("1d", "5m", 120)}
_mem = {}

def _ysym(t):
    t = t.upper()
    return "^BVSP" if t in ("IBOV", "^BVSP") else t + ".SA"

def yahoo(t, kind):
    rng, itv, _ = KINDS[kind]
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

def brapi(t, kind):
    rng, itv, _ = KINDS[kind]
    sym = "^BVSP" if t.upper() in ("IBOV", "^BVSP") else t.upper()
    p = {"range": {"20y": "max"}.get(rng, rng), "interval": itv, "dividends": "true"}
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

def snapshot(t, kind):
    if kind == "i":
        raise RuntimeError("snapshot sem intradiário")
    r = requests.get(f"{RAW}/history/{t.upper()}.json.gz", timeout=(6, 30))
    r.raise_for_status()
    d = json.loads(gzip.decompress(r.content))[kind]
    d["source"] = "cópia diária (Yahoo, " + d.get("at", "?") + ")"
    return d

def get(t, kind):
    t = t.upper().strip()
    if kind not in KINDS or not t.replace("^", "").isalnum() or len(t) > 12:
        raise ValueError("parâmetros inválidos")
    key = (t, kind)
    c = _mem.get(key)
    if c and time.time() - c[0] < KINDS[kind][2]:
        return c[1]
    errs = []
    for f in (yahoo, brapi, snapshot):
        try:
            d = f(t, kind)
            if len(_mem) > 600:
                _mem.clear()
            _mem[key] = (time.time(), d)
            return d
        except Exception as e:
            errs.append(f"{f.__name__}: {str(e)[:80]}")
    log.warning("histórico %s/%s falhou: %s", t, kind, errs)
    if c:
        return c[1]
    raise RuntimeError("; ".join(errs))

# ---------- Banco Central (SGS) ----------
SGS = {"cdi": 12, "ipca": 433, "poup": 25, "usd": 1}
_bcb = {}

def bcb(name):
    """Série completa dos últimos ~20 anos (BCB limita a 10 anos por consulta para séries diárias)."""
    c = _bcb.get(name)
    if c and time.time() - c[0] < 6 * 3600:
        return c[1]
    code = SGS[name]
    out, end = {}, datetime.now()
    for k in range(4):
        a, b = end - timedelta(days=1826 * (k + 1) - 1), end - timedelta(days=1826 * k)
        r = requests.get(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados",
                         params={"formato": "json", "dataInicial": a.strftime("%d/%m/%Y"), "dataFinal": b.strftime("%d/%m/%Y")},
                         headers=UA, timeout=(6, 40))
        r.raise_for_status()
        for x in r.json():
            d, m, y = x["data"].split("/")
            if name == "poup" and d != "01":
                continue
            out[f"{y}-{m}-{d}"] = float(x["valor"])
    if not out:
        raise RuntimeError("BCB vazio")
    s = sorted(out.items())
    res = {"d": [a for a, _ in s], "v": [b for _, b in s]}
    _bcb[name] = (time.time(), res)
    return res
