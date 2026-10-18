#!/usr/bin/env python3
"""Fatos Relevantes e Comunicados ao Mercado das empresas (CVM, IPE, dados abertos) -> OUT/fatos.json, para os modelos da Previsão.
Só os que têm tom pelo vocabulário (modelos.tom_noticia: recuperação judicial, fraude, recompra…); data = entrega à CVM (quando ficou
público), para os modelos nunca "verem o futuro". Por CNPJ, com o mapa ticker -> CNPJ do cadastro FCA (build_cvm.tickers).
Histórico completo 1×/semana; nos outros dias refaz só o ano corrente. Uso: build_fatos.py OUT_DIR [cache_zips]"""
import json, os, sys, time
from datetime import date, datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from build_cvm import get_zip, read, tickers  # noqa: E402  (mesma leitura dos arquivos da CVM)
from modelos import tom_noticia  # noqa: E402  (mesmo vocabulário dos modelos)

ANO0 = 2010
WEEK = 6.5 * 86400
CATS = ("Fato Relevante", "Comunicado ao Mercado")


def ano(cache, y, fresh=False):
    """-> {cnpj: [[data, assunto], ...]} dos documentos com tom no ano y."""
    fn = os.path.join(cache, f"ipe_cia_aberta_{y}.zip")
    if fresh and os.path.exists(fn): os.remove(fn)  # ano corrente: baixa de novo
    try: z = get_zip(cache, "IPE", y)
    except Exception as e: print(f"  IPE {y}: {type(e).__name__}"); z = None
    if not z: print(f"  IPE {y}: sem arquivo"); return {}
    df = read(z, f"ipe_cia_aberta_{y}.csv")
    if df.empty: return {}
    df = df[df["Categoria"].isin(CATS)]
    out, n = {}, 0
    for c, d, a, tp, es in zip(df["CNPJ_Companhia"], df["Data_Entrega"], df["Assunto"].fillna(""), df["Tipo"].fillna(""), df["Especie"].fillna("")):
        x = " ".join(str(v) for v in (a, tp, es) if v and v == v).strip()
        if not x or not str(d)[:4].isdigit() or not tom_noticia(x)[0]: continue
        out.setdefault(c, []).append([str(d)[:10], x[:160]]); n += 1
    print(f"  IPE {y}: {len(df)} documentos, {n} com tom", flush=True)
    z.close()
    return out


def main(out, cache):
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(out, "fatos.json"); today = date.today()
    try:
        old = json.load(open(path)); full = time.time() - datetime.fromisoformat(old["full_at"]).timestamp() >= WEEK
    except Exception:
        old, full = None, True
    C = {}
    if full:
        for y in range(ANO0, today.year + 1):
            for c, L in ano(cache, y, fresh=y == today.year).items(): C.setdefault(c, []).extend(L)
    else:  # mantém os anos anteriores e refaz o corrente
        cur = str(today.year); novo = ano(cache, today.year, fresh=True)
        for c, L in old["c"].items():
            L = [e for e in L if not (novo and e[0].startswith(cur))]  # sem o arquivo novo, fica o que já havia
            if L: C[c] = L
        for c, L in novo.items(): C.setdefault(c, []).extend(L)
    if not C: print("fatos: nada montado", file=sys.stderr); return 1
    t2c = tickers(cache, today.year)
    try:  # só papéis negociados (lista da B3)
        listed = set(json.load(open(os.path.join(out, "b3_listed.json")))["tickers"])
        if len(listed) > 200: t2c = {t: c for t, c in t2c.items() if t in listed}
    except Exception:
        pass
    T = {t: c for t, c in t2c.items() if c in C}
    for c in C: C[c] = sorted({tuple(e) for e in C[c]})
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump({"fetched_at": now, "full_at": now if full else old["full_at"], "fonte": "CVM (IPE: Fatos Relevantes e Comunicados ao Mercado)",
               "t": T, "c": {c: [list(e) for e in L] for c, L in C.items() if c in set(T.values())}},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"fatos: {len(T)} tickers, {sum(len(v) for v in C.values())} documentos com tom, {os.path.getsize(path) / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "/tmp/cvmraw"))
