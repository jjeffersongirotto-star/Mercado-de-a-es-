#!/usr/bin/env python3
"""Sinais semanais dos modelos da Previsão (card Modelos) -> OUT/modelos.json. Regras dos modelos: modelos.py (MODELOS).
Por ação da B3 (history4) e por semana (último pregão da semana): fechamento, proventos da semana, índice de Medo e Ganância
da ação (medo.stock_index), distância da média de 200 pregões, alta em 12 meses e a chance de alta prevista pelo algoritmo
para 1 mês (20 pregões) e 3 meses (60 pregões). O índice do mercado vem de fg.json (scripts/build_fg.py).
Algoritmo: regressão logística com os indicadores de gráfico, medo e ganância e dividendos, treinada a cada ano só com os anos
anteriores (a previsão de um ano nunca vê o próprio ano). Uso: build_modelos.py OUT_DIR (lê OUT_DIR/history4 e OUT_DIR/fg.json)."""
import gzip, json, os, sys, time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import medo  # noqa: E402  (índice da ação: mesma regra do Comparar)
from build_fg import load_hist, market  # noqa: E402  (mesmo "mercado" do índice)

START = "2006-01-01"  # primeira semana dos sinais (o algoritmo precisa de anos anteriores para treinar)
TRAIN0 = "1998-01-01"
F = ["si", "mi", "dsi20", "dmi20", "r5", "r20", "r60", "r120", "r250", "dd", "up52", "ma50", "ma200", "cross", "brk_hi", "brk_lo", "bb",
     "vol20", "volr", "vlr", "rsi", "streak_w", "dy12", "ddy", "rs60", "rs250"]
HS = (20, 60)  # horizontes do algoritmo (pregões): 1 e 3 meses


TIPO = (("J", "JRS CAP PROPRIO"), ("D", "DIVIDENDO"), ("R", "RENDIMENTO"), ("K", "REST CAP DIN"))  # rótulos da lista da B3
TC = [c for c, _ in TIPO]


def splits(out, t, sub="history4"):
    """Desdobramentos/grupamentos/bonificações do arquivo de histórico [[último pregão antes (AAAA-MM-DD), fator]] (ajustado = bruto ÷
    fatores dos eventos com data ≥ o pregão): modelos.py leva o número de ações de cada balanço (fund.json → sh) à base dos preços."""
    h = json.loads(gzip.decompress(open(os.path.join(out, sub, f"{t}.json.gz"), "rb").read()))
    return [[pd.Timestamp(x[0], unit="s").strftime("%Y-%m-%d"), round(float(x[1]), 6)] for x in h.get("splits") or [] if x[1]]


def divs(out, t, idx, sub="history4"):
    """Proventos por pregão (data ex) do arquivo history4 da ação: total (dv) e quanto de cada tipo da B3 (J = JCP, D = dividendo,
    R = rendimento, K = restituição de capital; datas antigas vêm do Yahoo sem tipo)."""
    h = json.loads(gzip.decompress(open(os.path.join(out, sub, f"{t}.json.gz"), "rb").read()))
    M = np.zeros((len(idx), 1 + len(TIPO)))
    for x in h.get("divs") or []:
        j = idx.searchsorted(pd.Timestamp(x[0], unit="s").normalize())
        if j >= len(idx): continue
        M[j, 0] += x[1]
        lb = str(x[2] if len(x) > 2 else "").upper()
        for k, (_, rx) in enumerate(TIPO):
            if rx in lb: M[j, 1 + k] += x[1]; break
    return pd.DataFrame(M, index=idx, columns=["dv"] + [c for c, _ in TIPO])


def features(c, v, dv, mi, mk):
    """Indicadores diários de uma ação (c, v: fechamento e volume; dv: proventos; mi: índice do mercado; mk: mercado acumulado)."""
    r = c.pct_change().where(lambda x: x.abs() < 0.5)
    X = pd.DataFrame(index=c.index)
    X["si"] = pd.Series(medo.stock_index(c.tolist(), v.tolist()), index=c.index, dtype="float64")
    X["mi"] = mi.reindex(c.index).ffill()
    X["dsi20"], X["dmi20"] = X.si - X.si.shift(20), X.mi - X.mi.shift(20)
    for n in (5, 20, 60, 120, 250): X[f"r{n}"] = c / c.shift(n) - 1
    X["dd"] = c / c.rolling(250, min_periods=120).max() - 1
    X["up52"] = c / c.rolling(250, min_periods=120).min() - 1
    s50, s200 = c.rolling(50).mean(), c.rolling(200, min_periods=150).mean()
    X["ma50"], X["ma200"], X["cross"] = c / s50 - 1, c / s200 - 1, s50 / s200 - 1
    X["brk_hi"] = (c >= c.rolling(20).max().shift(1)).astype(float)
    X["brk_lo"] = (c <= c.rolling(20).min().shift(1)).astype(float)
    X["bb"] = (c - c.rolling(20).mean()) / (2 * c.rolling(20).std())
    X["vol20"] = r.rolling(20).std() * np.sqrt(252)
    X["volr"] = X.vol20 / (r.rolling(250).std() * np.sqrt(252))
    X["vlr"] = v.rolling(20).mean() / v.rolling(120).mean()
    g, l = r.clip(lower=0).rolling(14).mean(), (-r.clip(upper=0)).rolling(14).mean()
    X["rsi"] = 100 - 100 / (1 + g / l)
    wk = c.resample("W-FRI").last().pct_change(); st, s_ = [], 0
    for x in wk:
        s_ = (s_ + 1 if s_ > 0 else 1) if x > 0 else (s_ - 1 if s_ < 0 else -1) if x < 0 else 0
        st.append(s_)
    X["streak_w"] = pd.Series(st, index=wk.index).reindex(c.index, method="ffill")
    X["dy12"] = dv.rolling(250, min_periods=200).sum() / c
    X["ddy"] = X.dy12 - X.dy12.shift(60)
    m = mk.reindex(c.index).ffill()
    X["rs60"], X["rs250"] = X.r60 - (m / m.shift(60) - 1), X.r250 - (m / m.shift(250) - 1)
    for n in HS: X[f"f{n}"] = c.shift(-n) / c - 1
    return X.replace([np.inf, -np.inf], np.nan)


def lucro(f, W):
    """Último balanço anual já publicado em cada semana teve lucro? 1 sim, 0 não, None sem balanço ainda.
    O exercício do ano Y vale a partir de 1º de maio de Y+1 (prazo de publicação): nunca usa um balanço que ainda não saiu."""
    if not f: return None
    av = pd.to_datetime([f"{y + 1}-05-01" for y in f["y"]])
    j = np.searchsorted(av.values, pd.DatetimeIndex(W).values, side="right") - 1
    return [None if k < 0 else int((f["ni"][k] or 0) > 0 and (f["eq"][k] or 0) > 0) for k in j]


def logit_fit(X, y, it=300, lr=0.2, l2=1.0):
    w, b = np.zeros(X.shape[1]), 0.0
    for _ in range(it):
        p = 1 / (1 + np.exp(-(X @ w + b))); g = p - y
        w -= lr * (X.T @ g / len(y) + l2 * w / len(y)); b -= lr * g.mean()
    return w, b


def walk_forward(P, H):
    """Chance de alta em H pregões de cada linha a partir de START; cada ano usa um modelo treinado só com os anos anteriores."""
    out = pd.Series(np.nan, index=P.index)
    ok = P[F[:1] + ["mi", "r250", "ma200", "rsi", "volr"]].notna().all(axis=1)
    yrs = sorted({d.year for d in P.index.get_level_values(0) if d >= pd.Timestamp(START)})
    hits = []
    for Y in yrs:
        d = P.index.get_level_values(0)
        lim = pd.Timestamp(f"{Y}-01-01") - pd.Timedelta(days=int(H * 1.5))  # rótulo (alta em H pregões) não pode entrar no ano testado
        trn = P[ok & (d < lim) & P.liq & P[f"f{H}"].notna()]
        te = P[ok & (d.year == Y)]
        if len(trn) < 5000 or not len(te): continue
        Xtr = trn[F].to_numpy(float); mu, sd = np.nanmean(Xtr, 0), np.nanstd(Xtr, 0) + 1e-9
        Z = lambda X: np.nan_to_num((X - mu) / sd).clip(-5, 5)
        w, b = logit_fit(Z(Xtr), (trn[f"f{H}"] > 0).to_numpy(float))
        p = 1 / (1 + np.exp(-(Z(te[F].to_numpy(float)) @ w + b)))
        out.loc[te.index] = p
        f = te[f"f{H}"].to_numpy(); m = ~np.isnan(f)
        hits += list((p[m] > 0.5) == (f[m] > 0))
    return out, (round(float(np.mean(hits)) * 100, 1) if hits else None)


def main(out):
    t0 = time.time()
    C, V = load_hist(out)
    R, mret, liq = market(C, V)
    mk = (1 + mret.fillna(0)).cumprod()
    fg = json.load(open(os.path.join(out, "fg.json")))
    mi = pd.Series(fg["v"], index=pd.to_datetime(fg["d"]), dtype="float64")
    C, V, liq = C[C.index >= TRAIN0], V[V.index >= TRAIN0], liq[liq.index >= TRAIN0]
    # empresas que saíram da bolsa (build_cotahist.py → history4_saiu): entram nos modelos até o último pregão; o "mercado" não muda
    Cs, Vs = load_hist(out, "history4_saiu") if os.path.isdir(os.path.join(out, "history4_saiu")) else (pd.DataFrame(), pd.DataFrame())
    Cs, Vs = Cs[Cs.index >= TRAIN0], Vs[Vs.index >= TRAIN0]
    SAI = {t: Cs[t].last_valid_index() for t in Cs.columns}
    v60 = V.rolling(60, min_periods=20).mean().shift(1).to_numpy()  # entre as 150 mais líquidas do dia (mesma regra de market) também treina
    thr = pd.Series(-np.sort(-np.nan_to_num(v60, nan=-1.0), axis=1)[:, min(149, v60.shape[1] - 1)], index=V.index)
    weeks = C.index.to_series().groupby(C.index.to_period("W-FRI")).max()  # último pregão de cada semana
    weeks = weeks[weeks >= pd.Timestamp(START)]
    W = pd.DatetimeIndex(weeks.values)
    try: FJ = json.load(open(os.path.join(out, "fund.json"))); FD = FJ["a"]  # fundamentos anuais (scripts/build_fund.py)
    except Exception as e: FJ, FD = {}, {}; print("modelos: sem fundamentos (fund.json):", e)
    TROCA = FJ.get("troca") or {}  # código antigo da mesma companhia de hoje (troca de código/classe): não é saída da bolsa
    rows, series = [], {}
    for t, CC, VV, sub in [(t, C, V, "history4") for t in C.columns] + [(t, Cs, Vs, "history4_saiu") for t in Cs.columns]:
        c = CC[t].dropna()
        if len(c) < 260 or (sub != "history4" and (t in C.columns or t in TROCA)): continue
        v, dd = VV[t].reindex(c.index), divs(out, t, c.index, sub); dv = dd["dv"]
        X = features(c, v, dv, mi, mk)
        X["liq"] = (liq[t].reindex(c.index).fillna(False).astype(bool) if t in liq.columns else
                    (v.rolling(60, min_periods=20).mean().shift(1) >= thr.reindex(c.index)).fillna(False))  # as que saíram também treinam
        X["vl"] = v.rolling(60, min_periods=20).mean() / 1000  # volume médio diário de 60 pregões (R$ mil): liquidez da época (modelos.REGRAS)
        wd = X.index[X.index.isin(C.index.to_series().groupby(C.index.to_period("W-FRI")).transform("max"))]
        Xw = X.loc[wd]; Xw.index = pd.MultiIndex.from_arrays([Xw.index, [t] * len(Xw)])
        rows.append(Xw)
        # séries semanais da simulação (a partir da 1ª semana com preço)
        cw = c.reindex(W, method="ffill", limit=10)
        if t in SAI: cw[W > SAI[t]] = np.nan  # depois do último pregão: sem preço (o modelo vende pelo último preço; modelos.build → SAI)
        if cw.notna().sum() < 2: continue
        dw = dd.groupby(dd.index.to_period("W-FRI")).sum()
        dw.index = dw.index.map(lambda p: weeks.get(p, pd.NaT)); dw = dw[dw.index.notna()].reindex(W).fillna(0)
        series[t] = (cw, dw, X, splits(out, t, sub))
        print(f"  {t}: {len(c)} pregões ({time.time() - t0:.0f}s)", flush=True) if len(series) % 50 == 0 else None
    P = pd.concat(rows).sort_index()
    pred, acerto = {}, {}
    for H in HS:
        pred[H], acerto[H] = walk_forward(P, H)
        print(f"algoritmo {H} pregões: acerto {acerto[H]}% ({time.time() - t0:.0f}s)", flush=True)
    A = {}
    q = lambda s, k=1: [None if x != x else (int(round(x * k)) if k != 1 or float(x).is_integer() else round(float(x), 4)) for x in s]
    for t, (cw, dw, X, sp) in series.items():
        i0 = int(np.argmax(cw.notna().to_numpy()))
        Xw = X.reindex(W, method="ffill", limit=10).iloc[i0:]
        a = {"i0": i0, "c": [None if x != x else round(float(x), 4) for x in cw.iloc[i0:]],
             "dv": {str(i - i0): round(float(x), 6) for i, x in enumerate(dw["dv"].to_numpy()) if x > 0 and i >= i0},
             # JCP por ação na semana (o modelo desconta 15% de IR na fonte) e tipos dos proventos da B3 na semana (J, D, R, K)
             "jc": {str(i - i0): round(float(x), 6) for i, x in enumerate(dw["J"].to_numpy()) if x > 0 and i >= i0},
             "tp": {str(i - i0): "".join(c for c, x in zip(TC, r) if x > 0) for i, r in enumerate(dw[TC].to_numpy()) if i >= i0 and r.max() > 0},
             "si": q(Xw.si), "m2": q(Xw.ma200, 1000), "r12": q(Xw.r250, 1000), "lp": lucro(FD.get(t), W[i0:]), "vl": [None if x != x else int(round(x)) for x in Xw.vl]}
        if sp: a["sp"] = sp
        for H, k in zip(HS, ("p1", "p3")):
            p = pred[H].xs(t, level=1) if t in pred[H].index.get_level_values(1) else pd.Series(dtype=float)
            a[k] = q(p.reindex(W, method="ffill", limit=2).iloc[i0:], 1000)
        A[t] = a
    res = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "fonte": "B3 (COTAHIST e proventos), índice de Medo e Ganância do site; cálculo do site",
           "acerto": {"p1": acerto[20], "p3": acerto[60]},
           "saiu": {t: d.strftime("%Y-%m-%d") for t, d in SAI.items() if t in A},  # empresas que saíram: último pregão
           "w": [d.strftime("%Y-%m-%d") for d in W], "mi": [None if x != x else int(x) for x in mi.reindex(W, method="ffill")], "a": A}
    json.dump(res, open(os.path.join(out, "modelos.json"), "w"), separators=(",", ":"))
    print(f"modelos: {len(A)} ações, {len(W)} semanas ({res['w'][0]} a {res['w'][-1]}), acerto {res['acerto']}, "
          f"{os.path.getsize(os.path.join(out, 'modelos.json')) / 1e6:.1f} MB, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1])
