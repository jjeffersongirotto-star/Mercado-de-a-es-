#!/usr/bin/env python3
"""Baixa o snapshot do Status Invest e grava data/statusinvest.csv + data/statusinvest.meta.json.
Usado pelo GitHub Actions (.github/workflows/statusinvest.yml). Sai com código 1 se falhar."""
import json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import statusinvest  # noqa: E402

out_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
os.makedirs(out_dir, exist_ok=True)
try:
    text, method = statusinvest.fetch_live()
except Exception as e:
    print(f"Falhou: {e}", file=sys.stderr)
    sys.exit(1)
rows = len([l for l in text.splitlines() if l.strip()]) - 1
if rows < 100:
    print(f"Poucas linhas ({rows}); não sobrescrevendo", file=sys.stderr)
    sys.exit(1)
with open(os.path.join(out_dir, "statusinvest.csv"), "w", encoding="utf-8") as f:
    f.write(text.rstrip("\n") + "\n")
meta = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": rows, "method": method}
with open(os.path.join(out_dir, "statusinvest.meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)
print(json.dumps(meta))
