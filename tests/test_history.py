"""Testes do histórico de fora (history.py): cópia salva na branch data (history5) e junção com os dias novos.
Rodar: python tests/test_history.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import history

DAY = 86400
NOW = 1_800_000_000


def fake(calls):
    def yahoo(t, kind, rng=None, sym=None):
        calls.append((sym, kind, rng))
        t0 = NOW - (40 * DAY if rng else 12 * 365 * DAY)  # incremental: último mês; completo: 12 anos
        ts = list(range(t0, NOW, DAY))
        return {"t": ts, "c": [1.0 + i for i in range(len(ts))], "div": [[ts[0], .5], [ts[-1], .1]], "source": "Yahoo Finance"}
    return yahoo


def test_copia_completa_incremental_e_semanal():
    calls = []; history.yahoo = fake(calls)
    c = history.copy_update(None, "AAPL", NOW)
    assert [x[2] for x in calls] == [None, None] and c["ts"] == NOW  # sem cópia: baixa tudo
    assert c["d"]["t"][0] >= NOW - 3653 * DAY and len(c["m"]["t"]) > len(c["d"]["t"])  # diário: 10 anos; mensal: desde o início
    assert all(v[0] >= NOW - 3653 * DAY for v in c["d"]["div"]) and "_at" not in c["d"] and c["d"]["at"]
    calls.clear()
    assert history.copy_update(c, "AAPL", NOW + 3 * DAY) is c and not calls  # menos de 6 dias: não baixa
    n = history.copy_update(c, "AAPL", NOW + 7 * DAY)
    assert [x[2] for x in calls] == [history.INC["m"], history.INC["d"]] and n["ts"] == NOW + 7 * DAY  # semana seguinte: só o último período
    assert n["m"]["t"][0] == c["m"]["t"][0]  # junta com o que já tinha
    calls.clear(); history.copy_update(c, "AAPL", NOW + 30 * DAY)
    assert [x[2] for x in calls] == [None, None]  # mais de 25 dias parada: baixa tudo de novo


def test_nome_do_arquivo():
    assert history.fname("^GSPC") == "_GSPC" and history.fname("7203.t") == "7203.T"


def test_cache_b3_limitado():
    # histórico completo da B3 (~1,4 MB cada): LRU de H4_MAX (fora dele, b3hist lê a cópia do disco); b3full: H4F_MAX
    history._h4.clear()
    for k in range(history.H4_MAX + 10): history._h4put(f"T{k:03d}3", (0, {"k": k}))
    assert len(history._h4) == history.H4_MAX and "T0003" not in history._h4 and history._h4get(f"T{history.H4_MAX + 9:03d}3")[1] == {"k": history.H4_MAX + 9}
    history._h4b["ZZZZ3"] = (0, {"b": 1}); assert history._h4get("ZZZZ3") == (0, {"b": 1}); history._h4b.clear()  # durante all_closes
    history._h4.clear()
    assert history.H4F_MAX <= 20

if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
