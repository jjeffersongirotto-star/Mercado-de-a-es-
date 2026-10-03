"""Snapshot CVM dados abertos (DFP/ITR oficiais) -> data/cvm.json compacto por ticker.
Pré-processa na máquina da rotina (memória); o Render só lê o JSON pronto.
Uso: build_cvm.py <dir_saida> [dir_cache_zips]
Calcula (TTM = acumulado do ano atual + último exercício − acumulado do ano anterior):
  receita, lucro bruto, EBIT padrão (3.05) e EBIT ajustado (Lucro bruto − desp. vendas − desp. G&A, como Fundamentus),
  lucro líquido, ativo, patrimônio, caixa, dívida bruta (empréstimos e financiamentos), fornecedores, ações.
Indicadores sem preço vão prontos; os que dependem de preço (P/L, P/VP, P/EBIT, EV/EBIT, P/Ativo, PSR) o servidor calcula."""
import io, os, sys, json, zipfile
from datetime import date
import requests, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from snaputil import save

BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC"
DRE_C = ["3.01", "3.03", "3.04.01", "3.04.02", "3.05", "3.11", "3.11.01"]
BPA_C = ["1", "1.01", "1.01.01", "1.01.02"]
BPP_C = ["2.01", "2.01.02", "2.01.04", "2.02.01", "2.03"]

def get_zip(cache, kind, year):
    fn = os.path.join(cache, f"{kind.lower()}_cia_aberta_{year}.zip")
    if not os.path.exists(fn) or os.path.getsize(fn) < 1000:
        r = requests.get(f"{BASE}/{kind}/DADOS/{kind.lower()}_cia_aberta_{year}.zip", timeout=300)
        if r.status_code != 200: return None
        open(fn, "wb").write(r.content)
    return zipfile.ZipFile(fn)

def read(z, name, codes=None, cols=None):
    names = [n for n in z.namelist() if n.endswith(name)]
    if not names: return pd.DataFrame()
    df = pd.read_csv(z.open(names[0]), sep=";", encoding="latin1", dtype=str, usecols=cols)
    if codes is not None: df = df[df["CD_CONTA"].isin(codes)]
    return df

def stmts(z, kind, year, stmt, codes):
    """con (consolidado) com fallback ind (individual) por empresa."""
    cols = ["CNPJ_CIA", "DT_REFER", "VERSAO", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC", "CD_CONTA", "DS_CONTA", "VL_CONTA"]
    cols_b = [c for c in cols if c != "DT_INI_EXERC"]
    out = []
    for ci in ("con", "ind"):
        df = read(z, f"{kind}_cia_aberta_{stmt}_{ci}_{year}.csv", None, cols if stmt.startswith("DRE") else cols_b)
        if df.empty: continue
        df = df[df["CD_CONTA"].str.count(r"\.") <= 2]
        df = normalize(df, stmt)
        df = df[df["CD_CONTA"].isin(codes)]
        if out: df = df[~df["CNPJ_CIA"].isin(set(out[0]["CNPJ_CIA"]))]
        out.append(df)
    df = pd.concat(out) if out else pd.DataFrame(columns=cols)
    df["v"] = pd.to_numeric(df["VL_CONTA"], errors="coerce") * df["ESCALA_MOEDA"].map({"MIL": 1000.0}).fillna(1.0)
    # versão mais recente do documento
    df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce")
    df = df[df["VERSAO"] == df.groupby(["CNPJ_CIA", "DT_REFER"])["VERSAO"].transform("max")]
    return df

def normalize(df, stmt):
    """Bancos/seguradoras usam códigos diferentes: mapeia lucro consolidado -> 3.11 (controladora -> 3.11.01)
    e patrimônio líquido -> 2.03 pelo nome da conta."""
    df = df.copy()
    cd = df["CD_CONTA"].tolist(); ds = df["DS_CONTA"].fillna("").tolist(); cn = df["CNPJ_CIA"].tolist()
    if stmt == "DRE":
        import re
        ni = {}
        for c, k, d in zip(cn, cd, ds):
            if k.count(".") == 1 and re.match(r"^Lucro.{0,3}Preju[ií]zo (Consolidado|Líquido)", d): ni.setdefault(c, k)
        new = []
        for c, k, d in zip(cn, cd, ds):
            b = ni.get(c)
            if b and b != "3.11":
                if k == b: k = "3.11"
                elif k.startswith(b + ".") and k.count(".") == 2 and "Controladora" in d: k = "3.11.01"
                elif k.startswith("3.11"): k = "x" + k
            new.append(k)
    else:
        eq = {}
        for c, k, d in zip(cn, cd, ds):
            if k.count(".") == 1 and d.startswith("Patrimônio Líquido"): eq.setdefault(c, k)
        new = []
        for c, k in zip(cn, cd):
            b = eq.get(c)
            if b and b != "2.03":
                if k == b: k = "2.03"
                elif k == "2.03" or k.startswith("2.03."): k = "x" + k
            new.append(k)
    df["CD_CONTA"] = new
    return df

def pivot(df, flt):
    d = df[flt]
    return {(c, k): v for c, k, v in zip(d["CNPJ_CIA"], d["CD_CONTA"], d["v"])}

def main(outdir, cache):
    os.makedirs(cache, exist_ok=True)
    today = date.today()
    fy = today.year - 1
    dfp = get_zip(cache, "DFP", fy)
    if dfp is None or len(read(dfp, f"dfp_cia_aberta_DRE_con_{fy}.csv", ["3.01"])) < 100:
        fy -= 1; dfp = get_zip(cache, "DFP", fy)
    dfp5 = get_zip(cache, "DFP", fy - 5)
    itr = get_zip(cache, "ITR", fy + 1)
    fca = get_zip(cache, "FCA", today.year)
    print(f"DFP {fy} / {fy-5}, ITR {fy+1}", flush=True)

    # --- DFP (exercício fy e fy-5)
    dre_f = stmts(dfp, "dfp", fy, "DRE", DRE_C)
    FY = pivot(dre_f, (dre_f["ORDEM_EXERC"] == "ÚLTIMO"))
    ds305 = {c: s for c, k, s in zip(dre_f["CNPJ_CIA"], dre_f["CD_CONTA"], dre_f["DS_CONTA"]) if k == "3.05"}
    dre_5 = stmts(dfp5, "dfp", fy - 5, "DRE", ["3.01", "3.11", "3.11.01"]) if dfp5 else pd.DataFrame()
    FY5 = pivot(dre_5, dre_5["ORDEM_EXERC"] == "ÚLTIMO") if len(dre_5) else {}
    bal_f = pd.concat([stmts(dfp, "dfp", fy, "BPA", BPA_C), stmts(dfp, "dfp", fy, "BPP", BPP_C)])
    BALF = pivot(bal_f, bal_f["ORDEM_EXERC"] == "ÚLTIMO")
    # --- ITR do ano corrente
    YTD, YTDP, BALI, refI = {}, {}, {}, {}
    if itr:
        dre_i = stmts(itr, "itr", fy + 1, "DRE", DRE_C)
        last = dre_i.groupby("CNPJ_CIA")["DT_REFER"].max()
        dre_i = dre_i[dre_i["DT_REFER"] == dre_i["CNPJ_CIA"].map(last)]
        YTD = pivot(dre_i, (dre_i["ORDEM_EXERC"] == "ÚLTIMO") & (dre_i["DT_INI_EXERC"] == f"{fy+1}-01-01"))
        YTDP = pivot(dre_i, (dre_i["ORDEM_EXERC"] == "PENÚLTIMO") & (dre_i["DT_INI_EXERC"] == f"{fy}-01-01"))
        refI = last.to_dict()
        bal_i = pd.concat([stmts(itr, "itr", fy + 1, "BPA", BPA_C), stmts(itr, "itr", fy + 1, "BPP", BPP_C)])
        bal_i = bal_i[bal_i["DT_REFER"] == bal_i["CNPJ_CIA"].map(last)]
        BALI = pivot(bal_i, bal_i["ORDEM_EXERC"] == "ÚLTIMO")
    # --- ações (composição do capital) e tickers
    shares = {}
    for z, kind, y in ((dfp, "dfp", fy), (itr, "itr", fy + 1)):
        if not z: continue
        cc = read(z, f"{kind}_cia_aberta_composicao_capital_{y}.csv")
        if cc.empty: continue
        cc = cc.sort_values("DT_REFER")
        for _, r in cc.iterrows():
            tot = pd.to_numeric(r.get("QT_ACAO_TOTAL_CAP_INTEGR"), errors="coerce")
            tes = pd.to_numeric(r.get("QT_ACAO_TOTAL_TESOURO"), errors="coerce")
            if tot and tot > 0: shares[r["CNPJ_CIA"]] = float(tot - (tes if tes == tes else 0))
    vm = read(fca, f"fca_cia_aberta_valor_mobiliario_{today.year}.csv")
    vm = vm[vm["Codigo_Negociacao"].notna() & vm["Data_Fim_Negociacao"].isna()]
    tick2cnpj = {str(t).strip().upper(): c for t, c in zip(vm["Codigo_Negociacao"], vm["CNPJ_Companhia"]) if 4 < len(str(t).strip()) <= 7}

    def acc(cnpj):
        """Valores TTM e balanço mais recente para a empresa."""
        g = lambda D, k: D.get((cnpj, k))
        has_itr = cnpj in refI and g(YTD, "3.01") is not None and g(YTDP, "3.01") is not None
        flow = {}
        for k in DRE_C:
            a = g(FY, k)
            if has_itr:
                b, c = g(YTD, k), g(YTDP, k)
                flow[k] = a + b - c if None not in (a, b, c) else None
            else:
                flow[k] = a
        B = BALI if (has_itr and (cnpj, "1") in BALI) else BALF
        bal = {k: B.get((cnpj, k)) for k in BPA_C + BPP_C}
        ref = refI.get(cnpj) if has_itr else f"{fy}-12-31"
        return flow, bal, ref

    rows, cache_co = {}, {}
    for t, cnpj in tick2cnpj.items():
        if (cnpj, "3.01") not in FY: continue
        if cnpj not in cache_co: cache_co[cnpj] = acc(cnpj)
        flow, bal, ref = cache_co[cnpj]
        fin = "Financeiro" not in (ds305.get(cnpj) or "")
        rev, gross, ebit, ni = flow["3.01"], flow["3.03"], flow["3.05"], flow["3.11.01"] if flow.get("3.11.01") is not None else flow["3.11"]
        ebit_adj = (gross + (flow["3.04.01"] or 0) + (flow["3.04.02"] or 0)) if gross is not None and not fin else None
        assets, eq = bal["1"], bal["2.03"]
        cash = (bal["1.01.01"] or 0) + (bal["1.01.02"] or 0)
        debt = (bal["2.01.04"] or 0) + (bal["2.02.01"] or 0)
        sh = shares.get(cnpj)
        div = lambda a, b, m=1.0: round(a / b * m, 4) if a is not None and b not in (None, 0) else None
        r = {"cnpj": cnpj, "ref": ref, "fin": fin,
             "_rev": rev, "_ebit": None if fin else ebit, "_ebit_adj": ebit_adj, "_ni": ni, "_assets": assets, "_eq": eq,
             "_netdebt": None if fin else debt - cash, "_shares": sh,
             "roe": div(ni, eq, 100) if eq and eq > 0 else None, "roa": div(ni, assets, 100),
             "lpa": div(ni, sh), "vpa": div(eq, sh)}
        if not fin:
             inv = (assets or 0) - (bal["2.01.02"] or 0) - cash
             r.update({"mbruta": div(gross, rev, 100), "mebit": div(ebit, rev, 100), "mebit_adj": div(ebit_adj, rev, 100),
                       "mliq": div(ni, rev, 100), "liqcorr": div(bal["1.01"], bal["2.01"]),
                       "dlpl": div(debt - cash, eq) if eq and eq > 0 else None, "dlebit": div(debt - cash, ebit) if ebit and ebit > 0 else None,
                       "roic": div(ebit, inv, 100) if inv > 0 else None, "roic_adj": div(ebit_adj, inv, 100) if inv > 0 else None})
        # CAGR 5 anos (exercícios fy vs fy-5)
        for key, k in (("cresc5a", "3.01"), ("lucro5a", "3.11.01")):
            a, b = FY.get((cnpj, k)), FY5.get((cnpj, k))
            if k == "3.11.01" and (a is None or b is None): a, b = FY.get((cnpj, "3.11")), FY5.get((cnpj, "3.11"))
            if a and b and a > 0 and b > 0 and not (fin and key == "cresc5a"): r[key] = round(((a / b) ** 0.2 - 1) * 100, 2)
        rows[t] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if v is not None}
    save(os.path.join(outdir, "cvm.json"), "cvm", rows, {"fy": fy, "itr_year": fy + 1})
    print(f"CVM: {len(rows)} tickers ({len(cache_co)} empresas)")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data", sys.argv[2] if len(sys.argv) > 2 else "/tmp/cvmraw")
