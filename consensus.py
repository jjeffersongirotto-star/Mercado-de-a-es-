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

def decide(vals, thr, divergente, adj_vals=None):
    """vals: {fonte: valor}. -> (valor, status|None, fontes_que_concordam)"""
    items = [(s, v) for s, v in vals.items() if v is not None]
    n = len(items)
    if n == 0: return None, None, []
    if n == 1: return items[0][1], None, [items[0][0]]
    cl = _clusters(items, thr, divergente)
    names = [s for s, _ in cl]
    fund = vals.get("fund")
    majority = 2 * len(cl) > n
    # Fundamentus fora (ou sem maioria): é diferença de definição de EBIT?
    if adj_vals and fund is not None and (not majority or "fund" not in names):
        if any(a is not None and not divergente(fund, a, thr) for a in adj_vals.values()):
            rest = [(s, v) for s, v in items if s != "fund"]
            if len(rest) == 1:
                return rest[0][1], "adj", [rest[0][0]]
            if rest:
                cl2 = _clusters(rest, thr, divergente)
                if 2 * len(cl2) > len(rest):
                    return round(median(v for _, v in cl2), 4), "adj", [s for s, _ in cl2]
    if not majority:
        if fund is not None: return fund, "red", []
        # sem Fundamentus: valor REAL da fonte mais próxima da mediana (não uma média sintética; ex.: 0,66 e −0,65 -> não 0,005)
        med = median(v for _, v in items)
        pick = min(items, key=lambda it: (abs(it[1] - med), PRIORITY.index(it[0]) if it[0] in PRIORITY else 99))
        return pick[1], "red", []
    val = fund if "fund" in names else round(median(v for _, v in cl), 4)
    return val, ("amb" if len(cl) < n else None), names

def apply_row(row, fields, divergente):
    """row['S'] = {fonte: {chave: valor}}; row['A'] = {fonte: {chave_adj: valor}} (EBIT ajustado).
    Preenche row['v'] (consenso), row['st'] {chave: red|amb|adj}, row['ag'] {chave: [fontes]} e row['src']."""
    S = row.get("S") or {}
    A = row.get("A") or {}
    v, st, ag, src, ex = {}, {}, {}, {}, {}
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
        val, status, names = decide(vals, thr, divergente, adj)
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
    return row
