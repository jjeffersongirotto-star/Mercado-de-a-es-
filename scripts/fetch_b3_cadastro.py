#!/usr/bin/env python3
"""Cadastro oficial de empresas listadas na B3 (nome, nome de pregão, segmento) → OUT/b3_cad.json {CODE4: [nome, segmento]}.
Usado para preencher nome/setor de papéis sem cadastro nas outras fontes."""
import base64, json, os, sys, time, requests
OUT = sys.argv[1]; res, pg = {}, 1
while True:
    p = base64.b64encode(json.dumps({"language": "pt-br", "pageNumber": pg, "pageSize": 120}).encode()).decode()
    d = requests.get(f"https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetInitialCompanies/{p}", headers={"User-Agent": "Mozilla/5.0"}, timeout=60).json()
    for r in d.get("results") or []:
        if r.get("issuingCompany"): res.setdefault(r["issuingCompany"], [r.get("companyName") or r.get("tradingName"), r.get("segment")])
    if pg >= (d.get("page") or {}).get("totalPages", 1): break
    pg += 1; time.sleep(0.3)
json.dump({"source": "B3 (empresas listadas)", "c": res}, open(os.path.join(OUT, "b3_cad.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print("Cadastro B3:", len(res), "empresas")
