"""Testes do valor exibido no consenso. Rodar: python -m pytest tests/ (ou python tests/test_consensus.py)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from consensus import decide

EQ = lambda a, b, thr: a != b  # "divergente" só quando diferentes (valores iguais = mesmo grupo)
SRC = ["si", "i10", "tv", "cvm", "ddm", "yf"]

def run(values):
    return decide({SRC[i]: v for i, v in enumerate(values)}, 0, EQ)

def approx(a, b): return abs(a - b) < 1e-3

def test_half_group_wins():          # regra 2
    v, st, names, meta = run([1, 1, 2, 4]); assert approx(v, 1) and st == "amb" and meta == {"t": "half"}
def test_two_different_mean():       # regra 3
    v, st, _, meta = run([1, 3]); assert approx(v, 2) and st == "red" and meta["t"] == "avg"
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
    v, st, _, _ = decide({"fund": 2.0, "si": 2.0, "tv": 9.0}, 0, EQ); assert v == 2.0 and st == "amb"

if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
