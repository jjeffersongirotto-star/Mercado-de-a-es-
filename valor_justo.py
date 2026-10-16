"""Barato/Caro: configuração e conta do valor justo (fonte única). O site recebe FAIR em /api/data → `fair` e faz a mesma
conta em app.js → fairOf; o chat usa fair() daqui. Explicação ao usuário: painel ⓘ → Glossário → Barato/Caro."""
import statistics

FAIR = {
    "ke": 14.0,        # custo de capital (% ao ano) do Gordon: bancos e seguradoras
    "g": 5.0,          # crescimento de longo prazo (% ao ano) do Gordon
    "pvp_min": 5,      # P/VP do setor só com pelo menos 5 empresas no subsetor
    "pvp_sub": ["Exploração de Imóveis", "Holdings Diversificadas"],  # holdings e imobiliárias: VPA × P/VP mediano do subsetor
    "teto": 2.0,       # LPA médio: ano com lucro maior que 2× a mediana dos outros conta pela metade
}


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
    l = (r["ln3"] * b if r.get("ln3") is not None else None) if br else lpa
    if l is None: return None, "Sem lucro de 3 anos na CVM" if br else "Sem LPA", None
    if l <= 0: return None, "Prejuízo médio nos últimos 3 anos" if br else "Prejuízo nos últimos 12 meses", None
    j = (22.5 * l * b) ** 0.5
    return j, (j / p - 1) * 100, "Graham"
