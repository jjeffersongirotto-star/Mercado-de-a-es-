#!/usr/bin/env python3
"""Snapshot de histórico (Yahoo: 20a mensal + 5a diário, com dividendos) para o universo exibido + Ibovespa,
séries do BCB (CDI, IPCA, Poupança, Dólar) e perfis/descrições das empresas (brapi summaryProfile).
Uso: fetch_history.py OUT_DIR   (grava OUT_DIR/history/*.json.gz, OUT_DIR/history/bcb_*.json, OUT_DIR/profiles.json)
ONLY_PROFILES=1 / ONLY_HISTORY=1 limitam a etapa. DATA_JSON=arquivo local de /api/data (senão baixa do app)."""
import gzip, json, os, sys, time
from datetime import datetime, timezone
import requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import history, universe

out = sys.argv[1]
os.makedirs(os.path.join(out, "history"), exist_ok=True)
if os.environ.get("DATA_JSON"):
    rows = json.load(open(os.environ["DATA_JSON"]))["rows"]
else:
    for _ in range(10):
        d = requests.get(os.environ.get("APP_URL", "https://mercado-de-acoes.onrender.com") + "/api/data", timeout=120).json()
        if d.get("rows"):
            break
        time.sleep(20)
    rows = d["rows"]
kept, _, _ = universe.universe(rows)
tickers = [r["ticker"] for r in kept]
at = datetime.now(timezone.utc).strftime("%d/%m/%Y")
ok = fail = 0
if not os.environ.get("ONLY_PROFILES"):
    for t in tickers + ["IBOV"]:
        try:
            pay = {}
            for k in ("m", "d"):
                pay[k] = history.yahoo(t, k); pay[k]["at"] = at
                time.sleep(0.3)
            with open(os.path.join(out, "history", t + ".json.gz"), "wb") as f:
                f.write(gzip.compress(json.dumps(pay, separators=(",", ":")).encode()))
            ok += 1
        except Exception as e:
            fail += 1; print("histórico", t, e, file=sys.stderr)
    for n in history.SGS:
        try:
            json.dump(history.bcb(n), open(os.path.join(out, "history", f"bcb_{n}.json"), "w"), separators=(",", ":"))
        except Exception as e:
            print("BCB", n, e, file=sys.stderr)
    print(f"histórico: {ok} ok, {fail} falhas")
if not os.environ.get("ONLY_HISTORY"):
    prof = {}
    for t in tickers:
        try:
            r = requests.get(f"https://brapi.dev/api/quote/{t}", params={"modules": "summaryProfile"}, timeout=30)
            p = (r.json().get("results") or [{}])[0].get("summaryProfile") or {}
            if p:
                prof[t] = {"d": (p.get("longBusinessSummary") or "")[:1500], "s": p.get("sectorDisp") or p.get("sector"), "i": p.get("industryDisp") or p.get("industry")}
        except Exception as e:
            print("perfil", t, e, file=sys.stderr)
        time.sleep(0.4)
    json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(), "profiles": prof}, open(os.path.join(out, "profiles.json"), "w"), ensure_ascii=False)
    print(f"perfis: {len(prof)}")
