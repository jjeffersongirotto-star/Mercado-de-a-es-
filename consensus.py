"""Consenso entre fontes ('Todos'): cluster majoritário dentro dos limiares por indicador.
- valor exibido: o do Fundamentus se ele estiver no cluster; senão a mediana do cluster;
- 'red'  : nenhum cluster com maioria (> metade das fontes com valor);
- 'amb'  : maioria encontrada, mas alguma fonte discorda;
- 'adj'  : o Fundamentus usa EBIT AJUSTADO (lucro bruto − desp. vendas − desp. G&A); se ele diverge do
           cluster padrão mas bate com a versão ajustada (Dados de Mercado/CVM), marca como diferença de
           definição em vez de erro."""
from statistics import median

EBIT_KEYS = {"pebit", "evebit", "roic", "mebit"}
SIGN_FROM = {"dlebit": "dlpl"}  # indicador -> indicador que define o sinal (dívida líquida)
PRIORITY = ["fund", "si", "cvm", "i10", "tv", "ddm", "yf"]  # desempate de clusters de mesmo tamanho

_MASKS = {}
def _masks(n):
    if n not in _MASKS:
        _MASKS[n] = sorted(range(1, 1 << n), key=lambda m: -bin(m).count("1"))
    return _MASKS[n]

def _clusters(items, thr, divergente):
    """Maior grupo de fontes que concordam ENTRE SI (todos os pares dentro do limiar)."""
    n = len(items)
    adj = [sum(1 << j for j in range(n) if not divergente(items[i][1], items[j][1], thr)) for i in range(n)]
    full = (1 << n) - 1
    if all(a == full for a in adj): return list(items)
    best, size = None, 0
    for m in _masks(n):
        c = bin(m).count("1")
        if c < size: break
        if all((adj[i] & m) == m for i in range(n) if m >> i & 1):
            cl = [items[i] for i in range(n) if m >> i & 1]
            names = [s for s, _ in cl]; vs = [v for _, v in cl]
            score = ("fund" in names, -min((PRIORITY.index(s) if s in PRIORITY else 99) for s in names), -(max(vs) - min(vs)))
            if best is None or score > best[0]: best = (score, cl)
            size = c
    return best[1]

def _groups(items, thr, divergente):
    """Particiona as fontes em grupos que concordam entre si (maior grupo primeiro, repetidamente)."""
    rest, out = list(items), []
    while rest:
        g = _clusters(rest, thr, divergente)
        out.append(g)
        names = {s for s, _ in g}
        rest = [it for it in rest if it[0] not in names]
    return out

def decide(vals, thr, divergente, adj_vals=None):
    """vals: {fonte: valor}. -> (valor, status|None, fontes_do_grupo_vencedor, meta)
    1) grupo com maioria (> n/2): Fundamentus se estiver nele, senão a mediana do grupo ('amb' se alguém discorda);
    2) grupo com exatamente n/2 (≥ 2) e único: igual à maioria ('amb', meta t=half);
    3) todos diferentes (nenhum grupo ≥ 2): média simples de todos ('red', meta t=avg);
    4) senão: média ponderada — cada grupo repetido = mediana × tamanho/n; singletons juntos = média × qtd/n ('red', meta t=w)."""
    items = [(s, v) for s, v in vals.items() if v is not None]
    n = len(items)
    if n == 0: return None, None, [], None
    if n == 1: return items[0][1], None, [items[0][0]], None
    groups = _groups(items, thr, divergente)
    g1 = groups[0]
    names = [s for s, _ in g1]
    fund = vals.get("fund")
    half_tie = len(groups) > 1 and 2 * len(groups[1]) == n
    winner = 2 * len(g1) > n or (2 * len(g1) == n and len(g1) >= 2 and not half_tie)
    # Fundamentus fora do grupo vencedor (ou sem vencedor): é diferença de definição de EBIT?
    if adj_vals and fund is not None and (not winner or "fund" not in names):
        if any(a is not None and not divergente(fund, a, thr) for a in adj_vals.values()):
            rest = [(s, v) for s, v in items if s != "fund"]
            if len(rest) == 1:
                return rest[0][1], "adj", [rest[0][0]], None
            if rest:
                cl2 = _clusters(rest, thr, divergente)
                if 2 * len(cl2) > len(rest):
                    return round(median(v for _, v in cl2), 4), "adj", [s for s, _ in cl2], None
    if winner:
        val = fund if "fund" in names else round(median(v for _, v in g1), 4)
        if 2 * len(g1) == n:
            return val, "amb", names, {"t": "half"}
        return val, ("amb" if len(g1) < n else None), names, None
    if len(g1) < 2:  # regra 3: todos diferentes
        return round(sum(v for _, v in items) / n, 4), "red", [], {"t": "avg"}
    # regra 4: ponderada
    parts, singles = [], []
    for g in groups:
        if len(g) >= 2: parts.append([round(len(g) / n, 4), round(median(v for _, v in g), 4), [s for s, _ in g]])
        else: singles.append(g[0])
    if singles:
        parts.append([round(len(singles) / n, 4), round(sum(v for _, v in singles) / len(singles), 4), [s for s, _ in singles]])
    val = round(sum(w * x for w, x, _ in parts), 4)
    return val, "red", [], {"t": "w", "w": parts}

def apply_row(row, fields, divergente):
    """row['S'] = {fonte: {chave: valor}}; row['A'] = {fonte: {chave_adj: valor}} (EBIT ajustado).
    Preenche row['v'] (consenso), row['st'] {chave: red|amb|adj}, row['ag'] {chave: [fontes]} e row['src']."""
    S = row.get("S") or {}
    A = row.get("A") or {}
    v, st, ag, src, ex, cm = {}, {}, {}, {}, {}, {}
    for key, thr, cmp in fields:
        vals = {s: d.get(key) for s, d in S.items() if d.get(key) is not None}
        if not cmp:  # não comparado (cotação, liquidez, valores absolutos): primeira fonte disponível
            for s in PRIORITY:
                if s in vals: v[key] = vals[s]; src[key] = s if s != "fund" else None; break
            else: v[key] = None
            src = {k: x for k, x in src.items() if x}
            continue
        adj = {s: d.get(key + "_adj") for s, d in A.items() if d.get(key + "_adj") is not None} if key in EBIT_KEYS else None
        dropped = {}
        if key in SIGN_FROM:
            # Dív.Líq/EBIT tem o sinal da dívida líquida (com EBIT positivo): o consenso de Dív.Líq/PL decide o sinal;
            # fontes com sinal oposto (ex.: Status Invest não conta aplicações de seguradora como caixa) saem da votação
            ref = v.get(SIGN_FROM[key])
            ebit_pos = (v.get("pebit") or 0) > 0 or (v.get("mebit") or 0) > 0
            if ref is not None and abs(ref) >= 0.02 and st.get(SIGN_FROM[key]) != "red" and ebit_pos:
                dropped = {s_: x for s_, x in vals.items() if abs(x) >= 0.05 and (x > 0) != (ref > 0)}
                if dropped and len(dropped) < len(vals):
                    vals = {s_: x for s_, x in vals.items() if s_ not in dropped}
                else:
                    dropped = {}
        val, status, names, meta = decide(vals, thr, divergente, adj)
        if meta: cm[key] = meta
        if dropped:
            ex[key] = sorted(dropped)
            if status is None or status == "red" and len(vals) == 1: status = "amb"
            if not names: names = list(vals)
        v[key] = val
        if status:
            st[key] = status
            if names: ag[key] = names
        if val is not None and "fund" not in vals and len(vals) >= 1:
            src[key] = names[0] if len(names) == 1 else ("si" if names == ["si"] else "multi")
    row["v"], row["st"], row["ag"], row["src"] = v, st, ag, src
    if ex: row["ex"] = ex
    if cm: row["cm"] = cm
    return row
