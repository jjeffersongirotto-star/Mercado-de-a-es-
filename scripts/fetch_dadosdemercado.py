"""Snapshot Dados de Mercado (indicadores TTM, EBIT padrão e ajustado). Uso: fetch_dadosdemercado.py <dir_saida>"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from snaputil import br_num, crawl, save, fundamentus_tickers, text_of

LAB = {"P/L": "pl", "P/VP": "pvp", "P/EBIT": "pebit", "P/EBIT *": "pebit_adj", "PSR": "psr", "P/Ativos": "pativo",
       "LPA": "lpa", "VPA": "vpa", "Margem bruta": "mbruta", "Margem líquida": "mliq", "Margem EBIT": "mebit",
       "Margem EBIT *": "mebit_adj", "ROE": "roe", "ROIC": "roic", "ROIC *": "roic_adj", "Liquidez corrente": "liqcorr"}

def parse(s):
    out = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
        if len(tds) < 2: continue
        lab = text_of(tds[0]).strip()
        lab = re.sub(r"^mi ", "", lab)
        k = LAB.get(lab)
        if k and k not in out:
            v = br_num(text_of(tds[1]))
            if v is not None: out[k] = v
    if out and "pebit" not in out:  # financeiras (bancos/seguradoras): DRE diferente, só o que é comparável
        out = {k: v for k, v in out.items() if k in ("pl", "pvp", "lpa", "vpa", "roe")}
    return out or None

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "data"
    tick = fundamentus_tickers(only_liquid=True)
    if len(sys.argv) > 2: tick = tick[:int(sys.argv[2])]
    # uma página por empresa (dados iguais entre classes ON/PN); reaproveita para as demais classes
    first = {}
    for t in tick: first.setdefault(t[:4], t)
    print(f"Dados de Mercado: {len(first)} empresas ({len(tick)} tickers)", flush=True)
    rows, codes = crawl(list(first.values()), lambda t: f"https://www.dadosdemercado.com.br/acoes/{t.lower()}", parse, delay=2.5, backoff=45)
    if len(rows) < 30: sys.exit(f"poucos dados ({len(rows)}) {codes}")
    # P/L, P/VP, P/EBIT, PSR, P/Ativos dependem do preço da classe: só mantém os por-empresa nas outras classes
    PER_CO = {"mbruta", "mliq", "mebit", "mebit_adj", "roe", "roic", "roic_adj", "liqcorr", "lpa", "vpa"}
    allrows = {}
    for t in tick:
        src = rows.get(first[t[:4]])
        if not src: continue
        allrows[t] = dict(src) if first[t[:4]] == t else {k: v for k, v in src.items() if k in PER_CO}
        if first[t[:4]] != t and src.get("pebit") and src.get("pebit_adj"):
            allrows[t]["_ebit_ratio"] = src["pebit_adj"] / src["pebit"]  # ebit_padrão/ebit_ajustado
        elif src.get("pebit") and src.get("pebit_adj"):
            allrows[t]["_ebit_ratio"] = src["pebit_adj"] / src["pebit"]
    save(os.path.join(outdir, "dadosdemercado.json"), "dadosdemercado", allrows, {"http": {str(k): v for k, v in codes.items()}})
    print(f"Dados de Mercado: {len(allrows)} tickers salvos {codes}")
