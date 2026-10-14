#!/usr/bin/env python3
"""Fundamentos anuais de cada empresa desde 2009 (DFP da CVM) -> OUT/fund.json, para os modelos da Previsão (scripts/build_modelos.py).
Por ticker negociado hoje: receita (3.01), lucro líquido (3.11.01 ou 3.11) e patrimônio líquido (2.03) de cada exercício.
O exercício do ano Y só é usado pelos modelos a partir de maio de Y+1 (prazo de publicação), para nunca "ver o futuro".
Os arquivos da CVM mudam pouco: refaz no máximo uma vez por semana. Uso: build_fund.py OUT_DIR [cache_zips]"""
import json, os, sys, time
from datetime import date, datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_cvm import get_zip, stmts, pivot, tickers  # noqa: E402  (mesma leitura dos arquivos da CVM)

ANO0 = 2009
WEEK = 6.5 * 86400


def main(out, cache):
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(out, "fund.json")
    try:
        old = json.load(open(path))
        age = time.time() - datetime.fromisoformat(old["fetched_at"]).timestamp()
        if age < WEEK: print("fund: snapshot desta semana já existe"); return 0
    except Exception:
        pass
    today = date.today()
    fca = get_zip(cache, "FCA", today.year)
    t2c = tickers(fca, today.year) if fca else {}
    data = {}  # cnpj -> {ano: {rev, ni, eq}}
    for y in range(ANO0, today.year):
        z = get_zip(cache, "DFP", y)
        if not z: print(f"  DFP {y}: sem arquivo"); continue
        dre = stmts(z, "dfp", y, "DRE", ["3.01", "3.11", "3.11.01"]); bpp = stmts(z, "dfp", y, "BPP", ["2.03"])
        F = pivot(dre, dre["ORDEM_EXERC"] == "ÚLTIMO"); B = pivot(bpp, bpp["ORDEM_EXERC"] == "ÚLTIMO")
        n = 0
        for (c, k), v in F.items():
            d = data.setdefault(c, {}).setdefault(y, {})
            if k == "3.01": d["rev"] = v
            elif k == "3.11.01" or (k == "3.11" and "ni" not in d): d["ni"] = v
        for (c, k), v in B.items(): data.setdefault(c, {}).setdefault(y, {})["eq"] = v; n += 1
        print(f"  DFP {y}: {n} empresas", flush=True)
        z.close()
    A = {}
    for t, c in t2c.items():
        d = data.get(c)
        if not d: continue
        ys = sorted(y for y in d if d[y].get("ni") is not None and d[y].get("eq") is not None)
        if not ys: continue
        A[t] = {"y": ys, "rev": [d[y].get("rev") for y in ys], "ni": [d[y]["ni"] for y in ys], "eq": [d[y]["eq"] for y in ys]}
    if not A: print("fund: nada montado", file=sys.stderr); return 1
    json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fonte": "CVM (DFP, dados abertos)", "a": A},
              open(path, "w"), separators=(",", ":"))
    print(f"fund: {len(A)} tickers, exercícios {ANO0}–{today.year - 1}, {os.path.getsize(path) / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "/tmp/cvmraw"))
