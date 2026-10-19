#!/usr/bin/env python3
"""ETFs listados na B3 (ações do Brasil, ações de fora e renda fixa; cripto e FIIs ficam fora) -> OUT/etfs.json.
Fase de teste: grava também OUT/etfs_probe.json com o que cada fonte respondeu (a B3 e a CVM são bloqueadas na máquina de
desenvolvimento; a rotina do GitHub alcança): lista de fundos da B3, detalhe de um ETF, linhas do COTAHIST e cadastro de fundos da CVM.
Uso: fetch_b3_etfs.py OUT_DIR [DIR_COTAHIST]"""
import base64, csv, io, json, os, sys, zipfile
import requests

OUT = sys.argv[1]; ZD = sys.argv[2] if len(sys.argv) > 2 else None
UA = {"User-Agent": "Mozilla/5.0"}
B3 = "https://sistemaswebb3-listados.b3.com.br"
AMOSTRA = ("BOVA11", "IVVB11", "SMAL11", "DIVO11", "IMAB11", "FIXA11", "B5P211", "NASD11", "HASH11", "XFIX11")
probe = {}


def b64(o): return base64.b64encode(json.dumps(o).encode()).decode()


def get(url, n=4000):
    try:
        r = requests.get(url, headers=UA, timeout=60)
        return {"status": r.status_code, "body": r.text[:n]}
    except Exception as e:
        return {"erro": f"{type(e).__name__}: {e}"[:300]}


# 1) B3: lista de fundos listados (ETF = typeFund 20 em diversos serviços; testa caminhos e tipos)
for path in ("fundsProxy/fundsCall/GetListedFundsSIG", "fundsProxy/fundsCall/GetListFunds", "fundsListedProxy/Search/GetListFunds"):
    for tf in (20, 21, 22, 7):
        q = {"language": "pt-br", "typeFund": tf, "pageNumber": 1, "pageSize": 20, "keyword": ""}
        probe[f"lista {path} tipo {tf}"] = get(f"{B3}/{path}/{b64(q)}", 3000)
for path in ("fundsProxy/fundsCall/GetDetailFundSIG", "fundsProxy/fundsCall/GetDetailFund"):
    for tf in (20, 21):
        q = {"language": "pt-br", "typeFund": tf, "identifierFund": "BOVA"}
        probe[f"detalhe {path} tipo {tf} BOVA"] = get(f"{B3}/{path}/{b64(q)}", 6000)

# 2) COTAHIST: como os ETFs aparecem (BDI, especificação, nome) no arquivo do ano mais recente
if ZD and os.path.isdir(ZD):
    anos = sorted(f for f in os.listdir(ZD) if f.startswith("COTAHIST_A"))
    if anos:
        vis, bdi = {}, {}
        with zipfile.ZipFile(os.path.join(ZD, anos[-1])) as z, z.open(z.namelist()[0]) as f:
            for raw in io.TextIOWrapper(f, encoding="latin1"):
                if not raw.startswith("01") or raw[24:27] != "010": continue
                cod = raw[12:24].strip(); b = raw[10:12]; esp = raw[39:49].strip()
                if cod.endswith("11"): bdi.setdefault(f"{b} {esp}", set()).add(cod)
                if cod in AMOSTRA: vis[cod] = {"bdi": b, "especi": esp, "nome": raw[27:39].strip(), "isin": raw[230:242]}
        probe["cotahist amostra"] = vis
        probe["cotahist BDI+especificação dos códigos terminados em 11"] = {k: [len(v)] + sorted(v)[:15] for k, v in sorted(bdi.items())}

# 3) CVM: cadastro de fundos (taxa de administração); ETF = fundo de índice
for u in ("https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv", "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"):
    try:
        r = requests.get(u, headers=UA, timeout=180)
        info = {"status": r.status_code, "bytes": len(r.content)}
        if r.status_code == 200:
            if u.endswith(".zip"):
                z = zipfile.ZipFile(io.BytesIO(r.content)); info["arquivos"] = z.namelist()
                for nm in z.namelist():
                    t = z.read(nm).decode("latin1"); L = t.splitlines()
                    info[nm] = {"cabecalho": L[0][:800], "etf": [l[:600] for l in L if "NDICE" in l.upper() and ("BOVA" in l.upper() or "ISHARES" in l.upper())][:5], "linhas": len(L)}
            else:
                t = r.content.decode("latin1"); L = t.splitlines()
                info["cabecalho"] = L[0][:800]; info["linhas"] = len(L)
                info["etf"] = [l[:600] for l in L if "ISHARES" in l.upper()][:8]
                info["tipos"] = sorted({row.get("TP_FUNDO") for row in csv.DictReader(io.StringIO(t), delimiter=";")} - {None})[:30]
        probe[f"cvm {u.rsplit('/', 1)[1]}"] = info
    except Exception as e:
        probe[f"cvm {u.rsplit('/', 1)[1]}"] = {"erro": f"{type(e).__name__}: {e}"[:300]}

json.dump(probe, open(os.path.join(OUT, "etfs_probe.json"), "w"), ensure_ascii=False, indent=1, default=list)
print("ETFs: teste gravado em etfs_probe.json;", ", ".join(f"{k}: {v.get('status', v.get('erro', '?')) if isinstance(v, dict) else '...'}" for k, v in probe.items())[:3000])
