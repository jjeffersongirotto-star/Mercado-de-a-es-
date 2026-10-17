"""Barato/Caro: configuração e conta do valor justo (fonte única). O site recebe FAIR em /api/data → `fair` e faz a mesma
conta em app.js → fairOf (e lpaRef = lpa_ref); o chat usa fair() daqui. Explicação ao usuário: painel ⓘ → Glossário → Barato/Caro."""
import statistics

FAIR = {
    "ke": 14.0,        # custo de capital (% ao ano) do Gordon: bancos e seguradoras
    "g": 5.0,          # crescimento de longo prazo (% ao ano) do Gordon
    "pvp_min": 5,      # P/VP do setor só com pelo menos 5 empresas no subsetor
    "pvp_sub": ["Exploração de Imóveis", "Holdings Diversificadas"],  # holdings e imobiliárias: VPA × P/VP mediano do subsetor
    "teto": 2.0,       # LPA médio: ano com lucro maior que 2× a mediana dos outros conta pela metade
    # LPA de referência (Brasil): média de 3 anos (ln3); se ela der prejuízo, a de 5 anos (ln5); sem média, o de 12 meses
    "lpa_anos": [3, 5],
    # sem valor justo: texto da célula (card, CSV, chat) e versão curta (widget do app); o motivo fica no detalhe
    "zero": 0.5,       # |margem| abaixo disso (%) = 0%: preço no valor justo, sem sinal, verde (site, chat, CSV e widget)
    "rot": {"prej": ["Prejuízo recorrente", "Prej."], "sem": ["Sem valor justo", "s/ VJ"]},
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


def margem(j, p):
    """Barato/Caro em %: (justo ÷ preço − 1) × 100; o que arredonda para 0% vira 0 (FAIR["zero"], mesma regra de app.js → fairOf)."""
    x = (j / p - 1) * 100
    return 0.0 if abs(x) < FAIR["zero"] else x


def lpa_ref(r, b, lpa, br):
    """LPA de referência -> (lpa, janela): Brasil = média de 3 anos (ln3 × VPA); se der prejuízo, a de 5 anos (ln5 × VPA) quando
    positiva; sem média de 3 anos, o de 12 meses. Exterior = 12 meses. janela: "3a", "5a", "12m" ou None (sem dado)."""
    if not br: return lpa, ("12m" if lpa is not None else None)
    if r.get("ln3") is None: return lpa, ("12m" if lpa is not None else None)
    l3 = r["ln3"] * b
    if l3 > 0 or r.get("ln5") is None: return l3, "3a"
    return (r["ln5"] * b, "5a") if r["ln5"] > 0 else (l3, "3a")


def rotulo(motivo):
    """Texto da célula sem valor justo: prejuízo nas médias (3 e 5 anos) = "Prejuízo recorrente"; resto = "Sem valor justo"."""
    return FAIR["rot"]["prej" if motivo.startswith("Prejuízo médio") else "sem"]


def fair(r, val, rows):
    """-> (valor justo, %, método) ou (None, motivo, None). r = linha de /api/data; val(r, k) = valor exibido; rows = todas (P/VP do setor).
    Método com a janela do LPA quando não é a padrão: "Barsi · média 5a", "Graham · LPA 12m". Texto da célula sem valor: rotulo(motivo)."""
    p, b, br = val(r, "preco"), val(r, "vpa"), r.get("cur") == "BRL"
    if not (p and p > 0): return None, "Sem preço", None
    if (r.get("st") or {}).get("vpa") == "red": return None, "Dados divergentes entre as fontes", None  # consenso (mesma regra de fairOf)
    if b is None: return None, "Sem VPA", None
    if b <= 0: return None, "Patrimônio negativo", None
    l, w = lpa_ref(r, b, val(r, "lpa"), br)
    if l is not None and l < 0:
        if w == "12m": return None, "Prejuízo nos últimos 12 meses", None
        return None, "Prejuízo médio nos últimos 3 e 5 anos" if r.get("ln5") is not None else "Prejuízo médio nos últimos 3 anos", None
    tag = lambda m: m + (" · média 5a" if w == "5a" else "")
    if br and r.get("fin"):
        roe = r.get("roe3")
        if roe is None: return None, "Sem ROE de 3 anos na CVM", None
        j = b * (roe - FAIR["g"]) / (FAIR["ke"] - FAIR["g"])
        if j <= 0: return None, "ROE abaixo do crescimento", None
        return j, margem(j, p), tag("Gordon")
    if br and r.get("subsetor") in FAIR["pvp_sub"]:
        pv = [x for x in (val(o, "pvp") for o in rows if o.get("subsetor") == r.get("subsetor")) if x and x > 0]
        if len(pv) < FAIR["pvp_min"]: return None, "Poucas empresas no setor", None
        j = b * statistics.median(pv)
        return j, margem(j, p), tag("P/VP do setor")
    if br and r.get("seg") in FAIR["barsi_seg"] and r.get("dpsm"):  # sem histórico de proventos: segue no Graham
        j = r["dpsm"] / (FAIR["barsi_taxa"] / 100)
        return j, margem(j, p), tag("Barsi")
    if l is None: return None, "Sem LPA" if not br else "Sem lucro de 3 anos na CVM nem LPA de 12 meses", None
    if l == 0: return None, "Lucro zero", None
    j = (22.5 * l * b) ** 0.5
    return j, margem(j, p), "Graham" + (" · média 5a" if w == "5a" else " · LPA 12m" if br and w == "12m" else "")
