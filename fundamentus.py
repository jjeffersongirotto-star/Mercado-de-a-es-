"""Fundamentus: endereço e leitura da tabela de todas as ações (fonte única para o servidor e os scripts).
Ao vivo primeiro; se falhar (certificado, bloqueio, site fora), o servidor usa a cópia diária da branch `data`
(snapshot `fundamentus`, gravado por scripts/fetch_fundamentus.py na rotina de dados)."""
import io, math
import pandas as pd
from snapshots import br_num

URL = "https://fundamentus.com.br/resultado.php"  # sem www: o certificado (15/10/2026) vale só para fundamentus.com.br


def _num(x):
    if x is None: return None
    try: f = float(x)
    except (TypeError, ValueError): return None
    return None if math.isnan(f) or math.isinf(f) else f


def parse(content):
    """bytes da página resultado.php -> {ticker: {coluna: número}}"""
    df = pd.read_html(io.StringIO(content.decode("latin-1")), decimal=",", thousands=".")[0]
    out = {}
    for _, row in df.iterrows():
        t = str(row["Papel"]).strip().upper()
        rec = {}
        for c in df.columns:
            if c == "Papel": continue
            v = row[c]
            if isinstance(v, str):
                v = br_num(v) if "%" in v else _num(v.replace(",", ".")) if v.count(".") <= 1 else br_num(v)
            rec[c] = _num(v)
        out[t] = rec
    return out
