#!/usr/bin/env python3
"""Snapshot de histórico (Yahoo: mensal desde o início (range=max) + 5a diário, com dividendos) para o universo exibido + Ibovespa,
séries do BCB (CDI, IPCA, Poupança, Dólar), histórico das maiores ações de fora (history.FORA, renova 1×/semana, OUT_DIR/history5)
e perfis/descrições das empresas (Investidor10 'Sobre a empresa').
Uso: fetch_history.py OUT_DIR   (grava OUT_DIR/history/*.json.gz, OUT_DIR/history/bcb_*.json, OUT_DIR/profiles.json)
ONLY_PROFILES=1 / ONLY_HISTORY=1 limitam a etapa. DATA_JSON=arquivo local de /api/data (senão baixa do app)."""
import gzip, json, os, sys, time
from datetime import datetime, timezone
import requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import history, universe
from snaputil import APP_API

out = sys.argv[1]
os.makedirs(os.path.join(out, "history"), exist_ok=True); os.makedirs(os.path.join(out, "history3"), exist_ok=True)
if os.environ.get("DATA_JSON"):
    rows = json.load(open(os.environ["DATA_JSON"]))["rows"]
else:
    for _ in range(10):
        d = requests.get(APP_API, timeout=120).json()
        if d.get("rows"):
            break
        time.sleep(20)
    rows = d["rows"]
kept = universe.universe(rows)
tickers = [r["ticker"] for r in kept]
at = datetime.now(timezone.utc).strftime("%d/%m/%Y")
ok = fail = 0
if not os.environ.get("ONLY_PROFILES"):
    for t in ["IBOV"]:  # ações brasileiras: histórico oficial da B3 (build_cotahist.py); Yahoo só para o índice
        try:
            pay = {}
            for k in ("m", "d"):
                pay[k] = history.yahoo(t, k); pay[k]["at"] = at
                time.sleep(0.3)
            with open(os.path.join(out, "history3", t + ".json.gz"), "wb") as f:
                f.write(gzip.compress(json.dumps(pay, separators=(",", ":")).encode()))
            ok += 1
        except Exception as e:
            fail += 1; print("histórico", t, e, file=sys.stderr)
    for n in history.SGS:
        try:
            json.dump(history.bcb(n), open(os.path.join(out, "history", f"bcb_{n}.json"), "w"), separators=(",", ":"))
        except Exception as e:
            print("BCB", n, e, file=sys.stderr)
    try:
        json.dump(history.gold(), open(os.path.join(out, "history", "gold3.json"), "w"), separators=(",", ":"))
    except Exception as e:
        print("ouro", e, file=sys.stderr)
    print(f"histórico: {ok} ok, {fail} falhas")
    # Ações de fora: as maiores de cada país (history.FORA) + índice do país, ouro e câmbio -> history5 (gráficos e Comparar: history.yget).
    # Renova uma vez por semana; nas outras rotinas não baixa nada (o site busca os dias novos ao vivo).
    import tradingview
    os.makedirs(os.path.join(out, "history5"), exist_ok=True)
    syms = {"GC=F"} | {f"USD{c[2]}=X" for c in tradingview.COUNTRIES.values() if c[2] != "USD"}
    for c, n in history.FORA.items():
        syms.add(tradingview.YAHOO[c][1])
        try:
            rs = [r for r in requests.get(APP_API, params={"country": c}, timeout=180).json()["rows"] if not r.get("il")]
            rs.sort(key=lambda r: -((r.get("v") or {}).get("valmerc") or 0))
            syms |= {history.ysym(r["ticker"], c) for r in rs[:n]}
        except Exception as e:
            print("fora: lista", c, e, file=sys.stderr)
    fo = ff = 0
    for sym in sorted(syms):
        p = os.path.join(out, "history5", history.fname(sym) + ".json.gz")
        try:
            old = json.loads(gzip.decompress(open(p, "rb").read())) if os.path.exists(p) else None
            new = history.copy_update(old, sym)
            if new is not old:
                with open(p, "wb") as f: f.write(gzip.compress(json.dumps(new, separators=(",", ":")).encode()))
                time.sleep(0.3)
            fo += 1
        except Exception as e:
            ff += 1; print("fora", sym, e, file=sys.stderr)
    print(f"histórico de fora: {fo} ok, {ff} falhas")
if not os.environ.get("ONLY_HISTORY"):
    import html as H, re
    prof = {}
    UAH = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
    for t in tickers:   # descrição "Sobre a empresa" do Investidor10 (português)
        try:
            h = requests.get(f"https://investidor10.com.br/acoes/{t.lower()}/", headers=UAH, timeout=30).text
            am = re.search(r'"articleBody":\s*"((?:[^"\\]|\\.)*)"', h)
            ab = json.loads('"' + am.group(1) + '"').strip() if am else ""
            body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S)
            txt = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", body)))
            pos = txt.find(ab[:40]) if ab else -1
            d = txt[pos:pos + 1200].strip() if pos >= 0 else ab
            m = re.search(r"atua no setor e subsetor de (.+?)\s*$", ab)
            if d:
                prof[t] = {"d": d, "s": m.group(1).strip()[:80] if m else None, "i": None}
        except Exception as e:
            print("perfil", t, e, file=sys.stderr)
        time.sleep(1.0)
    json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(), "profiles": prof}, open(os.path.join(out, "profiles.json"), "w"), ensure_ascii=False)
    print(f"perfis: {len(prof)}")
