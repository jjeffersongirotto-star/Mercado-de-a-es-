"""Carrega snapshots gerados na máquina da rotina diária (branch `data` no GitHub -> fallback arquivo local data/)."""
import json, logging, os, time
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

log = logging.getLogger("screener.snap")
BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get("SNAPSHOT_RAW_BASE",
                     "https://raw.githubusercontent.com/jjeffersongirotto-star/Mercado-de-a-es-/data/data")
TZ = ZoneInfo("America/Sao_Paulo")
_mem = {}  # nome -> (instante, payload, origem)

def when_sp(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "?"

def load(name, max_mem_age=1800):
    """-> (payload|None, descrição). Cache em memória por 30 min para não baixar a cada reapply."""
    c = _mem.get(name)
    if c and time.time() - c[0] < max_mem_age:
        return c[1], c[2]
    payload, origin = None, None
    try:
        r = requests.get(f"{RAW}/{name}.json", timeout=(10, 60))
        if r.status_code == 200:
            payload, origin = r.json(), "snapshot GitHub"
        else:
            origin = f"GitHub HTTP {r.status_code}"
    except Exception as e:
        origin = f"GitHub {type(e).__name__}"
    if payload is None:
        p = os.path.join(BASE, "data", f"{name}.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                payload = json.load(fh)
            origin = "arquivo local"
    if payload is None:
        _mem[name] = (time.time(), None, f"sem snapshot ({origin})")
        return None, f"sem snapshot ({origin})"
    desc = f"{origin} de {when_sp(payload.get('fetched_at', ''))}"
    _mem[name] = (time.time(), payload, desc)
    return payload, desc

def invalidate():
    _mem.clear()
