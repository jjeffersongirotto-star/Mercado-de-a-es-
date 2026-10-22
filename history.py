"""Histórico de preços/dividendos (Previsão e Gráfico) e índices do Banco Central.
Ordem de fontes para ações/Ibovespa: Yahoo chart API -> brapi.dev -> snapshot da branch `data`
(data/history/{TICKER}.json, gerado na máquina da rotina diária por scripts/fetch_history.py).
Formato: {"t": [epoch s], "c": [fechamento], "div": [[epoch s, valor/ação], ...], "source": str}"""
import gzip, json, logging, os, threading, time
from functools import partial
from datetime import datetime, timedelta
import numpy as np
import requests

log = logging.getLogger("screener.hist")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
from snapshots import RAW
import tradingview
KINDS = {"m": ("max", "1mo", 6 * 3600), "d": ("10y", "1d", 3 * 3600), "i": ("1d", "5m", 120)}
from collections import OrderedDict
_mem = OrderedDict()  # histórico em memória das ações de fora e índices (Yahoo/brapi): no máximo MEM_MAX itens (sai o usado há mais tempo); PIN nunca sai
MEM_MAX = 150
PIN = set()  # grupos prontos do rodízio (trocados a cada atualização dos dados): server.py -> pin(keep=...)
PIN_USER = OrderedDict()  # grupos e Favoritos enviados pelo usuário: ficam entre atualizações; no máximo PIN_USER_MAX (sai o mais antigo)
PIN_USER_MAX = 200

def pin(tickers, keep=None):
    """Tickers com prioridade no cache. keep = grupos prontos (substitui); tickers = do usuário (somam, com limite).
    Ações de fora/índices (_mem): o gráfico não sai do cache. B3: só não saem do LRU _h4 logo depois de all_closes; o LRU (H4_MAX)
    vale para todas, e fora dele b3hist lê a cópia do disco."""
    if keep is not None: PIN.clear(); PIN.update(keep)
    for t in list(tickers or [])[:PIN_USER_MAX]:
        t = str(t).upper()[:12]; PIN_USER[t] = 1; PIN_USER.move_to_end(t)
    while len(PIN_USER) > PIN_USER_MAX: PIN_USER.popitem(last=False)

def _pinned(key):
    return any(str(k).upper() in PIN or str(k).upper() in PIN_USER for k in key[:-1]) if isinstance(key, tuple) else False

_memlk = threading.Lock()

def _put(key, val):
    with _memlk:
        _mem[key] = val; _mem.move_to_end(key)
        free = [k for k in _mem if not _pinned(k)]
        for k in free[:max(0, len(free) - MEM_MAX)]: del _mem[k]

def _ysym(t):
    t = t.upper()
    return "^BVSP" if t in ("IBOV", "^BVSP") else t + ".SA"

def yahoo(t, kind, rng=None, sym=None):
    rng0, itv, _ = KINDS[kind]; rng = rng or rng0
    last = None
    for host in ("query1", "query2"):
        try:
            # Mensal = derivado do diário: no Yahoo, intervalo 1mo e range=max+1d perdem/achatam proventos.
            p = {"interval": "1d" if kind == "m" else itv, "events": "div,split"}
            if rng == "max":
                p.update(period1=0, period2=int(time.time()) + 86400)
            else:
                p["range"] = rng
            r = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym or _ysym(t)}",
                             params=p, headers={"User-Agent": "Mozilla/5.0"}, timeout=(4, 10))
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            ts, cl = res.get("timestamp") or [], res["indicators"]["quote"][0]["close"]
            pts = [(a, b) for a, b in zip(ts, cl) if b is not None]
            if not pts:
                raise ValueError("vazio")
            divs = sorted([int(k), float(v["amount"])] for k, v in (res.get("events", {}).get("dividends") or {}).items())
            if kind == "m":  # um ponto por mês: data do 1º pregão do mês, fechamento do último pregão
                mm = {}
                for a, b in pts:
                    k = time.strftime("%Y-%m", time.gmtime(a))
                    mm[k] = (mm[k][0], b) if k in mm else (a, b)
                pts = [mm[k] for k in sorted(mm)]
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
    r = requests.get(f"https://brapi.dev/api/quote/{sym}", params=p, headers=UA, timeout=(4, 10))
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

def snapshot(t, kind, rng=None, folder="history3"):
    """Cópia da branch data (scripts/fetch_history.py): history3 = Ibovespa; history5 = ações e índices de fora."""
    if kind == "i":
        raise RuntimeError("snapshot sem intradiário")
    r = requests.get(f"{RAW}/{folder}/{t.upper()}.json.gz", timeout=(6, 30))
    r.raise_for_status()
    d = json.loads(gzip.decompress(r.content))[kind]
    d["source"] = "cópia salva (Yahoo, " + d.get("at", "?") + ")"
    return d

def fname(sym):
    """Nome do arquivo do símbolo do Yahoo na branch data (history5): ^GSPC -> _GSPC."""
    return sym.upper().replace("^", "_")

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

# ---------- Ações brasileiras: histórico oficial da B3 (COTAHIST), sem Yahoo ----------
import re as _re, zipfile as _zf, io as _io
_BR = _re.compile(r"[A-Z]{4}\d{1,2}")
_h4 = OrderedDict()  # ticker -> (instante, histórico B3 completo ~1,4 MB): LRU de H4_MAX; fora dele, a cópia no disco (_dload "h4_")
H4_MAX = 30
_h4b = {}  # durante all_closes: históricos tirados do arquivo único (history4_all), lidos por b3hist sem passar pelo LRU
_h4lk = threading.Lock()

def _h4get(t):
    with _h4lk:
        c = _h4.get(t)
        if c is not None: _h4.move_to_end(t)
    return c or _h4b.get(t)

def _h4put(t, c):
    with _h4lk:
        _h4[t] = c; _h4.move_to_end(t)
        while len(_h4) > H4_MAX: _h4.popitem(last=False)
_cotad = {}

def is_br(t):
    return bool(_BR.fullmatch(t))

_cotal = __import__("threading").Lock()
_cotan = {}  # dia ainda não publicado -> momento da última tentativa

def _cota_day(d):
    """Arquivo diário COTAHIST_D{ddmmaaaa}: {isin: (fechamento por ação, ts)}; None se ainda não publicado.
    Um download por dia para todas as ações (trava) e, se ainda não saiu, só tenta de novo após 30 min
    (antes cada uma das ~360 ações baixava/esperava o mesmo arquivo: 'Comparar tudo' levava minutos)."""
    k = d.strftime("%Y%m%d")
    if k in _cotad:
        return _cotad[k]
    if time.time() - _cotan.get(k, 0) < 1800:
        return None
    with _cotal:
        if k in _cotad:
            return _cotad[k]
        if time.time() - _cotan.get(k, 0) < 1800:
            return None
        disk = _dload("cotad_" + k)
        if disk is not None:
            _cotad[k] = disk; return disk
        try:
            r = requests.get(f"https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D{d:%d%m%Y}.ZIP", headers=UA, timeout=(5, 25))
            if r.status_code != 200 or r.content[:2] != b"PK":
                if (datetime.utcnow() - d).days >= 3: _cotad[k] = None  # feriado/sem pregão: não tenta de novo
                else: _cotan[k] = time.time()
                return None
            z = _zf.ZipFile(_io.BytesIO(r.content)); out = {}
            for l in z.read(z.namelist()[0]).decode("latin1").splitlines():
                if l.startswith("01") and l[24:27] == "010" and l[10:12] not in ("96", "10", "14", "22"):
                    out[l[230:242]] = round(int(l[108:121]) / 100 / (int(l[210:217]) or 1), 4)
            _cotad[k] = out; _dsave("cotad_" + k, out)
            return out
        except Exception as e:
            log.warning("COTAHIST diário %s: %s", k, e)
            _cotan[k] = time.time()
            return None

def _h4file(t):
    """Arquivo completo do histórico B3 de uma ação (branch data): diário desde 1995, mensal, proventos.
    ETFs (aba Mercado → ETFs) ficam em history4_etf (fora do "mercado" e dos modelos): gráficos, Comparar e Carteira usam o mesmo caminho."""
    for sub in ("history4", "history4_etf"):
        r = requests.get(f"{RAW}/{sub}/{t}.json.gz", timeout=(6, 30))
        if r.status_code == 404 and sub == "history4": continue
        r.raise_for_status()
        return json.loads(gzip.decompress(r.content))

_h4f = OrderedDict()  # b3full: LRU de H4F_MAX ações
H4F_MAX = 10

def b3full(t):
    """Fechamentos e volumes diários completos (o bundle do servidor tem só 6 anos) + os pregões novos que b3hist já juntou (sem volume).
    Usado pelo Comparar → Medo e Ganância; guardado em memória (as H4F_MAX mais recentes) por 12 h."""
    with _h4lk:
        c = _h4f.get(t)
        if c is not None: _h4f.move_to_end(t)
    if c and time.time() - c[0] < 12 * 3600:
        return c[1]
    d = _h4file(t)["d"]; T, Cc = list(d["t"]), list(d["c"]); Vv = list(d.get("vol") or [None] * len(T))
    try:
        rec = b3hist(t)["d"]
        for a, b in zip(rec["t"], rec["c"]):
            if a > T[-1]: T.append(a); Cc.append(b); Vv.append(None)
    except Exception as e:
        log.info("b3full %s: %s", t, e)
    out = {"t": T, "c": Cc, "v": Vv}
    with _h4lk:
        _h4f[t] = (time.time(), out); _h4f.move_to_end(t)
        while len(_h4f) > H4F_MAX: _h4f.popitem(last=False)
    return out

def b3hist(t):
    c = _h4get(t)
    if c and time.time() - c[0] < 3 * 3600:
        return c[1]
    base = c[1] if c else _dload("h4_" + t)
    if not base:
        base = _h4file(t)
    d = base["d"]
    if d["t"]:
        day = datetime.utcfromtimestamp(d["t"][-1]).date() + timedelta(days=1)
        today = datetime.utcnow().date(); n = 0
        if (today - day).days > 12:  # série parada (deslistada/troca de código): não busca arquivos diários antigos
            day = today + timedelta(days=1)
        while day <= today and n < 15:
            if day.weekday() < 5:
                f = _cota_day(datetime(day.year, day.month, day.day))
                if f and base.get("isin") in f:
                    ts = int(datetime(day.year, day.month, day.day, 13).replace(tzinfo=__import__("datetime").timezone.utc).timestamp())
                    d["t"].append(ts); d["c"].append(f[base["isin"]]); n += 1
                    m = base["m"]
                    if m["t"] and time.strftime("%Y-%m", time.gmtime(m["t"][-1])) == day.strftime("%Y-%m"):
                        m["c"][-1] = f[base["isin"]]
                    else:
                        m["t"].append(ts); m["c"].append(f[base["isin"]])
            day += timedelta(days=1)
    _h4put(t, (time.time(), base)); _dsave("h4_" + t, base)
    return base

def b3get(t, kind):
    h = b3hist(t)
    if kind == "i":  # sem intradiário oficial gratuito: último pregão vs anterior
        d = h["d"]; return {"t": d["t"][-2:], "c": d["c"][-2:], "div": [], "source": "B3 (COTAHIST) · fechamento", "daily": True}
    x = {k: v for k, v in h[kind].items() if k not in ("h", "l")}; x["source"] = "B3 (COTAHIST, " + h["d"].get("at", "") + ")"  # máx./mín. do dia: só os modelos usam
    lab = {d[0]: d[2] for d in h.get("divs") or [] if len(d) > 2}  # tipo do provento (dividendo/JCP) quando a B3 informa
    if lab: x["div"] = [[d[0], d[1], lab[d[0]]] if d[0] in lab else d for d in x.get("div") or []]
    return x

def get(t, kind):
    t = t.upper().strip()
    if is_br(t) and kind in KINDS:
        return b3get(t, kind)
    if t == "^BVSP":
        t = "IBOV"
    if kind not in KINDS or not t.replace("^", "").isalnum() or len(t) > 12:
        raise ValueError("parâmetros inválidos")
    return _hist((t, kind), kind, [partial(yahoo, t), partial(brapi, t)], partial(snapshot, t), f"{t}_{kind}v4")

def _hist(key, kind, live, snap, name):
    """Histórico com cache (memória e disco): frio = cópia da branch data primeiro (rápida); depois só os dias novos ao vivo.
    live: fontes ao vivo em ordem; snap: cópia salva. Fontes fora: devolve o que já tinha."""
    c = _mem.get(key)
    if c:
        with _memlk:
            if key in _mem: _mem.move_to_end(key)
    if c and time.time() - c[0] < KINDS[kind][2]:
        return c[1]
    base = c[1] if c else (_dload(name) if kind != "i" else None)
    if base and kind != "i" and time.time() - base.get("_at", 0) < KINDS[kind][2]:
        _put(key, (base["_at"], base)); return base
    errs = []
    # frio (sem base): cópia diária do data branch primeiro (rápida); Yahoo/brapi só para os dias novos
    for f in live if base else [snap] + live:
        try:
            if base and base.get("t"):
                d = _merge(base, f(kind, INC[kind]))   # incremental: só os últimos dias/meses
            else:
                d = f(kind)
            d["_at"] = time.time()
            _put(key, (time.time(), d))
            if kind != "i":
                _dsave(name, d)
            return d
        except Exception as e:
            errs.append(f"{getattr(f, 'func', f).__name__}: {str(e)[:80]}")
    log.warning("histórico %s falhou: %s", name, errs)
    if base:
        _put(key, (time.time() - KINDS[kind][2] + 1800, base))  # fontes fora: não tenta de novo por 30 min
        return base
    raise RuntimeError("; ".join(errs))

FORA = {"us": 300, "jp": 300, "gb": 200, "de": 150, "pt": None}  # cópia salva: as maiores de cada país por valor de mercado (None = todas)

def copy_update(old, sym, now=None):
    """Cópia salva de um símbolo de fora ({m, d, ts}): sem cópia ou com mais de 25 dias, baixa tudo; senão só junta o último mês/ano.
    Diário guarda 10 anos (igual ao gráfico); mensal, desde o início. -> nova cópia, ou a antiga se ainda tem menos de 6 dias."""
    now = now or time.time()
    if old and now - old.get("ts", 0) < 6 * 86400: return old
    at = time.strftime("%d/%m/%Y", time.gmtime(now)); out = {"ts": int(now)}
    for k in ("m", "d"):
        inc = old and now - old.get("ts", 0) < 25 * 86400 and old.get(k, {}).get("t")
        x = _merge(old[k], yahoo(sym, k, INC[k], sym=sym)) if inc else yahoo(sym, k, sym=sym)
        if k == "d":  # 10 anos no diário
            i0 = next((i for i, t in enumerate(x["t"]) if t >= now - 3653 * 86400), 0)
            x = dict(x, t=x["t"][i0:], c=x["c"][i0:], div=[v for v in x.get("div", []) if v[0] >= now - 3653 * 86400])
        x.pop("_at", None); x["at"] = at; out[k] = x
    return out

def yget(sym, kind):
    """Ação/índice de fora do Brasil (símbolo do Yahoo já com sufixo): cópia semanal da branch data (history5) + dias novos do Yahoo.
    Quem não está na cópia (fora das maiores de cada país) vem só do Yahoo; intradiário sempre ao vivo."""
    return _hist(("y", sym, kind), kind, [partial(yahoo, sym, sym=sym)], partial(snapshot, fname(sym), folder="history5"), f"y_{fname(sym)}_{kind}v1")

def ysym(t, country):
    suf = tradingview.YAHOO[country][0]
    s = t.upper().rstrip(".").replace(".", "-")  # TradingView "RR." / "BRK.B" -> Yahoo "RR" / "BRK-B"
    return f"{s}.{suf}" if suf else s

def _cut(b, t0):  # série diária {d, v} a partir de ~40 dias antes do 1º ponto da ação
    cut = datetime.fromtimestamp(t0 - 40 * 86400).strftime("%Y-%m-%d")
    i0 = next((i for i, x in enumerate(b["d"]) if x >= cut), len(b["d"]))
    return {"d": b["d"][i0:], "v": b["v"][i0:]}

def chart_foreign(t, kind, country):
    """Ação de fora: ação + índice do país (chave ibov) + dólar (BCB); ouro em US$ só nos EUA. Sem índices brasileiros."""
    yx = tradingview.YAHOO[country]
    out = {"stock": yget(yx[1] if t.upper() == "@IX" else ysym(t, country), kind)}
    try: out["ibov"] = yget(yx[1], kind)
    except Exception as e: out["ibov"] = {"error": str(e)[:120]}
    if kind != "i":
        t0 = out["stock"]["t"][0] if out["stock"].get("t") else 0
        try: out["usd"] = _cut(bcb("usd"), t0)
        except Exception as e: out["usd"] = {"error": str(e)[:120]}
        try:  # ouro (US$/onça) na moeda do país: câmbio do Yahoo do mesmo dia (ou o último anterior); sem câmbio, sem ouro
            g = yget("GC=F", "d"); cur = tradingview.COUNTRIES[country][2]
            fx = {}
            if cur != "USD":
                f = yget(f"USD{cur}=X", "d"); fx = {datetime.utcfromtimestamp(x).strftime("%Y-%m-%d"): c for x, c in zip(f["t"], f["c"])}
            d, v, last = [], [], None
            for x, c in zip(g["t"], g["c"]):
                k = datetime.utcfromtimestamp(x).strftime("%Y-%m-%d"); last = fx.get(k, last) if fx else 1.0
                if last: d.append(k); v.append(round(c * last, 2))
            out["gold"] = _cut({"d": d, "v": v}, t0) if v else {"error": "sem câmbio"}
        except Exception as e: out["gold"] = {"error": str(e)[:120]}
    return out

def chart(t, kind, country="br"):
    """Uma requisição por período: ação + Ibovespa + índices BCB (exceto intradiário)."""
    if country != "br":
        return chart_foreign(t, kind, country)
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
    base = _dload("gold4")
    if not base:
        try:
            r = requests.get(f"{RAW}/history/gold3.json", timeout=(6, 20))
            if r.status_code == 200:
                base = r.json()
        except Exception:
            pass
    out = dict(zip(base["d"], base["v"])) if base else {}
    try:
        usd = bcb("usd"); ud = dict(zip(usd["d"], usd["v"])); keys = usd["d"]
        import bisect
        for rng, itv in ((("5d", "1d"),) if out else (("max", "1mo"), ("10y", "1d"))):
            for host in ("query1", "query2"):
                q = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/GC=F", params={"range": rng, "interval": itv}, headers={"User-Agent": "Mozilla/5.0"}, timeout=(4, 10))
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
    _dsave("gold4", res)
    return res

# ---------- Banco Central (SGS) ----------
# Índices dos gráficos/Comparar/chat (fonte única dos nomes; o site recebe em window.INDICES)
INDICES = {"ibov": "Ibovespa", "usd": "Dólar", "cdi": "CDB", "ipca": "Inflação (IPCA)", "poup": "Poupança", "gold": "Ouro"}
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

# ---------- Retornos de todas as ações (aba Comparar → "Comparar com tudo") ----------
_allc = {"at": 0, "d": {}}  # ticker -> {"d"|"m": (t int64, c float64)}: compacto (numpy), ~5× menos memória que listas

def _pack(x):
    """{t: [...], c: [...]} -> (t, c) numpy; fechamento vazio vira NaN"""
    return (np.asarray(x["t"], dtype=np.int64), np.array([np.nan if v is None else v for v in x["c"]], dtype=np.float64))

def _load_both(t):
    try:
        p = b3hist(t)
        return t, {k: _pack(p[k]) for k in ("d", "m")}
    except Exception:
        return t, None

def all_closes(tickers):
    import snapshots
    with snapshots.HEAVY:  # não carrega junto com as tabelas dos modelos (modelos.data): pico de memória menor
        return _all_closes(tickers)

def _all_closes(tickers):
    if time.time() - _allc["at"] > 6 * 3600:
        _allc["d"] = {}; _allc["at"] = time.time()
    miss = [t for t in tickers if t not in _allc["d"]]
    fresh = set()  # carregados aqui só para os retornos: saem do cache de gráficos depois (ficam no disco)
    try:
        return _all_closes2(tickers, miss, fresh)
    finally:
        _h4b.clear()  # o arquivo único não fica na memória

def _all_closes2(tickers, miss, fresh):
    from concurrent.futures import ThreadPoolExecutor
    if len(miss) > 20 and not _allc.get("bundle"):
        try:  # arquivo único com o histórico de todas as ações (um download em vez de ~360)
            r = requests.get(f"{RAW}/history4_all.json.gz", timeout=(6, 60)); r.raise_for_status()
            B = json.loads(gzip.decompress(r.content)); del r; _allc["bundle"] = True
            old = time.time() - 3 * 3600 - 1  # força só a atualização incremental (arquivos diários) depois
            want = set(miss)
            for t, h in B.items():
                if t in want and t not in _h4: _h4b[t] = (old, h); fresh.add(t)
            del B
        except Exception as e:
            log.warning("bundle de histórico: %s", e)
    if miss:
        fresh |= {t for t in miss if t not in _h4}
        with ThreadPoolExecutor(16) as ex:
            for t, v in ex.map(_load_both, miss):
                _allc["d"][t] = v
        with _h4lk:
            for t in fresh:  # gráfico dessas ações volta a ler do disco (b3hist -> _dload) quando alguém abrir
                if t.upper() not in PIN and t.upper() not in PIN_USER: _h4.pop(t, None)
    return _allc["d"]

def period_return(h, start_ts, end_ts, live=None):
    """Base = último fechamento até start_ts; fim = último fechamento até end_ts (ou preço atual). h = all_closes()[ticker]."""
    if not h:
        return None
    for k in ("d", "m"):
        x = h.get(k)
        if x is None or not len(x[0]) or x[0][0] > start_ts:
            continue
        ts, cs = x; ok = ~np.isnan(cs)
        ib = np.nonzero(ok & (ts <= start_ts))[0]; ie = np.nonzero(ok & (ts <= end_ts))[0]
        b = float(cs[ib[-1]]) if len(ib) else None; e = float(cs[ie[-1]]) if len(ie) else None
        last = int(ts[-1])
        stale = min(end_ts, time.time()) - last > 12 * 86400
        if stale and end_ts > last + 12 * 86400:
            return None  # série parada (ex.: troca de ISIN sem histórico novo): não mistura com o preço atual
        if live and end_ts >= last:
            e = live
        if b and e:
            return round((e / b - 1) * 100, 4)
    return None
    for k in ("d", "m"):
        x = h.get(k)
        if not x or not x["t"] or x["t"][0] > start_ts:
            continue
        b = e = None
        for ts, c in zip(x["t"], x["c"]):
            if c is None:
                continue
            if ts <= start_ts:
                b = c
            if ts <= end_ts:
                e = c
        stale = min(end_ts, time.time()) - x["t"][-1] > 12 * 86400
        if stale and end_ts > x["t"][-1] + 12 * 86400:
            return None  # série parada (ex.: troca de ISIN sem histórico novo): não mistura com o preço atual
        if live and end_ts >= x["t"][-1]:
            e = live
        if b and e:
            return round((e / b - 1) * 100, 4)
    return None
