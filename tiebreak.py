"""Desempate das divergências grosseiras (Fundamentus × Status Invest) usando o yfinance como 3ª fonte.

- Só consulta tickers que têm ao menos uma célula vermelha em indicador com equivalente no Yahoo.
- Coleta em thread de fundo, sequencial, com pausa e retries; cache em disco com TTL de 24 h.
- Se o Yahoo bloquear (muitas falhas seguidas) ou o yfinance não estiver instalado, usa o snapshot
  publicado na branch `data` (data/yfinance.json, gerado por scripts/fetch_yfinance.py) e depois o arquivo local.
"""
import copy, json, logging, os, threading, time
from datetime import datetime, timezone

import requests

log = logging.getLogger("screener.tiebreak")

# chave do indicador -> (campo do yfinance .info, multiplicador). Só definições comparáveis.
YF_MAP = {
    "preco":    ("currentPrice", 1),
    "pl":       ("trailingPE", 1),
    "pvp":      ("priceToBook", 1),
    "psr":      ("priceToSalesTrailing12Months", 1),
    "dy":       ("trailingAnnualDividendYield", 100),   # NÃO usar dividendYield (inconsistente)
    "roe":      ("returnOnEquity", 100),
    "roa":      ("returnOnAssets", 100),
    "mbruta":   ("grossMargins", 100),
    "mebit":    ("operatingMargins", 100),             # margem operacional ≈ margem EBIT (não EBITDA)
    "mliq":     ("profitMargins", 100),
    "evebitda": ("enterpriseToEbitda", 1),
    "liqcorr":  ("currentRatio", 1),
    "vpa":      ("bookValue", 1),
    "lpa":      ("trailingEps", 1),
}
ZERO_IS_NA = {"mbruta", "mebit", "mliq", "pl", "pvp", "psr", "evebitda", "liqcorr"}  # Yahoo usa 0 p/ "sem dado" (ex.: bancos)
TTL = 24 * 3600
REPO_RAW = os.environ.get(
    "YF_FALLBACK_URL",
    "https://raw.githubusercontent.com/jjeffersongirotto-star/Mercado-de-a-es-/data/data/yfinance.json")


def extract(info):
    out = {}
    for key, (field, mult) in YF_MAP.items():
        v = info.get(field)
        if key == "preco" and v is None:
            v = info.get("regularMarketPrice")
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if v != v or v in (float("inf"), float("-inf")):
            continue
        if v == 0 and key in ZERO_IS_NA:
            continue
        out[key] = round(v * mult, 6)
    return out


def fetch_one(ticker, tries=3):
    import yfinance as yf  # import tardio: o app funciona sem yfinance
    wait = 1.5
    last = None
    for i in range(tries):
        try:
            info = yf.Ticker(ticker + ".SA").info or {}
            if info.get("regularMarketPrice") is None and info.get("currentPrice") is None and len(info) < 5:
                return None  # ticker sem dados no Yahoo (não é bloqueio)
            return extract(info)
        except Exception as e:  # noqa
            last = e
            msg = str(e).lower()
            if "404" in msg or "not found" in msg:
                return None
            time.sleep(wait); wait *= 2
    raise RuntimeError(f"{ticker}: {type(last).__name__}: {str(last)[:120]}")


def tickers_needing(base_rows):
    """Tickers com célula vermelha em indicador mapeado, líquidos primeiro (rows já vêm por liquidez)."""
    return [r["ticker"] for r in base_rows if any(k in YF_MAP for k in (r.get("div") or {}))]


class YFStore:
    def __init__(self, path):
        self.path = path
        self.data = {}      # ticker -> {"t": iso, "v": {...} | None, "src": "live"|"snapshot"}
        self.lock = threading.Lock()
        self.status = "não iniciado"
        self.running = False
        self.blocked_until = 0.0   # após bloqueio, não tenta ao vivo por um tempo (usa snapshot)
        try:
            with open(path, encoding="utf-8") as fh:
                self.data = json.load(fh)
        except Exception:
            pass

    def save(self):
        with self.lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False)
            os.replace(tmp, self.path)

    def get(self, t):
        e = self.data.get(t)
        return None if e is None else e.get("v")

    def has(self, t):
        return t in self.data

    def stale(self, tickers):
        now = time.time()
        out = []
        for t in tickers:
            e = self.data.get(t)
            if not e or e.get("src") != "live":
                out.append(t); continue
            try:
                age = now - datetime.fromisoformat(e["t"]).timestamp()
            except Exception:
                age = 1e12
            if age > TTL:
                out.append(t)
        return out

    def put(self, t, v, src="live", when=None):
        with self.lock:
            self.data[t] = {"t": when or datetime.now(timezone.utc).isoformat(timespec="seconds"), "v": v, "src": src}

    def load_snapshot(self, only_missing=True):
        """Snapshot da branch data (raw.githubusercontent) e, se falhar, data/yfinance.json local."""
        snap, origin = None, None
        try:
            r = requests.get(REPO_RAW, timeout=(10, 30))
            if r.status_code == 200:
                snap, origin = r.json(), "snapshot GitHub"
        except Exception as e:
            log.warning("snapshot yfinance GitHub: %s", e)
        if snap is None:
            local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "yfinance.json")
            if os.path.exists(local):
                with open(local, encoding="utf-8") as fh:
                    snap, origin = json.load(fh), "arquivo local"
        if not snap:
            return None
        when = snap.get("fetched_at")
        n = 0
        for t, v in (snap.get("tickers") or {}).items():
            e = self.data.get(t)
            if only_missing and e and e.get("src") == "live" and e.get("v"):
                continue
            self.put(t, v, src="snapshot", when=when); n += 1
        return f"{origin} de {fmt_sp(when)} ({n} tickers)"


def fmt_sp(iso):
    try:
        from zoneinfo import ZoneInfo
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso or "?"


def run_fetch(store, tickers, on_progress=None, delay=0.35, max_consecutive_fail=8):
    """Coleta sequencial. Retorna (ok, falhas, bloqueado:bool, msg)."""
    todo = store.stale(tickers)
    ok = fail = consec = with_data = 0
    fetched_now = []
    try:
        import yfinance  # noqa: F401
    except Exception as e:
        return 0, 0, True, f"yfinance indisponível ({type(e).__name__})"
    for i, t in enumerate(todo, 1):
        try:
            v = fetch_one(t)
            store.put(t, v, src="live"); fetched_now.append(t)
            ok += 1; consec = 0
            if v:
                with_data += 1
            elif ok >= 15 and with_data == 0:
                # Yahoo responde, mas sem dados (bloqueio "suave" visto em IPs de datacenter)
                for x in fetched_now:
                    store.data.pop(x, None)
                store.save()
                return ok, fail, True, "Yahoo devolveu dados vazios (provável bloqueio)"
        except Exception as e:
            fail += 1; consec += 1
            log.warning("yfinance %s", e)
            if consec >= max_consecutive_fail:
                store.save()
                return ok, fail, True, f"bloqueado/erros seguidos ({str(e)[:80]})"
        if on_progress and i % 25 == 0:
            store.save(); on_progress()
        time.sleep(delay)
    store.save()
    return ok, fail, False, f"{ok} consultados agora, {fail} falhas"


def _rel(x, y):
    m = max(abs(x), abs(y))
    return 0.0 if m == 0 else abs(x - y) / m


def apply(base, store, divergente, abs_thr):
    """Retorna cópia de `base` com divergências resolvidas por 2 de 3 quando possível."""
    d = copy.deepcopy(base)
    red_before = resolved = 0
    reasons = {"sem_terceira": 0, "yf_sem_dado": 0, "yf_pendente": 0, "tres_divergem": 0}
    for r in d["rows"]:
        div = r.get("div") or {}
        if not div:
            continue
        res, info = {}, {}
        yv = store.get(r["ticker"]) or {}
        fetched = store.has(r["ticker"])
        for key, (a, b) in list(div.items()):
            red_before += 1
            if key not in YF_MAP:
                info[key] = {"reason": "sem_terceira"}; reasons["sem_terceira"] += 1; continue
            c = yv.get(key)
            if c is None:
                why = "yf_sem_dado" if fetched else "yf_pendente"
                info[key] = {"reason": why}; reasons[why] += 1; continue
            thr = abs_thr.get(key, 0)
            cand = sorted([(_rel(a, c), "fund", a), (_rel(b, c), "si", b)])
            best = cand[0]
            if not divergente(best[2], c, thr):
                res[key] = {"f": a, "s": b, "y": c, "w": best[1]}
                r["v"][key] = best[2]
                if best[1] == "si":
                    r.setdefault("src", {})[key] = "si"
                del div[key]
                resolved += 1
            else:
                info[key] = {"reason": "tres_divergem", "y": c}; reasons["tres_divergem"] += 1
        if res:
            r["res"] = res
        if info:
            r["divinfo"] = info
    c = d["counts"]
    c["red_before"] = red_before
    c["resolved"] = resolved
    c["red"] = red_before - resolved
    c["red_reasons"] = reasons
    return d
