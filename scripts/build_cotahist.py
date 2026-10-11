#!/usr/bin/env python3
"""Histórico diário oficial da B3 (COTAHIST) para as ações brasileiras mantidas.
- Lê os arquivos anuais COTAHIST_A{ano}.ZIP (desde 07/1994, Plano Real; antes há trocas de moeda) e os diários
  COTAHIST_D{ddmmaaaa}.ZIP dos dias que ainda não estão no anual.
- Junta as negociações pelo ISIN (pega o histórico mesmo após troca de código), mercado à vista (TPMERC 010), lote padrão (BDI 02).
- Preço por ação = PREULT / FATCOT. Ajuste por desdobramento/grupamento/bonificação com os eventos oficiais da B3
  (GetListedSupplementCompany → stockDividends): preços antes da data-com são divididos pelo fator acumulado.
- Proventos: B3 (últimos ~12 meses, com tipo: dividendo/JCP/rendimento) + Yahoo para datas anteriores (valores já ajustados).
Uso: build_cotahist.py DIR_ZIPS OUT_DIR   (grava OUT_DIR/history4/{TICKER}.json.gz)  DATA_JSON = /api/data salvo."""
import base64, calendar, gzip, io, json, os, sys, time, zipfile
from datetime import datetime, timezone, timedelta
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import universe

ZD, OUT = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(OUT, "history4"), exist_ok=True)
rows = json.load(open(os.environ["DATA_JSON"]))["rows"] if os.environ.get("DATA_JSON") else \
    requests.get("https://mercado-de-acoes.onrender.com/api/data", timeout=120).json()["rows"]
kept, _, _ = universe.universe(rows)
TICK = [r["ticker"] for r in kept]
if os.environ.get("COTA_ONLY"): TICK = [t for t in TICK if t in os.environ["COTA_ONLY"].split(",")]
UA = {"User-Agent": "Mozilla/5.0"}

def lines(path):
    with zipfile.ZipFile(path) as z:
        with z.open(z.namelist()[0]) as f:
            for raw in io.TextIOWrapper(f, encoding="latin1"):
                if raw.startswith("01"):
                    yield raw

def rec(l):
    return {"d": l[2:10], "bdi": l[10:12], "cod": l[12:24].strip(), "tp": l[24:27], "c": int(l[108:121]) / 100,
            "o": int(l[56:69]) / 100, "q": int(l[152:170]), "vol": int(l[170:188]) / 100, "fat": int(l[210:217]) or 1, "isin": l[230:242]}

years = sorted(int(f[10:14]) for f in os.listdir(ZD) if f.startswith("COTAHIST_A"))
# ISIN atual de cada ticker (arquivo mais recente)
isin, seen = {}, {}
for l in lines(os.path.join(ZD, f"COTAHIST_A{years[-1]}.ZIP")):
    r = rec(l)
    if r["tp"] == "010":
        seen[r["cod"]] = max(seen.get(r["cod"], ""), r["d"])
        if r["cod"] in TICK:
            isin[r["cod"]] = r["isin"]
# Lista oficial de papéis negociados no mercado à vista (últimos 90 dias): fonte B3 tem prioridade —
# ticker ausente aqui é tratado como não negociado/deslistado e sai do universo.
lim = (datetime.strptime(max(seen.values()), "%Y%m%d") - timedelta(days=90)).strftime("%Y%m%d")
json.dump({"date": max(seen.values()), "source": "B3 COTAHIST", "tickers": sorted(k for k, v in seen.items() if v >= lim)},
          open(os.path.join(OUT, "b3_listed.json"), "w"), separators=(",", ":"))
want = {v: k for k, v in isin.items()}
print("tickers", len(TICK), "com ISIN no arquivo atual", len(isin), file=sys.stderr)
data = {t: {} for t in isin}
last_day = "00000000"
for y in years:
    if y < 1994:
        continue
    for l in lines(os.path.join(ZD, f"COTAHIST_A{y}.ZIP")):
        if l[24:27] != "010" or l[10:12] in ("96", "10", "14", "22"):  # à vista: lote padrão e também papéis em recuperação judicial/situação especial (BDI 08 etc.); fora fracionário e direitos
            continue
        t = want.get(l[230:242]) or (l[12:24].strip() if l[12:24].strip() in data else None)  # ISIN atual ou mesmo código (ISIN muda em grupamentos)
        if not t:
            continue
        r = rec(l)
        if r["d"] < "19940701":
            continue
        prev = data[t].get(r["d"])
        if prev is None or r["vol"] > prev[2]:
            data[t][r["d"]] = (r["c"] / r["fat"], r["q"], r["vol"], r["isin"])
        last_day = max(last_day, r["d"])
# dias depois do arquivo anual (arquivos diários)
d0 = datetime.strptime(last_day, "%Y%m%d") + timedelta(days=1)
while d0.date() <= datetime.now().date():
    if d0.weekday() < 5:
        u = f"https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D{d0:%d%m%Y}.ZIP"
        try:
            rr = requests.get(u, headers=UA, timeout=60)
            if rr.status_code == 200 and rr.content[:2] == b"PK":
                p = os.path.join(ZD, f"COTAHIST_D{d0:%d%m%Y}.ZIP"); open(p, "wb").write(rr.content)
                for l in lines(p):
                    tk = want.get(l[230:242]) or (l[12:24].strip() if l[12:24].strip() in data else None)
                    if l[24:27] == "010" and l[10:12] not in ("96", "10", "14", "22") and tk:
                        r = rec(l); data[tk][r["d"]] = (r["c"] / r["fat"], r["q"], r["vol"], r["isin"])
        except Exception as e:
            print("diário", d0.date(), e, file=sys.stderr)
    d0 += timedelta(days=1)

def b3_events(code4):
    p = base64.b64encode(json.dumps({"issuingCompany": code4, "language": "pt-br"}).encode()).decode()
    for _ in range(3):
        try:
            r = requests.get(f"https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/{p}", headers=UA, timeout=30)
            j = r.json(); return j[0] if isinstance(j, list) and j else {}
        except Exception:
            time.sleep(2)
    return {}

def num(s):
    return float(str(s).replace(".", "").replace(",", "."))

def ts_of(d):  # 13:00 UTC = fechamento aproximado do pregão (mesma convenção dos dados anteriores)
    return int(datetime.strptime(d, "%Y%m%d").replace(hour=13, tzinfo=timezone.utc).timestamp())

ok = 0
evcache = {}
for t, days in data.items():
    if not days:
        continue
    if os.environ.get("SKIP_NEWER") and os.path.exists(os.path.join(OUT, "history4", t + ".json.gz")) and os.path.getmtime(os.path.join(OUT, "history4", t + ".json.gz")) > float(os.environ["SKIP_NEWER"]):
        ok += 1; continue
    code4 = t[:4]
    ev = evcache.get(code4) or evcache.setdefault(code4, b3_events(code4)); time.sleep(0.4)
    keys = sorted(days)
    my = days[keys[-1]][3]; isin[t] = my  # ISIN do último pregão (após troca de ISIN por grupamento)
    isins = {v[3] for v in days.values()}
    import math
    def plaus(dc, m):  # confere o evento com o salto do preço bruto em torno da data-com
        pre = [d for d in keys if d <= dc]; pos = [d for d in keys if d > dc]
        if abs(math.log(m)) < 0.2: return True  # bonificação pequena: salto se confunde com a oscilação do dia
        if not pre or not pos: return False
        r = days[pre[-1]][0] / days[pos[0]][0]
        return abs(math.log(r / m)) < abs(math.log(m)) / 2
    try:
        q = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}.SA", params={"period1": 0, "period2": int(time.time()) + 86400, "interval": "1d", "events": "div,split"},
                         headers=UA, timeout=(6, 25)).json()["chart"]["result"][0]
        yev = q.get("events") or {}
    except Exception as e:
        print("Yahoo eventos", t, e, file=sys.stderr); yev = {}
    time.sleep(0.3)
    # Eventos: B3 primeiro (prioridade); Yahoo só completa datas que a B3 não lista (±7 dias). Só desdobramento/grupamento/bonificação.
    bydc = {}
    for x in ev.get("stockDividends") or []:
        lab = (x.get("label") or "").upper()
        if x.get("isinCode") not in isins or not lab.startswith(("DESD", "GRUP", "BONIF")):
            continue
        f = num(x["factor"])
        mult = f if lab.startswith("GRUP") else 1 + f / 100  # grupamento: fator direto; desdobramento/bonificação: +f%
        dc = datetime.strptime(x["lastDatePrior"], "%d/%m/%Y").strftime("%Y%m%d")
        if mult > 0:
            bydc.setdefault(dc, {})[(lab[:4], mult)] = lab  # repetidos contam uma vez; eventos do mesmo dia se combinam
    spl = []
    for dc, evs in sorted(bydc.items()):
        mult = math.prod(m for _, m in evs); lab = "+".join(sorted(set(evs.values())))
        if abs(math.log(mult)) < 1e-9: continue
        if plaus(dc, mult): spl.append((dc, mult, lab))
        else: print("evento B3 descartado (preço não confirma)", t, dc, lab, mult, file=sys.stderr)
    for k_, v in (yev.get("splits") or {}).items():
        m = float(v["numerator"]) / float(v["denominator"])
        ex = datetime.utcfromtimestamp(int(k_))
        dc = (ex - timedelta(days=1)).strftime("%Y%m%d")
        if any(abs((datetime.strptime(e, "%Y%m%d") - ex).days) <= 7 for e, _, _ in spl):
            continue
        pre = [d for d in keys if d < ex.strftime("%Y%m%d")]
        if pre and m > 0 and plaus(pre[-1], m):
            spl.append((pre[-1], m, "EVENTO (Yahoo)"))
    # Troca de ISIN sem evento listado: o salto do preço bruto na troca é o fator (arredondado a uma proporção usual)
    NICE = [1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15, 16, 20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200, 250, 300, 400, 500, 1000]
    for a, b in zip(keys, keys[1:]):
        if days[a][3] == days[b][3]: continue
        if any(abs((datetime.strptime(e, "%Y%m%d") - datetime.strptime(a, "%Y%m%d")).days) <= 7 for e, _, _ in spl): continue
        r = days[a][0] / days[b][0]
        if abs(math.log(r)) < math.log(1.5): continue
        n = min(NICE, key=lambda x: abs(math.log(max(r, 1 / r) / x)))
        if abs(math.log(max(r, 1 / r) / n)) > 0.25: continue
        spl.append((a, n if r > 1 else 1 / n, "TROCA DE ISIN")); spl.sort()
    adj = []
    for d in keys:
        k = 1.0
        for dc, m, _ in spl:
            if d <= dc:
                k *= m
        adj.append(round(days[d][0] / k, 4))
    # proventos: B3 (recentes, ajustados por eventos posteriores) + Yahoo (anteriores)
    # conferência: salto diário > 50% sem evento correspondente
    flags = [(keys[i], round(adj[i] / adj[i - 1], 3)) for i in range(1, len(adj)) if adj[i - 1] > 0 and adj[i] > 0 and abs(math.log(adj[i] / adj[i - 1])) > math.log(1.5)]
    if flags: print("SALTO>50% sem evento", t, flags[-5:], file=sys.stderr)
    divs, b3min = [], None
    for x in ev.get("cashDividends") or []:
        if x.get("isinCode") not in isins:
            continue
        dc = datetime.strptime(x["lastDatePrior"], "%d/%m/%Y").strftime("%Y%m%d")
        k = 1.0
        for e, m, _ in spl:
            if dc <= e:
                k *= m
        divs.append([ts_of(dc), round(num(x["rate"]) / k, 8), x.get("label") or "provento"])
        b3min = dc if b3min is None or dc < b3min else b3min
    for k_, v in (yev.get("dividends") or {}).items():
        dd = datetime.fromtimestamp(int(k_), timezone.utc).strftime("%Y%m%d")
        if b3min is None or dd < b3min:
            divs.append([int(k_), round(float(v["amount"]), 8), "provento (Yahoo)"])
    divs.sort()
    tt = [ts_of(d) for d in keys]
    mm = {}
    for a, c in zip(tt, adj):
        k_ = time.strftime("%Y-%m", time.gmtime(a)); mm[k_] = (mm[k_][0], c) if k_ in mm else (a, c)
    mk = sorted(mm)
    at = datetime.now().strftime("%d/%m/%Y")
    src = "B3 (COTAHIST)"
    pay = {"d": {"t": tt, "c": adj, "vol": [round(days[d][2]) for d in keys], "div": [[a, b] for a, b, _ in divs], "source": src, "at": at},
           "m": {"t": [mm[k_][0] for k_ in mk], "c": [mm[k_][1] for k_ in mk], "div": [[a, b] for a, b, _ in divs], "source": src, "at": at},
           "divs": divs, "splits": [[ts_of(dc), m, lab] for dc, m, lab in spl], "isin": my,
           "flags": [[ts_of(d), r] for d, r in flags]}
    with open(os.path.join(OUT, "history4", t + ".json.gz"), "wb") as f:
        f.write(gzip.compress(json.dumps(pay, separators=(",", ":")).encode()))
    ok += 1
print(f"COTAHIST: {ok} tickers gravados; último pregão {max(max(v) for v in data.values() if v)}")
