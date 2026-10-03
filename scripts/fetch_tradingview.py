"""Snapshot TradingView (fallback caso o scanner bloqueie o Render). Uso: fetch_tradingview.py <dir_saida>"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import tradingview
from snaputil import save

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "data"
    ok = 0
    for cc in tradingview.COUNTRIES:
        try:
            rows = tradingview.fetch(cc)
            save(os.path.join(outdir, f"tradingview_{cc}.json"), "tradingview", rows, {"country": cc})
            print(f"TradingView {cc}: {len(rows)} papéis"); ok += 1
        except Exception as e:
            print(f"AVISO TradingView {cc}: {e}", file=sys.stderr)
        time.sleep(3)
    sys.exit(0 if ok else 1)
