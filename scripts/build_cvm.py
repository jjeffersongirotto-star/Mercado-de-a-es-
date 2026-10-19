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

def acoes(z, kind, year):
    """Composição do capital da entrega (DFP/ITR) -> {cnpj: ações em circulação = total integralizado − tesouraria} (versão mais nova).
    Fonte do número de ações de cada ano nos modelos (fund.json → sh): valor de mercado da época sem supor a base acionária de hoje."""
    df = read(z, f"{kind}_cia_aberta_composicao_capital_{year}.csv")
    if df.empty: return {}
    col = lambda *ks: next((c for c in df.columns if all(k in c.upper() for k in ks)), None)
    tot, tes = col("TOTAL", "INTEGR"), col("TOTAL", "TESOURO")
    if not tot: return {}
    df = df.assign(_v=pd.to_numeric(df.get("VERSAO"), errors="coerce").fillna(0)).sort_values("_v")
    out = {}
    for c, a, b in zip(df["CNPJ_CIA"], df[tot], df[tes] if tes else [None] * len(df)):
        try: n = float(a) - (float(b) if b not in (None, "") and b == b else 0)
        except (TypeError, ValueError): continue
        if n > 0: out[c] = n  # a última versão (maior VERSAO) fica
    return out

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

DA_RE = r"(?i)deprecia|amortiza|exaust"

def da_flows(z, kind, year):
    """Depreciação, amortização e exaustão (DFC método indireto, contas 6.01.01.xx) -> {(cnpj, DT_INI_EXERC, ORDEM): valor}.
    Consolidado com fallback individual por empresa; versão mais recente."""
    cols = ["CNPJ_CIA", "DT_REFER", "VERSAO", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_INI_EXERC", "CD_CONTA", "DS_CONTA", "VL_CONTA"]
    out, got = {}, set()
    for ci in ("con", "ind"):
        df = read(z, f"{kind}_cia_aberta_DFC_MI_{ci}_{year}.csv", None, cols)
        if df.empty: continue
        df = df[df["CD_CONTA"].str.startswith("6.01.01.") & df["DS_CONTA"].fillna("").str.contains(DA_RE) & ~df["CNPJ_CIA"].isin(got)]
        df = df[~df["DS_CONTA"].str.contains(r"(?i)des[aá]gio|ágio|custo de capta|juros|arrendamento financeiro|direito de uso.*juros")]
        df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce")
        df = df[df["VERSAO"] == df.groupby(["CNPJ_CIA", "DT_REFER"])["VERSAO"].transform("max")]
        last = df.groupby("CNPJ_CIA")["DT_REFER"].transform("max")
        df = df[df["DT_REFER"] == last]
        v = pd.to_numeric(df["VL_CONTA"], errors="coerce") * df["ESCALA_MOEDA"].map({"MIL": 1000.0}).fillna(1.0)
        for c, ini, o, x in zip(df["CNPJ_CIA"], df["DT_INI_EXERC"], df["ORDEM_EXERC"], v):
            if x == x: out[(c, ini, o)] = out.get((c, ini, o), 0.0) + abs(x)
        got |= set(df["CNPJ_CIA"])
    return out

def dividends_declared(z, year):
    """Dividendos + JCP declarados no exercício (DMPL: contas 5.04.xx de dividendos/JCP, sem prescritos; coluna do patrimônio da controladora)."""
    out = {}
    for ci in ("con", "ind"):
        df = read(z, f"dfp_cia_aberta_DMPL_{ci}_{year}.csv")
        if df.empty: continue
        df = df[(df["ORDEM_EXERC"] == "ÚLTIMO") & (df["COLUNA_DF"] == "Patrimônio Líquido") & df["CD_CONTA"].str.match(r"^5\.04\.\d+$")
                & df["DS_CONTA"].fillna("").str.contains(r"(?i)dividend|juros sobre (?:o )?capital|jcp")
                & ~df["DS_CONTA"].fillna("").str.contains(r"(?i)prescri|revers|IRRF")
                & ~df["CNPJ_CIA"].isin(set(out))]
        df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce")
        df = df[df["VERSAO"] == df.groupby("CNPJ_CIA")["VERSAO"].transform("max")]
        v = pd.to_numeric(df["VL_CONTA"], errors="coerce") * df["ESCALA_MOEDA"].map({"MIL": 1000.0}).fillna(1.0)
        acc, fix = {}, {}
        for c, k, x in zip(df["CNPJ_CIA"], df["CD_CONTA"], v):
            if x != x: continue
            acc[c] = acc.get(c, 0.0) - x  # deduções vêm negativas
            if k in ("5.04.06", "5.04.07"): fix[c] = fix.get(c, 0.0) - x
        acc = {c: (fix[c] if fix.get(c) else x) for c, x in acc.items()}  # contas padrão (dividendos, JCP); outras só sem elas
        out.update(acc)
    return out

CAD = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"

def cancelamentos():
    """CNPJ -> motivo do cancelamento do registro na CVM (falência, incorporação, OPA…), do cadastro de companhias abertas."""
    r = requests.get(CAD, timeout=120)
    if r.status_code != 200: return {}
    df = pd.read_csv(io.BytesIO(r.content), sep=";", encoding="latin1", dtype=str)
    df = df[df["SIT"].fillna("").str.upper().str.startswith("CANCEL")]
    return {c: str(m).strip() for c, m in zip(df["CNPJ_CIA"], df["MOTIVO_CANCEL"]) if m == m and str(m).strip()}

def nao_fin(ds305):
    """Empresa não financeira: a conta 3.05 da DRE é "Resultado Antes do Resultado Financeiro…" (banco/seguradora usa outra)."""
    return "Financeiro" in (ds305 or "")

def divida_liquida(bal):
    """Dívida líquida = empréstimos e financiamentos (2.01.04 + 2.02.01) − caixa e aplicações (1.01.01 + 1.01.02)."""
    return (bal.get("2.01.04") or 0) + (bal.get("2.02.01") or 0) - (bal.get("1.01.01") or 0) - (bal.get("1.01.02") or 0)

def pivot(df, flt):
    d = df[flt]
    return {(c, k): v for c, k, v in zip(d["CNPJ_CIA"], d["CD_CONTA"], d["v"])}

FCA_ANOS = 5  # o FCA é entregue só quando muda: junta os últimos anos (a entrega mais recente de cada empresa vale)

def tickers(cache, year, anos=FCA_ANOS, ativos=True):
    """Ticker negociado hoje -> CNPJ da companhia. Fonte única: cadastro FCA da CVM (valor mobiliário).
    ativos=False: também os códigos que deixaram de ser negociados (empresas que saíram da bolsa; anos = quantos FCA anuais ler).
    Usado também por build_fund.py."""
    out, seen = {}, set()
    for y in range(year, year - anos, -1):  # do mais novo ao mais velho
        z = get_zip(cache, "FCA", y)
        if not z: continue
        vm = read(z, f"fca_cia_aberta_valor_mobiliario_{y}.csv")
        if vm.empty: continue
        vm = vm[~vm["CNPJ_Companhia"].isin(seen)]  # empresa já coberta por entrega mais nova
        vm = vm[vm["Versao"].astype(int) == vm.groupby("CNPJ_Companhia")["Versao"].transform(lambda v: v.astype(int).max())]
        for t, c, fim in zip(vm["Codigo_Negociacao"], vm["CNPJ_Companhia"], vm["Data_Fim_Negociacao"]):
            t = str(t).strip().upper()
            if t != "NAN" and 4 < len(t) <= 7 and (fim != fim or not ativos) and t not in out: out[t] = c
        seen |= set(vm["CNPJ_Companhia"])
    # algumas empresas informam só parte dos códigos (ex.: só a unit): as outras classes da mesma raiz (4 letras)
    # são da mesma companhia quando a raiz aponta para um único CNPJ no FCA
    raiz = {}
    for t, c in out.items(): raiz.setdefault(t[:4], set()).add(c)
    for r, cs in raiz.items():
        if len(cs) == 1:
            for n in ("3", "4", "5", "6", "7", "8", "11"): out.setdefault(r + n, next(iter(cs)))
    return out


def main(outdir, cache):
    os.makedirs(cache, exist_ok=True)
    today = date.today()
    fy = today.year - 1
    dfp = get_zip(cache, "DFP", fy)
    if dfp is None or len(read(dfp, f"dfp_cia_aberta_DRE_con_{fy}.csv", ["3.01"])) < 100:
        fy -= 1; dfp = get_zip(cache, "DFP", fy)
    dfpn = {n: get_zip(cache, "DFP", fy - n) for n in range(1, 6)}  # exercícios anteriores (crescimento 1 a 5 anos)
    itr = get_zip(cache, "ITR", fy + 1)
    print(f"DFP {fy} / {fy-5}..{fy-1}, ITR {fy+1}", flush=True)

    # --- DFP (exercício fy e fy-5)
    dre_f = stmts(dfp, "dfp", fy, "DRE", DRE_C)
    FY = pivot(dre_f, (dre_f["ORDEM_EXERC"] == "ÚLTIMO"))
    ds305 = {c: s for c, k, s in zip(dre_f["CNPJ_CIA"], dre_f["CD_CONTA"], dre_f["DS_CONTA"]) if k == "3.05"}
    FYN = {}
    for n, z in dfpn.items():
        dre_n = stmts(z, "dfp", fy - n, "DRE", ["3.01", "3.11", "3.11.01"]) if z else pd.DataFrame()
        FYN[n] = pivot(dre_n, dre_n["ORDEM_EXERC"] == "ÚLTIMO") if len(dre_n) else {}
    bal_f = pd.concat([stmts(dfp, "dfp", fy, "BPA", BPA_C), stmts(dfp, "dfp", fy, "BPP", BPP_C)])
    BALF = pivot(bal_f, bal_f["ORDEM_EXERC"] == "ÚLTIMO")
    DA_F = {c: v for (c, ini, o), v in da_flows(dfp, "dfp", fy).items() if o == "ÚLTIMO"}
    DIV_F = dividends_declared(dfp, fy)
    # --- ITR do ano corrente
    YTD, YTDP, BALI, refI, DA_Y, DA_YP = {}, {}, {}, {}, {}, {}
    if itr:
        dre_i = stmts(itr, "itr", fy + 1, "DRE", DRE_C)
        last = dre_i.groupby("CNPJ_CIA")["DT_REFER"].max()
        dre_i = dre_i[dre_i["DT_REFER"] == dre_i["CNPJ_CIA"].map(last)]
        YTD = pivot(dre_i, (dre_i["ORDEM_EXERC"] == "ÚLTIMO") & (dre_i["DT_INI_EXERC"] == f"{fy+1}-01-01"))
        YTDP = pivot(dre_i, (dre_i["ORDEM_EXERC"] == "PENÚLTIMO") & (dre_i["DT_INI_EXERC"] == f"{fy}-01-01"))
        refI = last.to_dict()
        da_i = da_flows(itr, "itr", fy + 1)
        DA_Y = {c: v for (c, ini, o), v in da_i.items() if o == "ÚLTIMO" and ini == f"{fy+1}-01-01"}
        DA_YP = {c: v for (c, ini, o), v in da_i.items() if o == "PENÚLTIMO" and ini == f"{fy}-01-01"}
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
    tick2cnpj = tickers(cache, today.year)
    try:  # só papéis negociados (lista da B3 do snapshot anterior): as classes deduzidas pela raiz que não existem saem
        listed = set(json.load(open(os.path.join(outdir, "b3_listed.json")))["tickers"])
        if len(listed) > 200: tick2cnpj = {t: c for t, c in tick2cnpj.items() if t in listed}
    except Exception:
        pass

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
        a = DA_F.get(cnpj)
        if has_itr and a is not None and cnpj in DA_Y and cnpj in DA_YP: a = a + DA_Y[cnpj] - DA_YP[cnpj]
        flow["da"] = a
        return flow, bal, ref

    g0 = lambda D, c, k: D.get((c, k)) not in (None, 0)  # 3.11.01 = 0: empresa sem a linha da controladora preenchida
    rows, cache_co = {}, {}
    for t, cnpj in tick2cnpj.items():
        if (cnpj, "3.01") not in FY: continue
        if cnpj not in cache_co: cache_co[cnpj] = acc(cnpj)
        flow, bal, ref = cache_co[cnpj]
        fin = not nao_fin(ds305.get(cnpj))
        rev, gross, ebit, ni = flow["3.01"], flow["3.03"], flow["3.05"], flow["3.11.01"] if g0(FY, cnpj, "3.11.01") else flow["3.11"]
        ebit_adj = (gross + (flow["3.04.01"] or 0) + (flow["3.04.02"] or 0)) if gross is not None and not fin else None
        assets, eq = bal["1"], bal["2.03"]
        cash = (bal["1.01.01"] or 0) + (bal["1.01.02"] or 0)
        dl = divida_liquida(bal)
        sh = shares.get(cnpj)
        div = lambda a, b, m=1.0: round(a / b * m, 4) if a is not None and b not in (None, 0) else None
        r = {"cnpj": cnpj, "ref": ref, "fin": fin,
             "_rev": rev, "_ebit": None if fin else ebit, "_ebit_adj": ebit_adj, "_ni": ni, "_assets": assets, "_eq": eq,
             "_netdebt": None if fin else dl, "_shares": sh,
             "roe": div(ni, eq, 100) if eq and eq > 0 else None, "roa": div(ni, assets, 100),
             "lpa": div(ni, sh), "vpa": div(eq, sh)}
        if not fin:
             inv = (assets or 0) - (bal["2.01.02"] or 0) - cash
             r.update({"mbruta": div(gross, rev, 100), "mebit": div(ebit, rev, 100), "mebit_adj": div(ebit_adj, rev, 100),
                       "mliq": div(ni, rev, 100), "liqcorr": div(bal["1.01"], bal["2.01"]),
                       "dlpl": div(dl, eq) if eq and eq > 0 else None, "dlebit": div(dl, ebit) if ebit and ebit > 0 else None,
                       "roic": div(ebit, inv, 100) if inv > 0 else None, "roic_adj": div(ebit_adj, inv, 100) if inv > 0 else None})
             # EBITDA = EBIT (3.05, 12 meses) + depreciação/amortização (DFC, 12 meses); Dív. líq./EBITDA só com EBITDA positivo
             ebitda = ebit + flow["da"] if ebit is not None and flow.get("da") is not None else None
             r.update({"_ebitda": ebitda, "dlebitda": div(dl, ebitda) if ebitda and ebitda > 0 else None})
        # payout do último exercício (DFP): dividendos + JCP declarados ÷ lucro da controladora
        dv, nfy = DIV_F.get(cnpj), FY.get((cnpj, "3.11.01")) if g0(FY, cnpj, "3.11.01") else FY.get((cnpj, "3.11"))
        if dv and dv > 0 and nfy and nfy > 0: r["payout"] = round(dv / nfy * 100, 2)
        # crescimento médio por ano (CAGR) em n anos: exercício fy vs fy-n (receita de banco/seguradora não é comparável)
        for n, FN in FYN.items():
            for key, k in (("cresc", "3.01"), ("lucro", "3.11.01")):
                a, b = FY.get((cnpj, k)), FN.get((cnpj, k))
                if k == "3.11.01" and not (a and b): a, b = FY.get((cnpj, "3.11")), FN.get((cnpj, "3.11"))
                if a and b and a > 0 and b > 0 and not (fin and key == "cresc"): r[f"{key}{n}a"] = round(((a / b) ** (1 / n) - 1) * 100, 2)
        rows[t] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if v is not None}
    save(os.path.join(outdir, "cvm.json"), "cvm", rows, {"fy": fy, "itr_year": fy + 1})
    print(f"CVM: {len(rows)} tickers ({len(cache_co)} empresas)")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data", sys.argv[2] if len(sys.argv) > 2 else "/tmp/cvmraw")
