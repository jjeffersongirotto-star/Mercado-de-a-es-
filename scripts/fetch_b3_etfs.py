#!/usr/bin/env python3
"""ETFs listados na B3 -> OUT/etfs.json (aba Mercado → ETFs, /api/etfs). Duas fases na rotina:
  lista  (antes do COTAHIST): lista oficial da B3 (fundos de índice, typeFund "ETF") com código, nome do fundo e tipo pelo índice
         do nome (TIPOS): ações do Brasil, ações de fora, renda fixa; cripto e fundos imobiliários (FII) ficam fora (FORA).
  dados  (depois do COTAHIST): preço, variação do dia, volume médio de 30 pregões, rendimento em 1–5 anos e proventos de 12 meses
         lidos dos históricos history4_etf/<TICKER>.json.gz que build_cotahist.py grava para os ETFs da lista (mesma base B3; pasta própria
         para não entrarem no "mercado" do Medo e Ganância nem nos modelos).
Taxa de administração: o detalhe do fundo da B3 não responde e o cadastro da CVM (registro_classe) não traz a taxa -> fica sem.
Uso: fetch_b3_etfs.py lista|dados OUT_DIR"""
import base64, gzip, json, os, re, sys, time, unicodedata
from datetime import datetime, timezone
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import universe  # noqa: E402  (mesma regra de ilíquido do site)

UA = {"User-Agent": "Mozilla/5.0"}
URL = "https://sistemaswebb3-listados.b3.com.br/fundsListedProxy/Search/GetListFunds/"
# tipo pelo nome do fundo (sem acento, maiúsculas); a ordem importa: o primeiro que casa vale
FORA = [("cripto", r"BITCOIN|CRIPTO|ETHEREUM|ETHER\b|BLOCKCHAIN|SOLANA|\bXRP\b|HASHDEX|WEB3|DEFI\b|NCI\b"),
        ("fii", r"IFIX|IMOBILIARI|FUNDOS? IMOB|REAL ESTATE|\bREIT")]
TIPOS = [("rf", r"RENDA FIXA|\bIMA[- ]?B|\bIMAB|\bIRF[- ]?M|\bIDKA|TESOURO|DEBENTURE|\bCDI\b|\bDI\b|INFLACAO|\bIPCA|PREFIXAD|TITULOS PUBLICOS|CREDITO PRIVADO|\bIDA\b|JUROS"),
         ("ext", r"S&P|SP ?500|NASDAQ|MSCI|\bEUA\b|ESTADOS UNIDOS|EUROPA|EUROPE|CHINA|ASIA|GLOBAL|DOW JONES|WORLD|\bACWI|EMERG|JAPAO|JAPAN|INDIA|ALEMANHA|INTERNACIONAL|\bUSA?\b|\bUS\b|HANG SENG|RUSSELL|FTSE|STOXX|NYSE|AMERICAN|TREASURY|\bOURO\b|GOLD|ESG GLOBAL|ARK|INNOVATION|SEMICONDUT|NIKKEI")]
TIPO_N = {"br": "Ações Brasil", "ext": "Ações de fora", "rf": "Renda fixa"}


def b64(o): return base64.b64encode(json.dumps(o).encode()).decode()
def sem_acento(s): return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()


def tipo(nome):
    n = sem_acento(nome)
    for k, rx in FORA + TIPOS:
        if re.search(rx, n): return k
    return "br"


def indice(nome):
    """Índice que o ETF acompanha = nome do fundo sem a forma jurídica (… FUNDO DE ÍNDICE / CLASSE DE ÍNDICE …)."""
    n = re.split(r"\s*[-–]?\s*(FUNDO DE [IÍ]NDICE|CLASSE DE [IÍ]NDICE|FUNDO DE INVESTIMENTO|RESPONSABILIDADE LIMITADA)", nome or "", flags=re.I)[0]
    return re.sub(r"\s+", " ", n).strip(" -–")


def lista(out):
    res, pg = [], 1
    while True:
        d = requests.get(URL + b64({"language": "pt-br", "typeFund": "ETF", "pageNumber": pg, "pageSize": 120}), headers=UA, timeout=60).json()
        res += d.get("results") or []
        if pg >= (d.get("page") or {}).get("totalPages", 1): break
        pg += 1; time.sleep(0.3)
    if len(res) < 30: print("ETFs: lista da B3 veio curta:", len(res), file=sys.stderr); return 1
    E, fora = {}, {}
    for r in res:
        ac = (r.get("acronym") or "").strip().upper(); nome = (r.get("fundName") or "").strip()
        if not re.fullmatch(r"[A-Z0-9]{4}", ac): continue
        k = tipo(nome)
        if k in ("cripto", "fii"): fora[ac + "11"] = k; continue
        E[ac + "11"] = {"n": r.get("tradingName") or ac, "f": nome, "i": indice(nome), "k": k}
    json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fonte": "B3 (fundos de índice listados)",
               "tipos": TIPO_N, "e": E, "fora": fora}, open(os.path.join(out, "etfs.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    cont = ", ".join(TIPO_N[k] + " " + str(sum(1 for x in E.values() if x["k"] == k)) for k in TIPO_N)
    print(f"ETFs: {len(E)} na lista ({cont}); fora: {len(fora)} (cripto/FII)")
    return 0


def dados(out):
    p = os.path.join(out, "etfs.json"); J = json.load(open(p)); E = J["e"]; ok = 0
    for t, x in E.items():
        f = os.path.join(out, "history4_etf", f"{t}.json.gz")
        if not os.path.exists(f): continue
        h = json.loads(gzip.decompress(open(f, "rb").read())); d = h.get("d") or {}
        ts, c, v = d.get("t") or [], d.get("c") or [], d.get("vol") or []
        if len(c) < 2: continue
        x["p"] = c[-1]; x["v"] = round((c[-1] / c[-2] - 1) * 100, 2) if c[-2] else None; x["u"] = datetime.fromtimestamp(ts[-1], timezone.utc).strftime("%Y-%m-%d")
        x["vm"] = round(sum(v[-30:]) / len(v[-30:])) if v else None  # volume médio diário de 30 pregões (R$)
        if universe.illiquid(x["vm"]): x["il"] = 1  # mesma regra das ações: some com "Só líquidos"
        dv = [b for a, b in (h.get("divs") or []) if a >= ts[-1] - 365 * 86400]
        x["dy"] = round(sum(dv) / c[-1] * 100, 2) if dv and c[-1] else 0.0  # proventos de 12 meses ÷ preço (%)
        for n in range(1, 6):  # rendimento só de preço em n anos (proventos à parte, em dy)
            alvo = ts[-1] - n * 365.25 * 86400; j = next((i for i, a in enumerate(ts) if a >= alvo), None)
            x[f"r{n}"] = round((c[-1] / c[j] - 1) * 100, 1) if j is not None and j > 0 and c[j] else None
        x["ini"] = datetime.fromtimestamp(ts[0], timezone.utc).strftime("%Y-%m-%d"); ok += 1
    J["dados_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(J, open(p, "w"), ensure_ascii=False, separators=(",", ":"))
    print(f"ETFs: preços de {ok} de {len(E)} (COTAHIST)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit((lista if sys.argv[1] == "lista" else dados)(sys.argv[2]))
