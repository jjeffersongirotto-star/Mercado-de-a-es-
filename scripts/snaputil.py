"""Utilidades comuns dos scripts de snapshot (rodam na máquina da rotina diária, não no Render)."""
import io, json, os, re, html, time
from datetime import datetime, timezone
import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
      "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}

def br_num(s):
    if s is None: return None
    s = str(s).strip().replace("%", "").replace("R$", "").strip()
    if s in ("", "-", "—", "nan", "N/A"): return None
    try: return float(s.replace(".", "").replace(",", "."))
    except ValueError: return None

APP_API = os.environ.get("APP_API", "https://mercado-de-acoes.onrender.com/api/data")
SI_SNAPSHOT = os.environ.get("SI_FALLBACK_URL",
    "https://raw.githubusercontent.com/jjeffersongirotto-star/Mercado-de-a-es-/data/data/statusinvest.csv")

def app_api_data(wait=600):
    """Payload do app no Render (/api/data, Brasil). O Render lê o Fundamentus normalmente.
    Se o servidor estiver acordando/atualizando (503 loading), espera até `wait` s."""
    t0 = time.time(); last = None
    while time.time() - t0 < wait:
        try:
            r = requests.get(APP_API, headers=UA, timeout=180)
            if r.status_code == 200:
                d = r.json()
                if d.get("rows"): return d
                last = "sem linhas"
            else:
                last = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError) as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(20)
    raise RuntimeError(f"API do app indisponível: {last}")

def _fund_direct(only_liquid):
    import pandas as pd
    r = requests.get("https://www.fundamentus.com.br/resultado.php", headers=UA, timeout=60)
    r.raise_for_status()
    df = pd.read_html(io.StringIO(r.content.decode("latin-1")), decimal=",", thousands=".")[0]
    df["liq"] = pd.to_numeric(df["Liq.2meses"], errors="coerce").fillna(0)
    df = df.sort_values("liq", ascending=False)
    if only_liquid: df = df[df["liq"] > 0]
    return [str(t).strip().upper() for t in df["Papel"]]

def _from_app(only_liquid):
    rows = app_api_data()["rows"]  # já vêm ordenadas por liquidez (Fundamentus)
    liq = lambda r: (r.get("v") or {}).get("liq2m") or ((r.get("S") or {}).get("fund") or {}).get("liq2m") or 0
    rows = sorted(rows, key=lambda r: -liq(r))
    return [r["ticker"].upper() for r in rows if not only_liquid or liq(r) > 0]

def _from_statusinvest(only_liquid):
    r = requests.get(SI_SNAPSHOT, headers=UA, timeout=60); r.raise_for_status()
    lines = [l for l in r.content.decode("utf-8", errors="replace").splitlines() if l.strip()]
    hdr = [h.strip().upper() for h in lines[0].lstrip("\ufeff").split(";")]
    if "TICKER" not in hdr[0]: raise RuntimeError("CSV Status Invest inesperado")
    li = next((i for i, h in enumerate(hdr) if "LIQUIDEZ MEDIA DIARIA" in h), None)
    out = []
    for l in lines[1:]:
        p = l.split(";")
        q = br_num(p[li]) if li is not None and li < len(p) else None
        out.append((p[0].strip().upper(), q or 0))
    out.sort(key=lambda x: -x[1])
    return [t for t, q in out if t and (not only_liquid or q > 0)]

def fundamentus_tickers(only_liquid=False):
    """Lista de papéis (ordem por liquidez desc): Fundamentus direto -> API do app no Render
    (que lê o Fundamentus) -> snapshot do Status Invest (branch data). O Fundamentus pode bloquear o IP desta máquina."""
    errs = []
    for name, fn in (("Fundamentus", _fund_direct), ("API do app", _from_app), ("snapshot Status Invest", _from_statusinvest)):
        try:
            t = fn(only_liquid)
            if len(t) >= 100:
                print(f"  lista de papéis: {name} ({len(t)})", flush=True)
                return t
            errs.append(f"{name}: só {len(t)} papéis")
        except Exception as e:
            errs.append(f"{name}: {type(e).__name__}: {str(e)[:120]}")
        print(f"  lista de papéis: {errs[-1]} -> próxima opção", flush=True)
    raise RuntimeError("sem lista de papéis: " + " | ".join(errs))

def save(path, source, rows, extra=None):
    out = {"source": source, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "count": len(rows), "rows": rows}
    if extra: out.update(extra)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)

def text_of(s):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)

def crawl(tickers, url_fn, parse_fn, delay=1.0, log_every=50, max_fail_streak=25, backoff=20):
    """Busca sequencial ~1 req/s. Para se houver muitas falhas seguidas (bloqueio)."""
    s = requests.Session(); s.headers.update(UA)
    rows, fails, streak, codes = {}, 0, 0, {}
    for i, t in enumerate(tickers, 1):
        try:
            r = s.get(url_fn(t), timeout=40)
            if r.status_code in (403, 429):  # limite de taxa: espera e tenta 1x
                time.sleep(backoff); r = s.get(url_fn(t), timeout=40)
            codes[r.status_code] = codes.get(r.status_code, 0) + 1
            v = parse_fn(r.text) if r.status_code == 200 else None
        except requests.RequestException as e:
            codes[type(e).__name__] = codes.get(type(e).__name__, 0) + 1; v = None
        if v: rows[t] = v; streak = 0
        else:
            fails += 1; streak += 1
            if streak >= max_fail_streak and not rows:
                raise RuntimeError(f"bloqueado? {codes}")
        if i % log_every == 0: print(f"  {i}/{len(tickers)} ok={len(rows)} {codes}", flush=True)
        time.sleep(delay)
    return rows, codes
