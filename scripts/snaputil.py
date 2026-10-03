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

def fundamentus_tickers(only_liquid=False):
    """Lista de papéis do Fundamentus (ordem por liquidez desc)."""
    import pandas as pd
    r = requests.get("https://www.fundamentus.com.br/resultado.php", headers=UA, timeout=60)
    df = pd.read_html(io.StringIO(r.content.decode("latin-1")), decimal=",", thousands=".")[0]
    df["liq"] = pd.to_numeric(df["Liq.2meses"], errors="coerce").fillna(0)
    df = df.sort_values("liq", ascending=False)
    if only_liquid: df = df[df["liq"] > 0]
    return [str(t).strip().upper() for t in df["Papel"]]

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
