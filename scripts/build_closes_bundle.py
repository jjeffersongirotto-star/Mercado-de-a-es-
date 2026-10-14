#!/usr/bin/env python3
"""Junta o histórico COTAHIST (history4/*.json.gz) num único arquivo history4_all.json.gz:
diário dos últimos 6 anos + mensal completo + proventos ([data, valor]) + ISIN por papel. O servidor carrega este arquivo de uma vez ao iniciar
(antes eram ~360 downloads: 'Comparar tudo' ficava minutos aquecendo após cada reinício)."""
import glob, gzip, json, os, sys, time
D = sys.argv[1]
cut = time.time() - 6.2 * 365 * 86400
out = {}
for f in sorted(glob.glob(os.path.join(D, "history4", "*.json.gz"))):
    h = json.loads(gzip.decompress(open(f, "rb").read()))
    d = h.get("d") or {}; i0 = next((i for i, t in enumerate(d.get("t") or []) if t >= cut), len(d.get("t") or []))
    out[os.path.basename(f)[:-8]] = {"isin": h.get("isin"), "d": {"t": d["t"][i0:], "c": d["c"][i0:], "at": d.get("at", "")}, "m": {"t": h["m"]["t"], "c": h["m"]["c"]},
                                       "divs": [[x[0], x[1]] for x in h.get("divs") or []]}
open(os.path.join(D, "history4_all.json.gz"), "wb").write(gzip.compress(json.dumps(out, separators=(",", ":")).encode(), 6))
print("bundle:", len(out), "papéis")
