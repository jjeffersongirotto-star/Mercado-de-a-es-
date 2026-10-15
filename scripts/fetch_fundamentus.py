"""Snapshot Fundamentus (cópia diária usada pelo servidor quando o site do Fundamentus falha). Uso: fetch_fundamentus.py <dir_saida>"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import requests
import fundamentus
from snaputil import save, UA

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "data"
    r = requests.get(fundamentus.URL, headers=UA, timeout=(10, 60)); r.raise_for_status()
    rows = fundamentus.parse(r.content)
    if len(rows) < 300: sys.exit(f"Fundamentus: só {len(rows)} papéis")
    save(os.path.join(outdir, "fundamentus.json"), "fundamentus", rows)
    print(f"Fundamentus: {len(rows)} papéis")
