#!/usr/bin/env python3
"""Índice de Medo e Ganância da B3 (0 = medo extremo, 100 = ganância extrema), diário desde os anos 1990 -> OUT/fg.json.
Só dados da B3 que o site já guarda: histórico COTAHIST (history4/), fluxo por investidor (b3_flow.json) e CDI do BCB.
"Mercado" = média dos retornos diários das 50 ações mais negociadas (volume médio de 60 pregões), parecido com o Ibovespa,
mas disponível desde 1995 (o Ibovespa diário do Yahoo só tem 5 anos). Cada parte vira uma nota de 0 a 100 pela posição do
valor de hoje entre os valores do último ano (252 pregões); o índice é a média das partes disponíveis no dia.
O índice de cada ação (Comparar) é calculado na hora por medo.stock_index, com a mesma regra de nota (medo.rank).
Uso: build_fg.py OUT_DIR   (lê OUT_DIR/history4, OUT_DIR/b3_flow.json, OUT_DIR/history/bcb_cdi.json)."""
import glob, gzip, json, os, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import medo  # noqa: E402  (regra da nota 0–100: fonte única)

OUT = sys.argv[1]
WIN = 252
# faixas do índice (fonte única: o site, o chat e o Comparar leem de fg.json)
FAIXAS = [[25, "Medo extremo"], [45, "Medo"], [55, "Neutro"], [75, "Ganância"], [100, "Ganância extrema"]]
# partes: chave -> (nome, sentido). sentido -1: valor alto = medo (a nota é invertida)
PARTES = {"mom": ("Ibovespa × média de 6 meses", 1), "forca": ("Máximas × mínimas de 1 ano", 1), "amp": ("Ações acima da média de 50 dias", 1),
          "vol": ("Oscilação do mercado", -1), "volume": ("Volume em altas × quedas", 1), "porto": ("Ações × renda fixa (CDI) em 20 dias", 1),
          "estr": ("Saldo de estrangeiros em 20 dias", 1)}


def load_hist():
    C, V = {}, {}
    for f in glob.glob(os.path.join(OUT, "history4", "*.json.gz")):
        h = json.loads(gzip.decompress(open(f, "rb").read()))
        d = h.get("d") or {}
        if len(d.get("t") or []) < WIN: continue
        idx = pd.to_datetime(d["t"], unit="s").normalize()
        t = os.path.basename(f)[:-8]
        C[t] = pd.Series(d["c"], index=idx, dtype="float64")
        V[t] = pd.Series(d.get("vol") or [np.nan] * len(idx), index=idx, dtype="float64")
    C = pd.DataFrame(C).sort_index(); V = pd.DataFrame(V).reindex(C.index)
    C = C[~C.index.duplicated()]; V = V[~V.index.duplicated()]
    return C, V


def pct_rank(s, invert=False):
    """Nota 0–100 de cada dia: posição do valor entre os últimos 252 (mesma regra de medo.rank)."""
    a = s.to_numpy(dtype="float64")
    return pd.Series([np.nan if (x := medo.rank(a, i, invert)) is None else x for i in range(len(a))], index=s.index)


def main():
    C, V = load_hist()
    R = C.pct_change(fill_method=None).where(lambda x: x.abs() < 0.5)  # retornos diários (descarta erros de dado > 50%)
    vol60 = V.rolling(60, min_periods=20).mean().shift(1)
    rk = vol60.rank(axis=1, ascending=False)
    top = rk <= 50; liq = rk <= 150  # mercado (50 mais negociadas) e universo líquido (150)
    mret = R.where(top).mean(axis=1)
    M = (1 + mret.fillna(0)).cumprod()
    raw = {}
    raw["mom"] = M / M.rolling(125, min_periods=100).mean() - 1
    hi = C >= C.rolling(WIN, min_periods=200).max(); lo = C <= C.rolling(WIN, min_periods=200).min()
    n = (liq & C.notna()).sum(axis=1).replace(0, np.nan)
    raw["forca"] = ((hi & liq).sum(axis=1) - (lo & liq).sum(axis=1)) / n
    raw["amp"] = ((C > C.rolling(50, min_periods=40).mean()) & liq).sum(axis=1) / n
    raw["vol"] = mret.rolling(20, min_periods=15).std() * np.sqrt(252)
    up = V.where(liq & (R > 0)).rolling(20, min_periods=15).sum().sum(axis=1)
    tot = V.where(liq & R.notna()).rolling(20, min_periods=15).sum().sum(axis=1).replace(0, np.nan)
    raw["volume"] = up / tot
    try:
        cdi = json.load(open(os.path.join(OUT, "history", "bcb_cdi.json")))
        cs = pd.Series(cdi["v"], index=pd.to_datetime(cdi["d"])).reindex(M.index).ffill()
        cacc = (1 + cs / 100).rolling(20, min_periods=15).apply(np.prod, raw=True) - 1
        raw["porto"] = (M / M.shift(20) - 1) - cacc
    except Exception as e:
        print("fg: sem CDI:", e)
    try:
        fl = json.load(open(os.path.join(OUT, "b3_flow.json"))).get("days") or {}
        es = pd.Series({pd.Timestamp(d): v.get("Investidor Estrangeiro", [0, 0, 0])[2] for d, v in fl.items()}).sort_index()
        if len(es) >= 140:  # só entra com histórico suficiente para comparar com o ano
            raw["estr"] = es.rolling(20, min_periods=15).sum().reindex(M.index)
    except Exception as e:
        print("fg: sem fluxo:", e)
    notas = {k: pct_rank(s, PARTES[k][1] < 0) for k, s in raw.items()}
    N = pd.DataFrame(notas)
    fg = N.mean(axis=1, skipna=True).where(N.notna().sum(axis=1) >= 3).dropna().round()
    fg = fg[fg.index >= "1997-01-01"]
    last = N.loc[fg.index[-1]]
    out = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "fonte": "B3 (COTAHIST, fluxo por investidor) e BCB (CDI); cálculo do site", "faixas": FAIXAS,
           "d": [x.strftime("%Y-%m-%d") for x in fg.index], "v": [int(x) for x in fg.to_numpy()],
           "partes": {k: {"n": PARTES[k][0], "v": None if np.isnan(last.get(k, np.nan)) else int(round(last[k]))} for k in PARTES}}
    json.dump(out, open(os.path.join(OUT, "fg.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    print(f"fg: {out['d'][0]} a {out['d'][-1]}, hoje {out['v'][-1]}, {len(out['d'])} pregões; partes {out['partes']}")


if __name__ == "__main__":
    main()
