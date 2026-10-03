"""Consenso entre fontes ('Todos'): grupos de valores iguais (tolerância única de 10%).
- valor exibido: o do Fundamentus se ele estiver no cluster; senão a mediana do cluster;
- 'red'  : nenhum cluster com maioria (> metade das fontes com valor);
- 'amb'  : maioria encontrada, mas alguma fonte discorda;
- EBIT: o Fundamentus usa EBIT AJUSTADO (lucro bruto − desp. vendas − desp. G&A); CVM/Dados de Mercado
           votam com o valor padrão ou o ajustado (o que formar o maior grupo) — meta 'aj'."""
from statistics import median

EBIT_KEYS = {"pebit", "evebit", "roic", "mebit"}
SIGN_FROM = {"dlebit": "dlpl"}  # indicador -> indicador que define o sinal (dívida líquida)
PRIORITY = ["fund", "si", "cvm", "i10", "tv", "ddm", "yf"]  # desempate de clusters de mesmo tamanho
RANK = ["cvm", "si", "ddm", "fund", "i10", "tv", "yf"]  # 2 fontes divergentes: exibe a de maior prioridade
# fontes fora da votação por indicador (definição própria; seguem visíveis no tooltip)
NO_VOTE = {"roic": {"tv"}, "roa": {"yf"}, "mebit": {"yf"}, "cresc5a": {"fund"}, "lucro5a": {"si"}}
# piso absoluto de tolerância (pontos percentuais), além dos 10%
FLOOR = {"roa": 0.3, "roe": 0.3, "mbruta": 0.3, "mebit": 0.3, "mliq": 0.3, "roic": 0.3, "cresc5a": 1.0, "lucro5a": 1.0}
# bancos/seguradoras: indicadores baseados em EBIT/receita não são comparáveis entre fontes
BANK_KEYS = {"roic", "evebitda", "evebit", "pebit", "mebit", "cresc5a"}

TOL = 0.10  # "iguais" se |a−b| ≤ max(10% de max(|a|,|b|), piso); sinais opostos nunca são iguais

def equal(a, b, fl=0.0):
    if a == b: return True
    if a * b < 0: return False
    return abs(a - b) <= max(TOL * max(abs(a), abs(b)), fl) + 1e-9

_MASKS = {}
def _masks(n):
    if n not in _MASKS:
        _MASKS[n] = sorted(range(1, 1 << n), key=lambda m: -bin(m).count("1"))
    return _MASKS[n]

def _score(cl):
    names = [s for s, _ in cl]; vs = [v for _, v in cl]
    return (len(cl), "fund" in names, -(max(vs) - min(vs)), -min((PRIORITY.index(s) if s in PRIORITY else 99) for s in names))

def _clusters(items, thr=None, divergente=None, fl=0.0):
    """Maior grupo de fontes iguais ENTRE SI (todos os pares dentro de 10%).
    Desempate: grupo com o Fundamentus, depois o mais apertado."""
    n = len(items)
    adj = [sum(1 << j for j in range(n) if equal(items[i][1], items[j][1], fl)) for i in range(n)]
    full = (1 << n) - 1
    if all(a == full for a in adj): return list(items)
    best, size = None, 0
    for m in _masks(n):
        c = bin(m).count("1")
        if c < size: break
        if all((adj[i] & m) == m for i in range(n) if m >> i & 1):
            cl = [items[i] for i in range(n) if m >> i & 1]
            sc = _score(cl)
            if best is None or sc > best[0]: best = (sc, cl)
            size = c
    return best[1]

def _groups(items, fl=0.0):
    """Particiona as fontes em grupos iguais entre si (maior grupo primeiro, repetidamente)."""
    rest, out = list(items), []
    while rest:
        g = _clusters(rest, fl=fl)
        out.append(g)
        names = {s for s, _ in g}
        rest = [it for it in rest if it[0] not in names]
    return out

def _best_assignment(vals, adj_vals, fl=0.0):
    """EBIT: o Fundamentus usa EBIT ajustado. Fontes com versão ajustada (CVM, Dados de Mercado) votam com o valor
    padrão OU o ajustado (cada fonte conta uma vez). Escolhe a atribuição cujo maior grupo é o maior; o ajustado
    só é aceito se a fonte cair no grupo do Fundamentus. Empate: grupo com o Fundamentus, menos fontes via ajustado, mais apertado."""
    items = [(s, v) for s, v in vals.items() if v is not None]
    cand = [s for s, a in (adj_vals or {}).items() if a is not None and vals.get(s) is not None]
    if not cand or vals.get("fund") is None:
        return items, _groups(items, fl), []
    best = None
    for m in range(1 << len(cand)):
        use = {cand[i] for i in range(len(cand)) if m >> i & 1}
        it = [(s, adj_vals[s] if s in use else v) for s, v in items]
        gs = _groups(it, fl)
        if use:
            gf = next(g for g in gs if any(s == "fund" for s, _ in g))
            if not use <= {s for s, _ in gf}: continue
        sc0 = _score(gs[0]); sc = (sc0[0], sc0[1], -len(use)) + sc0[2:]
        if best is None or sc > best[0]: best = (sc, it, gs, sorted(use))
    return best[1], best[2], best[3]

def decide(vals, thr=None, divergente=None, adj_vals=None, key=None):
    """vals: {fonte: valor}. -> (valor, status|None, fontes_do_grupo_vencedor, meta)
    1) grupo com maioria (> n/2): Fundamentus se estiver nele, senão a mediana do grupo ('amb' se alguém discorda);
    2) grupo com exatamente n/2 (≥ 2) e único: igual à maioria ('amb', meta t=half);
    3) todos diferentes (nenhum grupo ≥ 2): média simples de todos ('red', meta t=avg); com só 2 fontes,
       o valor da fonte de maior prioridade (RANK; meta t=pri);
    4) senão: média ponderada — cada grupo repetido = mediana × tamanho/n; singletons juntos = média × qtd/n ('red', meta t=w).
    meta 'aj' = fontes que concordaram com o Fundamentus via EBIT ajustado."""
    items, groups, use = _best_assignment(vals, adj_vals, FLOOR.get(key, 0.0))
    n = len(items)
    if n == 0: return None, None, [], None
    if n == 1: return items[0][1], None, [items[0][0]], None
    g1 = groups[0]
    names = [s for s, _ in g1]
    fund = vals.get("fund")
    aj = [s for s in use if s in names]
    def M(d):
        if aj: d = dict(d or {}); d["aj"] = aj
        return d or None
    half_tie = len(groups) > 1 and 2 * len(groups[1]) == n
    winner = 2 * len(g1) > n or (2 * len(g1) == n and len(g1) >= 2 and not half_tie)
    if winner:
        val = fund if "fund" in names else round(median(v for _, v in g1), 4)
        if 2 * len(g1) == n:
            return val, "amb", names, M({"t": "half"})
        return val, ("amb" if len(g1) < n else None), names, M(None)
    aj = [s for s in use]
    if len(g1) < 2 and n == 2:  # 2 fontes divergentes: a de maior prioridade
        s0 = min((s for s, _ in items), key=lambda s: RANK.index(s) if s in RANK else 99)
        return dict(items)[s0], "red", [], M({"t": "pri", "src": s0})
    if len(g1) < 2:  # regra 3: todos diferentes (3+)
        return round(sum(v for _, v in items) / n, 4), "red", [], M({"t": "avg"})
    # regra 4: ponderada
    parts, singles = [], []
    for g in groups:
        if len(g) >= 2: parts.append([round(len(g) / n, 4), round(median(v for _, v in g), 4), [s for s, _ in g]])
        else: singles.append(g[0])
    if singles:
        parts.append([round(len(singles) / n, 4), round(sum(v for _, v in singles) / len(singles), 4), [s for s, _ in singles]])
    val = round(sum(w * x for w, x, _ in parts), 4)
    return val, "red", [], M({"t": "w", "w": parts})

def apply_row(row, fields, divergente):
    """row['S'] = {fonte: {chave: valor}}; row['A'] = {fonte: {chave_adj: valor}} (EBIT ajustado).
    Preenche row['v'] (consenso), row['st'] {chave: red|amb}, row['cm'] (meta), row['ag'] {chave: [fontes]} e row['src']."""
    S = row.get("S") or {}
    A = row.get("A") or {}
    v, st, ag, src, ex, cm, xv, bk = {}, {}, {}, {}, {}, {}, {}, []
    fin = bool(row.get("fin"))
    for key, thr, cmp in fields:
        vals = {s: d.get(key) for s, d in S.items() if d.get(key) is not None}
        if not cmp:  # não comparado (cotação, liquidez, valores absolutos): primeira fonte disponível
            for s in PRIORITY:
                if s in vals: v[key] = vals[s]; src[key] = s if s != "fund" else None; break
            else: v[key] = None
            src = {k: x for k, x in src.items() if x}
            continue
        adj = {s: d.get(key + "_adj") for s, d in A.items() if d.get(key + "_adj") is not None} if key in EBIT_KEYS else None
        nv = NO_VOTE.get(key)
        if nv and any(s_ in vals for s_ in nv) and any(s_ not in nv for s_ in vals):
            xv[key] = sorted(s_ for s_ in vals if s_ in nv)
            vals = {s_: x for s_, x in vals.items() if s_ not in nv}
            if adj: adj = {s_: x for s_, x in adj.items() if s_ not in nv}
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
        val, status, names, meta = decide(vals, thr, divergente, adj, key)
        if meta: cm[key] = meta
        if dropped:
            ex[key] = sorted(dropped)
            if status is None or status == "red" and len(vals) == 1: status = "amb"
            if not names: names = list(vals)
        v[key] = val
        if fin and key in BANK_KEYS and status in ("red", "amb"): bk.append(key)
        if status:
            st[key] = status
            if names: ag[key] = names
        if val is not None and "fund" not in vals and len(vals) >= 1:
            src[key] = names[0] if len(names) == 1 else ("si" if names == ["si"] else "multi")
    row["v"], row["st"], row["ag"], row["src"] = v, st, ag, src
    if ex: row["ex"] = ex
    if cm: row["cm"] = cm
    if xv: row["xv"] = xv
    if bk: row["bk"] = bk
    return row

import re
_FIN_SUB = re.compile(r"Banc|Segur|Resseg|Serviços Financeiros", re.I)
_FIN_NAME = re.compile(r"\bBCO\b|\bBANCO\b|SEGURIDADE|SEGURO|BANESTES|BANESE", re.I)

def financial_tickers(rows):
    """Bancos/seguradoras/serviços financeiros: subsetor (Bancos, Bancos Diversificados, Seguradoras, Resseguradoras,
    Corretoras de Seguros, Serviços Financeiros Diversos) OU nome (BCO/BANCO/SEGURIDADE/SEGURO/BANESTES/BANESE);
    estende às demais classes da mesma empresa (mesma raiz de 4 letras)."""
    hit = {r["ticker"] for r in rows if _FIN_SUB.search(r.get("subsetor") or "") or _FIN_NAME.search(r.get("nome") or "")}
    roots = {t[:4] for t in hit}
    return {r["ticker"] for r in rows if r["ticker"][:4] in roots}
