#!/usr/bin/env python3
"""Dados públicos da B3 (Boletim Diário, arquivos.b3.com.br/bdi): aluguel de ações e fluxo por tipo de investidor.
OUT/b3_btb.json  : {date, t: {TICKER: [saldo_em_aberto_qtd, taxa_doador_%aa, taxa_tomador_%aa, contratos, qtd_registrada_no_dia]}}
OUT/b3_flow.json : {days: {AAAA-MM-DD: {categoria: [compras_mil, vendas_mil, saldo_dia_mil]}}} — a B3 publica o acumulado do mês;
                   o saldo do dia é a diferença entre dias consecutivos do mesmo mês (a B3 guarda só ~21 pregões: o histórico é acumulado aqui)."""
import json, os, sys, time
from datetime import date, timedelta
import requests
OUT = sys.argv[1]
RAW = os.environ.get("SNAPSHOT_RAW_BASE", "https://raw.githubusercontent.com/jjeffersongirotto-star/Mercado-de-a-es-/data/data")
UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

def table(name, d, take=1000):
    out, pg = [], 1
    while True:
        for _ in range(3):
            try:
                t = requests.post(f"https://arquivos.b3.com.br/bdi/table/{name}/{d}/{d}/{pg}/{take}", data="{}", headers=UA, timeout=60).json()["table"]; break
            except Exception:
                time.sleep(3)
        else:
            return out
        out += t.get("values") or []
        if pg >= (t.get("pageCount") or 1): return out
        pg += 1; time.sleep(0.3)

days = [date.today() - timedelta(days=i) for i in range(1, 35)]
days = [d.isoformat() for d in days if d.weekday() < 5]
# Aluguel: último pregão publicado
btb = None
for d in days[:6]:
    bal = table("BTBLoanBalance", d)
    if bal:
        res = {}
        for v in bal:
            t = v[2]; r = res.setdefault(t, [0, None, None, 0, 0, 0.0])
            r[3] += v[6] or 0; r[4] += v[7] or 0
            if v[7]:  # taxas médias ponderadas pela quantidade registrada no dia
                r[5] += v[7]; r[1] = ((r[1] or 0) * (r[5] - v[7]) + v[9] * v[7]) / r[5]; r[2] = ((r[2] or 0) * (r[5] - v[7]) + v[12] * v[7]) / r[5]
            elif r[1] is None:
                r[1], r[2] = v[9], v[12]
        for v in table("BTBLendingOpenPosition", d):
            if v[2] in res: res[v[2]][0] += v[7] or 0
            else: res[v[2]] = [v[7] or 0, None, None, 0, 0, 0.0]
        btb = {"date": d, "source": "B3 BDI (Empréstimos registrados + Posições em aberto)",
               "t": {k: [r[0], None if r[1] is None else round(r[1], 4), None if r[2] is None else round(r[2], 4), r[3], r[4]] for k, r in res.items() if k[-1:].isdigit()}}
        break
if btb:
    json.dump(btb, open(os.path.join(OUT, "b3_btb.json"), "w"), separators=(",", ":"))
    print("Aluguel B3:", btb["date"], len(btb["t"]), "papéis")
# Fluxo por investidor
try: flow = requests.get(f"{RAW}/b3_flow.json", timeout=30).json()
except Exception: flow = {"days": {}}
mtd = flow.get("mtd", {})
for d in sorted(days):
    if d in mtd: continue
    v = table("SharesInvesVolum", d, 20)
    if v: mtd[d] = {x[0]: [x[1], x[3]] for x in v if x and x[0]}
    time.sleep(0.3)
D = {}
ks = sorted(mtd)
# Acumulado do mês (a B3 publica com ~2 pregões de defasagem): o saldo do dia é a diferença para a publicação anterior;
# quando o acumulado cai, começou um mês novo e o valor publicado é o próprio dia.
for i, d in enumerate(ks):
    if i == 0: continue
    p0 = mtd[ks[i - 1]]; cur = mtd[d]
    reset = sum(v[0] for v in cur.values()) < sum(v[0] for v in p0.values())
    D[d] = {}
    for c, (bb, ss) in cur.items():
        pb, ps = (0, 0) if reset or c not in p0 else p0[c]
        D[d][c] = [round(bb - pb), round(ss - ps), round((bb - pb) - (ss - ps))]
flow = {"source": "B3 BDI · Participação dos investidores (R$ mil)", "mtd": mtd, "days": D, "last": ks[-1] if ks else None}
json.dump(flow, open(os.path.join(OUT, "b3_flow.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print("Fluxo B3:", len(D), "pregões, último", flow["last"])
