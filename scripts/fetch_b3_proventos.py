#!/usr/bin/env python3
"""Proventos em dinheiro (dividendos + JCP) por ação, oficial da B3 -> OUT/b3_proventos.json. Fonte única do dividendo por ação.
Por papel negociado (lista b3_listed.json do snapshot, classes 3/4/5/6/11): soma por ano da data-com dos últimos ANOS exercícios completos,
ajustada por desdobramento, grupamento e bonificação (eventos da própria B3), para comparar com a cotação de hoje.
Usado pelo Barato/Caro (Barsi: média do dividendo por ação ÷ taxa, valor_justo.FAIR). Roda na rotina (≈1 req/0,3 s);
refaz no máximo a cada REFAZ dias (os anos completos quase não mudam). Uso: fetch_b3_proventos.py OUT_DIR"""
import base64, json, os, re, sys, time
from datetime import date, datetime, timezone
import requests

API = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall"
UA = {"User-Agent": "Mozilla/5.0"}
ANOS = 5
REFAZ = 6.5 * 86400
CLS = {"ON": "3", "PN": "4", "PNA": "5", "PNB": "6", "PNC": "7", "PND": "8", "UNT": "11", "UNIT": "11"}


def call(name, payload):
    p = base64.b64encode(json.dumps(payload).encode()).decode()
    for i in range(3):
        try:
            r = requests.get(f"{API}/{name}/{p}", headers=UA, timeout=60)
            if r.status_code == 200: return r.json()
        except Exception:
            pass
        time.sleep(2 + 3 * i)
    return None


def num(s):
    try: return float(str(s).replace(".", "").replace(",", "."))
    except Exception: return None


def dmy(s):
    try: return datetime.strptime(s[:10], "%d/%m/%Y").date()
    except Exception: return None


def empresa(code, trading, y0, y1):
    """-> {classe: {ano: dps ajustado}}"""
    sup = call("GetListedSupplementCompany", {"issuingCompany": code, "language": "pt-br"}) or []
    ev = set()
    for s in (sup[0].get("stockDividends") or []) if sup else []:
        lab, f, d = (s.get("label") or "").upper(), num(s.get("factor")), dmy(s.get("lastDatePrior") or "")
        if not f or not d: continue
        if lab.startswith("DESDOBRAMENTO") or lab.startswith("BONIFICA"): ev.add((d, 1 + f / 100))
        elif lab.startswith("GRUPAMENTO"): ev.add((d, f))
    out, pg = {}, 1
    while True:
        d = call("GetListedCashDividends", {"language": "pt-br", "pageNumber": pg, "pageSize": 120, "tradingName": trading})
        if not d: break
        for x in d.get("results") or []:
            dc = dmy(x.get("lastDatePriorEx") or "")
            v, q = num(x.get("valueCash")), num(x.get("quotedPerShares")) or 1
            c = CLS.get((x.get("typeStock") or "").strip().upper())
            if not (dc and v and c) or not (y0 <= dc.year <= y1): continue
            if not re.search(r"DIVIDEND|JRS|JUROS|RENDIMENTO", (x.get("corporateAction") or "").upper()): continue
            m = 1.0
            for de, k in ev:
                if de >= dc: m *= k  # evento depois da data-com: ajusta o valor por ação ao número de ações de hoje
            out.setdefault(c, {}).setdefault(dc.year, 0.0)
            out[c][dc.year] += v / q / m
        if pg >= ((d.get("page") or {}).get("totalPages") or 1): break
        pg += 1; time.sleep(0.3)
    return out


def main(outd):
    path = os.path.join(outd, "b3_proventos.json")
    try:
        old = json.load(open(path))
        if time.time() - datetime.fromisoformat(old["fetched_at"]).timestamp() < REFAZ:
            print("Proventos B3: snapshot desta semana já existe"); return 0
    except Exception:
        pass
    try: listed = set(json.load(open(os.path.join(outd, "b3_listed.json")))["tickers"])
    except Exception: listed = set()
    roots = {t[:4] for t in listed if re.match(r"^[A-Z0-9]{4}(3|4|5|6|7|8|11)$", t)}
    comp, pg = {}, 1
    while True:
        d = call("GetInitialCompanies", {"language": "pt-br", "pageNumber": pg, "pageSize": 120})
        if not d: print("Proventos B3: lista de empresas falhou", file=sys.stderr); return 1
        for r in d.get("results") or []:
            c = r.get("issuingCompany")
            if c and (not roots or c in roots) and r.get("tradingName"): comp.setdefault(c, r["tradingName"].strip())
        if pg >= (d.get("page") or {}).get("totalPages", 1): break
        pg += 1; time.sleep(0.3)
    y1 = date.today().year - 1; y0 = y1 - ANOS + 1
    A, n = {}, 0
    for code, tr in sorted(comp.items()):
        try:
            res = empresa(code, tr, y0, y1)
        except Exception as e:
            print(f"  {code}: {e}", file=sys.stderr); continue
        for c, ys in res.items():
            t = code + c
            if listed and t not in listed: continue
            A[t] = {str(y): round(v, 6) for y, v in sorted(ys.items())}
        n += 1
        if n % 50 == 0: print(f"  {n}/{len(comp)} empresas", flush=True)
        time.sleep(0.3)
    if len(A) < 50: print(f"Proventos B3: só {len(A)} papéis, mantém o anterior", file=sys.stderr); return 1
    json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fonte": "B3 (proventos em dinheiro)",
               "anos": [y0, y1], "a": A}, open(path, "w"), separators=(",", ":"))
    print(f"Proventos B3: {len(A)} papéis de {n} empresas, {y0}–{y1}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
