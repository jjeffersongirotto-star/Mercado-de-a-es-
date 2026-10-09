"""Testes do valor exibido no consenso. Rodar: python -m pytest tests/ (ou python tests/test_consensus.py)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from consensus import decide, equal, apply_row, _clusters
SRC = ["si", "i10", "tv", "cvm", "ddm", "yf"]

def run(values):
    return decide({SRC[i]: v for i, v in enumerate(values)})

def approx(a, b): return abs(a - b) < 1e-3

def test_half_group_wins():          # regra 2
    v, st, names, meta = run([1, 1, 2, 4]); assert approx(v, 1) and st == "amb" and meta == {"t": "half"}
def test_two_different_priority():   # 2 fontes divergentes -> fonte de maior prioridade (si > i10)
    v, st, _, meta = run([1, 3]); assert v == 1 and st is None and meta == {"t": "pri", "src": "si"}
    v, st, _, meta = decide({"tv": 5, "fund": 9}); assert v == 9 and meta["src"] == "fund"
    v, st, _, meta = decide({"yf": 5, "i10": 9}); assert v == 9 and meta["src"] == "i10"
    v, st, _, meta = decide({"si": 5, "cvm": 9}); assert v == 9 and meta["src"] == "cvm"
def test_weighted_singletons():      # regra 4
    v, st, _, meta = run([1, 1, 2, 4, 6]); assert approx(v, 2.8) and st == "red" and meta["t"] == "w"
def test_weighted_two_groups():      # regra 4: 0,4×1 + 0,4×3 + 0,2×7 = 3,0
    v, st, _, meta = run([1, 1, 3, 3, 7]); assert approx(v, 3.0) and meta["t"] == "w"
def test_two_halves_tie():           # regra 2 empata -> regra 4 (50/50)
    v, st, _, meta = run([1, 1, 3, 3]); assert approx(v, 2) and st == "red" and meta["t"] == "w"
def test_all_different_three():      # regra 3
    v, st, _, meta = run([1, 2, 4]); assert approx(v, 7 / 3) and meta["t"] == "avg"
def test_majority_unchanged():       # regra 1
    v, st, names, meta = run([5, 5, 5, 9]); assert v == 5 and st == "amb" and meta is None
def test_fund_preferred_in_majority():
    v, st, _, _ = decide({"fund": 2.0, "si": 2.0, "tv": 9.0}); assert v == 2.0 and st == "amb"

# --- tolerância única de 10% ---
def test_tolerance_edges():
    assert equal(10, 9) and equal(9, 10)            # 1 ≤ 10% de 10
    assert not equal(10, 8.99)                       # 1,01 > 1,0
    assert equal(0, 0) and equal(-5, -4.5) and not equal(-5, -4.4)
    assert not equal(0.1, -0.1) and not equal(0, 0.01) and not equal(-0.001, 0.001)
    assert equal(100, 90.0000000001) and not equal(100, 89.99)
def test_clique_required():                          # 10 ~ 9,2 ~ 8,5 mas 10 ≠ 8,5 -> sem grupo de 3
    v, st, names, meta = decide({"si": 10, "i10": 9.2, "tv": 8.5}); assert st == "amb" and len(names) == 2
def test_tie_prefers_fund_group():
    g = _clusters([("si", 9), ("i10", 9.3), ("fund", 5), ("tv", 5.2)]); assert sorted(s for s, _ in g) == ["fund", "tv"]
    g = _clusters([("si", 9), ("i10", 9.8), ("tv", 5), ("cvm", 5.1)]); assert sorted(s for s, _ in g) == ["cvm", "tv"]  # mais apertado
def test_axia3_dy():                                 # metade (2/4) -> 3,32 âmbar
    v, st, names, meta = decide({"fund": 2.71, "si": 3.32, "i10": 3.32, "tv": 7.98})
    assert approx(v, 3.32) and st == "amb" and meta["t"] == "half" and sorted(names) == ["i10", "si"]
def test_bbas3_mliq():                               # todos diferentes -> média 5,52
    v, st, _, meta = decide({"si": 4.66, "i10": 3.71, "tv": 8.19}); assert approx(v, 5.52) and st == "red" and meta["t"] == "avg"
def test_bbdc4_mliq():                               # 2/3 maioria
    v, st, names, meta = decide({"si": 8.20, "i10": 8.11, "tv": 13.69}); assert approx(v, 8.155) and st == "amb" and meta is None
# --- EBIT ajustado vota junto com o Fundamentus ---
def test_axia3_roic_adjusted():
    vals = {"fund": 3.25, "si": -7.20, "cvm": 4.62, "i10": -0.30, "tv": 6.91, "ddm": 4.62}
    v, st, names, meta = decide(vals, adj_vals={"cvm": 3.2459, "ddm": 3.25})
    assert v == 3.25 and st == "amb" and meta["t"] == "half" and sorted(meta["aj"]) == ["cvm", "ddm"] and sorted(names) == ["cvm", "ddm", "fund"]
def test_adjusted_not_used_when_standard_better():  # padrão já forma maioria com o Fundamentus
    v, st, names, meta = decide({"fund": 10, "si": 10.2, "cvm": 10.1}, adj_vals={"cvm": 10.0})
    assert v == 10 and st is None and meta is None
def test_adjusted_only_with_fund():                  # ajustado não serve para formar grupo sem o Fundamentus
    v, st, names, meta = decide({"fund": 1, "si": 5, "cvm": 9}, adj_vals={"cvm": 5})
    assert st == "red" and meta["t"] == "avg" and "aj" not in meta
def test_apply_row_ebit():
    r = apply_row({"S": {"fund": {"roic": 3.25}, "si": {"roic": -7.2}, "cvm": {"roic": 4.62}, "i10": {"roic": -0.3}, "tv": {"roic": 6.91}, "ddm": {"roic": 4.62}},
                   "A": {"cvm": {"roic_adj": 3.2459}, "ddm": {"roic_adj": 3.25}}}, [("roic", 1.0, True)], None)
    assert r["v"]["roic"] == 3.25 and r["st"]["roic"] == "amb" and r["cm"]["roic"]["aj"] == ["cvm", "ddm"]

# --- piso absoluto, exclusão por indicador, bancos ---
def test_floor():
    assert equal(0.5, 0.75, 0.3) and not equal(0.5, 0.85, 0.3) and not equal(0.5, 0.75)
    assert equal(0, 0.2, 0.3) and not equal(-0.1, 0.1, 0.3)          # sinais opostos nunca iguais
    v, st, names, meta = decide({"si": 0.59, "tv": 0.49, "i10": 0.59, "cvm": 0.47}, key="roa"); assert st is None
    v, st, names, meta = decide({"si": 0.59, "tv": 0.49, "i10": 0.59, "cvm": 0.47}, key="pl"); assert st == "red"  # sem piso: 2 grupos de metade
    v, st, _, _ = decide({"si": 2.0, "tv": 2.9, "i10": 2.5}, key="cresc5a"); assert st is None
def test_no_vote_roic_tv():
    r = apply_row({"S": {"tv": {"roic": 7.55}, "i10": {"roic": 22.01}}}, [("roic", 1.0, True)], None)
    assert r["v"]["roic"] == 22.01 and "roic" not in r["st"] and r["xv"]["roic"] == ["tv"]
def test_no_vote_cresc_fund():
    r = apply_row({"S": {"fund": {"cresc5a": -2.33}, "si": {"cresc5a": 12.83}, "tv": {"cresc5a": 12.83}}}, [("cresc5a", 1.0, True)], None)
    assert r["v"]["cresc5a"] == 12.83 and "cresc5a" not in r["st"] and r["xv"]["cresc5a"] == ["fund"]
def test_no_vote_only_source_kept():
    r = apply_row({"S": {"yf": {"roa": 3.0}}}, [("roa", 1.0, True)], None); assert r["v"]["roa"] == 3.0 and "xv" not in r
def test_bank_marks():
    S = {"fund": {"pebit": 5, "pl": 5}, "si": {"pebit": 9, "pl": 9}, "tv": {"pebit": 20, "pl": 20}}
    r = apply_row({"S": S, "fin": True}, [("pebit", 1.0, True), ("pl", 1.0, True)], None); assert r["bk"] == ["pebit"] and r["st"]["pebit"] == "red"
    r = apply_row({"S": S}, [("pebit", 1.0, True)], None); assert "bk" not in r
def test_financial_detection():
    from consensus import financial_tickers
    rows = [{"ticker": "BBAS3", "nome": "BCO BRASIL S.A.", "subsetor": "Bancos Diversificados"}, {"ticker": "RPAD3", "nome": "ALFA HOLDINGS S.A.", "subsetor": "Bancos"},
            {"ticker": "RPAD5", "nome": "ALFA HOLDINGS S.A.", "subsetor": None}, {"ticker": "BBSE3", "nome": "BB SEGURIDADE", "subsetor": "Seguradoras"},
            {"ticker": "PETR4", "nome": "PETROBRAS", "subsetor": "Petróleo"}, {"ticker": "B3SA3", "nome": "B3 S.A.", "subsetor": "Dados Financeiros e Bolsas de Valores"}]
    assert financial_tickers(rows) == {"BBAS3", "RPAD3", "RPAD5", "BBSE3"}

def test_evebitda_20pct():
    v, st, _, _ = decide({"fund": 15.0, "tv": 12.65, "i10": 12.76}, key="evebitda"); assert st is None   # 2,35 ≤ 20% de 15
    v, st, _, _ = decide({"fund": 15.0, "tv": 12.65, "i10": 12.76}, key="evebit"); assert st == "amb"   # 10%
    assert not equal(10, 7.9, (0.2, 0))

def test_bank_two_sources_dark_blue():
    from consensus import apply_row
    r = {"S": {"si": {"mebit": 10.0}, "tv": {"mebit": 30.0}}, "fin": True}
    apply_row(r, [("mebit", 1.0, True)], lambda a, b, t: True)
    assert r["bk"] == ["mebit"] and "mebit" not in r["st"] and r["cm"]["mebit"]["t"] == "pri"

if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
