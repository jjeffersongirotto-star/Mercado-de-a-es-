"""Snapshot Investidor10 (indicadores por ticker, ~1 req/s). Uso: fetch_investidor10.py <dir_saida>"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from snaputil import br_num, text_of, crawl, save, fundamentus_tickers

LAB = {"pl": "P/ L", "pvp": "P/ VP", "psr": "P/ Receita (PSR)", "evebitda": "EV/ Ebitda", "evebit": "EV/ Ebit",
       "pebit": "P/ Ebit", "pativo": "P/ Ativo", "lpa": "LPA", "vpa": "VPA", "mbruta": "Margem Bruta",
       "mebit": "Margem Ebit", "mliq": "Margem Líquida", "roe": "ROE", "roa": "ROA", "roic": "ROIC",
       "dy": "Dividend Yield", "liqcorr": "Liquidez Corrente", "dlebit": "Divida Liquida/ Ebit",
       "dlpl": "Divida Liquida/ Patrimônio", "cresc5a": "CAGR Receitas 5 anos", "lucro5a": "CAGR Lucros 5 anos"}
NUM = r"(-?[\d\.]*\d(?:,\d+)?%?|-)"

def parse(s):
    t = text_of(s)
    i = t.find("Indicadores Fundamentalistas")
    if i < 0: return None
    t = t[i:i + 7000] + " "
    out = {}
    for k, l in LAB.items():
        m = re.search(r"(?<![\w/])" + re.escape(l) + r" " + NUM + r" ", t)
        if m:
            v = br_num(m.group(1))
            if v is not None: out[k] = v
    return out or None

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "data"
    tick = fundamentus_tickers()
    if len(sys.argv) > 2: tick = tick[:int(sys.argv[2])]
    print(f"Investidor10: {len(tick)} tickers", flush=True)
    rows, codes = crawl(tick, lambda t: f"https://investidor10.com.br/acoes/{t.lower()}/", parse, delay=1.0)
    if len(rows) < 50: sys.exit(f"poucos dados ({len(rows)}) {codes}")
    save(os.path.join(outdir, "investidor10.json"), "investidor10", rows, {"http": {str(k): v for k, v in codes.items()}})
    print(f"Investidor10: {len(rows)} tickers salvos {codes}")
