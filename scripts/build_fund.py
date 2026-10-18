#!/usr/bin/env python3
"""Fundamentos anuais de cada empresa desde 2009 (DFP da CVM) -> OUT/fund.json, para os modelos da Previsão (scripts/build_modelos.py).
Por ticker negociado hoje: receita (3.01), lucro líquido (3.11.01 ou 3.11), patrimônio líquido (2.03) e, nas não financeiras,
dívida líquida (build_cvm.divida_liquida) e EBITDA (EBIT 3.05 + depreciação/amortização da DFC, build_cvm.da_flows) de cada exercício.
O exercício do ano Y só é usado pelos modelos a partir de maio de Y+1 (prazo de publicação), para nunca "ver o futuro".
Os arquivos da CVM mudam pouco: refaz no máximo uma vez por semana. Uso: build_fund.py OUT_DIR [cache_zips]"""
import json, os, sys, time
from datetime import date, datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_cvm import get_zip, stmts, pivot, tickers, da_flows, nao_fin, divida_liquida, cancelamentos  # noqa: E402  (mesma leitura e contas da CVM)

ANO0 = 2009
WEEK = 6.5 * 86400


def main(out, cache):
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(out, "fund.json")
    try:
        old = json.load(open(path))
        age = time.time() - datetime.fromisoformat(old["fetched_at"]).timestamp()
        tem_dl = any("dl" in v for v in old["a"].values())  # snapshot antigo sem dívida ou sem as empresas que saíram: refaz
        if age < WEEK and tem_dl and "saida" in old: print("fund: snapshot desta semana já existe"); return 0
    except Exception:
        pass
    today = date.today()
    t2c = tickers(cache, today.year)
    try:  # só papéis negociados (lista da B3): as classes deduzidas pela raiz que não existem saem
        listed = set(json.load(open(os.path.join(out, "b3_listed.json")))["tickers"])
        if len(listed) > 200: t2c = {t: c for t, c in t2c.items() if t in listed}
    except Exception:
        pass
    # empresas que saíram da bolsa (history4_saiu, build_cotahist.py): CNPJ pelos FCA desde 2010 e motivo do cancelamento na CVM
    sd = os.path.join(out, "history4_saiu"); saiu = sorted(f[:-8] for f in os.listdir(sd)) if os.path.isdir(sd) else []
    if saiu:
        velho = tickers(cache, today.year, anos=today.year - 2009, ativos=False)
        t2c.update({t: velho[t] for t in saiu if t in velho and t not in t2c})
    try: canc = cancelamentos() if saiu else {}
    except Exception as e: canc = {}; print("fund: cadastro da CVM indisponível:", type(e).__name__)
    data = {}  # cnpj -> {ano: {rev, ni, eq, dl, eb}}
    for y in range(ANO0, today.year):
        z = get_zip(cache, "DFP", y)
        if not z: print(f"  DFP {y}: sem arquivo"); continue
        dre = stmts(z, "dfp", y, "DRE", ["3.01", "3.05", "3.11", "3.11.01"]); bpp = stmts(z, "dfp", y, "BPP", ["2.03", "2.01.04", "2.02.01"])
        bpa = stmts(z, "dfp", y, "BPA", ["1.01.01", "1.01.02"])
        F = pivot(dre, dre["ORDEM_EXERC"] == "ÚLTIMO"); B = pivot(bpp, bpp["ORDEM_EXERC"] == "ÚLTIMO"); B.update(pivot(bpa, bpa["ORDEM_EXERC"] == "ÚLTIMO"))
        ds = {c: d for c, k, d in zip(dre["CNPJ_CIA"], dre["CD_CONTA"], dre["DS_CONTA"]) if k == "3.05"}
        DA = {c: v for (c, ini, o), v in da_flows(z, "dfp", y).items() if o == "ÚLTIMO"}
        n = 0
        for (c, k), v in F.items():
            d = data.setdefault(c, {}).setdefault(y, {})
            if k == "3.01": d["rev"] = v
            elif (k == "3.11.01" and v) or (k == "3.11" and "ni" not in d): d["ni"] = v  # 3.11.01 = 0: linha não preenchida
        for (c, k), v in B.items():
            if k == "2.03": data.setdefault(c, {}).setdefault(y, {})["eq"] = v; n += 1
        for c in {c for c, _ in B} & set(ds):  # dívida e EBITDA só nas não financeiras (banco/seguradora: não se aplica)
            if not nao_fin(ds[c]): continue
            d = data.setdefault(c, {}).setdefault(y, {}); bal = {k: B.get((c, k)) for k in ("2.01.04", "2.02.01", "1.01.01", "1.01.02")}
            d["dl"] = divida_liquida(bal)
            if F.get((c, "3.05")) is not None and c in DA: d["eb"] = F[(c, "3.05")] + DA[c]
        print(f"  DFP {y}: {n} empresas", flush=True)
        z.close()
    A = {}
    for t, c in t2c.items():
        d = data.get(c)
        if not d: continue
        ys = sorted(y for y in d if d[y].get("ni") is not None and d[y].get("eq") is not None)
        if not ys: continue
        A[t] = {"y": ys, "rev": [d[y].get("rev") for y in ys], "ni": [d[y]["ni"] for y in ys], "eq": [d[y]["eq"] for y in ys]}
        if any("dl" in d[y] for y in ys): A[t].update({"dl": [d[y].get("dl") for y in ys], "eb": [d[y].get("eb") for y in ys]})
    if not A: print("fund: nada montado", file=sys.stderr); return 1
    saida = {t: canc.get(t2c.get(t), "") for t in saiu}  # motivo da saída ("" = registro não cancelado ou sem CNPJ: troca de código, etc.)
    json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fonte": "CVM (DFP, dados abertos)", "a": A, "saida": saida},
              open(path, "w"), separators=(",", ":"))
    print(f"fund: {len(A)} tickers, exercícios {ANO0}–{today.year - 1}, {os.path.getsize(path) / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "/tmp/cvmraw"))
