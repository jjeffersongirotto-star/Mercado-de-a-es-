"""Barato/Caro: configuração e conta do valor justo (fonte única). O site recebe FAIR em /api/data → `fair` e faz a mesma
conta em app.js → fairOf; o chat usa fair() daqui. Explicação ao usuário: painel ⓘ → Glossário → Barato/Caro."""
import statistics

FAIR = {
    "ke": 14.0,        # custo de capital (% ao ano) do Gordon: bancos e seguradoras
    "g": 5.0,          # crescimento de longo prazo (% ao ano) do Gordon
    "pvp_min": 5,      # P/VP do setor só com pelo menos 5 empresas no subsetor
    "pvp_sub": ["Exploração de Imóveis", "Holdings Diversificadas"],  # holdings e imobiliárias: VPA × P/VP mediano do subsetor
    "teto": 2.0,       # LPA médio: ano com lucro maior que 2× a mediana dos outros conta pela metade
    # Barsi (preço teto): dividendo médio por ação dos últimos anos completos (B3, 3 a 5 anos) ÷ taxa; segmentos oficiais da B3
    "barsi_taxa": 6.0,
    "barsi_anos": [3, 5],
    "barsi_seg": ["Energia Elétrica", "Água e Saneamento", "Gás", "Exploração de Rodovias"],
    # alertas do card (⚠️): não mudam o percentual
    "al_dlebitda": 3.5,  # dívida líquida ÷ EBITDA acima disso (CVM)
    "al_dy": 15.0,       # dividend yield (%) acima disso
    "al_payout": 100.0,  # payout (%) do último exercício acima disso (CVM)
}


def dps_medio(anos, y1):
    """Dividendo médio por ação: anos = {"2021": dps, ...} (B3, anos completos já ajustados), y1 = último ano completo. Conta os
    anos desde o primeiro com provento (ano sem provento = 0) dentro dos últimos barsi_anos[1]; None com menos de barsi_anos[0]."""
    if not anos: return None
    ys = sorted(int(y) for y in anos)
    lo = max(min(ys), y1 - FAIR["barsi_anos"][1] + 1)
    n = y1 - lo + 1
    if n < FAIR["barsi_anos"][0]: return None
    return round(sum(anos.get(str(y), 0.0) for y in range(lo, y1 + 1)) / n, 6)


def alertas(r, dy):
    """-> lista de (tipo, valor) dos alertas do card. r = linha de /api/data (r['al'] da CVM); dy = DY exibido."""
    a, out = r.get("al") or {}, []
    if a.get("dlebitda") is not None and a["dlebitda"] > FAIR["al_dlebitda"]: out.append(("divida", a["dlebitda"]))
    if dy is not None and dy > FAIR["al_dy"]: out.append(("dy", dy))
    if a.get("payout") is not None and a["payout"] > FAIR["al_payout"]: out.append(("payout", a["payout"]))
    return out


def lucro_medio(ni, n=3):
    """Lucro médio dos últimos n anos com teto (ano exagerado conta pela metade); None sem os n anos."""
    x = [v for v in (ni or [])[-n:] if v]  # 0 = conta não encontrada no balanço (sem dado)
    if len(x) != n: return None
    out = []
    for i, v in enumerate(x):
        m = statistics.median([y for j, y in enumerate(x) if j != i])
        out.append(v / 2 if v > 0 and v > FAIR["teto"] * abs(m) else v)
    return sum(out) / n


def fair(r, val, rows):
    """-> (valor justo, %, método) ou (None, motivo, None). r = linha de /api/data; val(r, k) = valor exibido; rows = todas (P/VP do setor)."""
    p, b, br = val(r, "preco"), val(r, "vpa"), r.get("cur") == "BRL"
    if not (p and p > 0): return None, "Sem preço", None
    if (r.get("st") or {}).get("vpa") == "red": return None, "Dados divergentes entre as fontes", None  # consenso (mesma regra de fairOf)
    if b is None: return None, "Sem VPA", None
    if b <= 0: return None, "Patrimônio negativo", None
    lpa = val(r, "lpa")
    if br and lpa is not None and lpa < 0: return None, "Prejuízo nos últimos 12 meses", None
    if br and r.get("fin"):
        roe = r.get("roe3")
        if roe is None: return None, "Sem ROE de 3 anos na CVM", None
        j = b * (roe - FAIR["g"]) / (FAIR["ke"] - FAIR["g"])
        if j <= 0: return None, "ROE abaixo do crescimento", None
        return j, (j / p - 1) * 100, "Gordon"
    if br and r.get("subsetor") in FAIR["pvp_sub"]:
        pv = [x for x in (val(o, "pvp") for o in rows if o.get("subsetor") == r.get("subsetor")) if x and x > 0]
        if len(pv) < FAIR["pvp_min"]: return None, "Poucas empresas no setor", None
        j = b * statistics.median(pv)
        return j, (j / p - 1) * 100, "P/VP do setor"
    if br and r.get("seg") in FAIR["barsi_seg"] and r.get("dpsm"):  # sem histórico de proventos: segue no Graham
        j = r["dpsm"] / (FAIR["barsi_taxa"] / 100)
        return j, (j / p - 1) * 100, "Barsi"
    l = (r["ln3"] * b if r.get("ln3") is not None else None) if br else lpa
    if l is None: return None, "Sem lucro de 3 anos na CVM" if br else "Sem LPA", None
    if l <= 0: return None, "Prejuízo médio nos últimos 3 anos" if br else "Prejuízo nos últimos 12 meses", None
    j = (22.5 * l * b) ** 0.5
    return j, (j / p - 1) * 100, "Graham"
