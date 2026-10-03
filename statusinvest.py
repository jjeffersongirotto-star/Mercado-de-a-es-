"""Coleta da busca avançada de ações do Status Invest.

Usado pelo servidor (tentativa ao vivo) e pelo workflow do GitHub Actions
(scripts/fetch_statusinvest.py), que salva um snapshot diário na branch `data`.
Formato canônico: CSV do próprio export (separador ';', decimal ',').
"""
import json
import time

import requests

BASE = "https://statusinvest.com.br"
SEARCH = json.dumps({"Sector": "", "SubSector": "", "Segment": "", "my_range": "-20;100"})

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Ch-Ua": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}
REFERER = BASE + "/acoes/busca-avancada"

# Cabeçalho do CSV de export  <->  chave do JSON paginado
COLS = [
    ("TICKER", "ticker"), ("PRECO", "price"), ("DY", "dy"), ("P/L", "p_l"), ("P/VP", "p_vp"),
    ("P/ATIVOS", "p_ativo"), ("MARGEM BRUTA", "margembruta"), ("MARGEM EBIT", "margemebit"),
    ("MARG. LIQUIDA", "margemliquida"), ("P/EBIT", "p_ebit"), ("EV/EBIT", "ev_ebit"),
    ("DIVIDA LIQUIDA / EBIT", "dividaliquidaebit"), ("DIV. LIQ. / PATRI.", "dividaliquidapatrimonioliquido"),
    ("PSR", "p_sr"), ("P/CAP. GIRO", "p_capitalgiro"), ("P. AT CIR. LIQ.", "p_ativocirculante"),
    ("LIQ. CORRENTE", "liquidezcorrente"), ("ROE", "roe"), ("ROA", "roa"), ("ROIC", "roic"),
    ("PATRIMONIO / ATIVOS", "pl_ativo"), ("PASSIVOS / ATIVOS", "passivo_ativo"), ("GIRO ATIVOS", "giroativos"),
    ("CAGR RECEITAS 5 ANOS", "receitas_cagr5"), ("CAGR LUCROS 5 ANOS", "lucros_cagr5"),
    (" LIQUIDEZ MEDIA DIARIA", "liquidezmediadiaria"), (" VPA", "vpa"), (" LPA", "lpa"),
    (" PEG Ratio", "peg_ratio"), (" VALOR DE MERCADO", "valormercado"),
    ("NOME", "companyname"), ("SETOR", "sectorname"),
]


def _session():
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)
    try:  # cookies de sessão (ex.: Cloudflare) antes da chamada de dados
        s.get(REFERER, timeout=(10, 20))
    except requests.RequestException:
        pass
    return s


def _xhr_headers(accept):
    return {"Referer": REFERER, "Origin": BASE, "X-Requested-With": "XMLHttpRequest", "Accept": accept,
            "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin"}


def fetch_export_csv(session=None, timeout=(10, 45)):
    s = session or _session()
    r = s.get(BASE + "/category/advancedsearchresultexport", params={"search": SEARCH, "CategoryType": 1},
              headers=_xhr_headers("text/csv,application/octet-stream,*/*;q=0.8"), timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"export HTTP {r.status_code}")
    text = r.content.decode("utf-8", errors="replace").lstrip("\ufeff")
    if not text.upper().startswith("TICKER"):
        raise RuntimeError("export: resposta inesperada")
    return text


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        t = f"{v:.6f}".rstrip("0").rstrip(".")
        return t.replace(".", ",")
    return str(v).replace(";", ",").replace("\n", " ")


def fetch_paginated_csv(session=None, timeout=(10, 45)):
    """Endpoint JSON da busca avançada, convertido para o mesmo formato CSV (com NOME e SETOR)."""
    s = session or _session()
    rows, page, take = [], 0, 1000
    while True:
        r = s.get(BASE + "/category/advancedsearchresultpaginated",
                  params={"search": SEARCH, "orderColumn": "", "isAsc": "", "page": page, "take": take,
                          "CategoryType": 1},
                  headers=_xhr_headers("application/json, text/javascript, */*; q=0.01"), timeout=timeout)
        if r.status_code != 200:
            raise RuntimeError(f"paginated HTTP {r.status_code}")
        d = r.json()
        lst = d.get("list") or []
        rows.extend(lst)
        total = d.get("totalResults") or len(lst)
        if not lst or len(rows) >= total or page > 20:
            break
        page += 1
        time.sleep(0.5)
    if not rows:
        raise RuntimeError("paginated: lista vazia")
    lines = [";".join(c for c, _ in COLS)]
    for it in rows:
        lines.append(";".join(_fmt(it.get(k)) for _, k in COLS))
    return "\n".join(lines)


def fetch_live():
    """Tenta export CSV e depois o JSON paginado. Retorna (csv_text, método)."""
    s = _session()
    errs = []
    for name, fn in (("export", fetch_export_csv), ("paginated", fetch_paginated_csv)):
        try:
            return fn(s), name
        except Exception as e:  # noqa
            errs.append(f"{name}: {e}")
    raise RuntimeError("; ".join(errs))


def parse_csv(text, num_fn):
    lines = [l for l in text.splitlines() if l.strip()]
    hdr = lines[0].lstrip("\ufeff").split(";")
    if "TICKER" not in hdr[0].upper():
        raise RuntimeError("CSV Status Invest inesperado")
    out = {}
    for l in lines[1:]:
        p = l.split(";")
        rec = {}
        for i in range(1, len(hdr)):
            raw = p[i] if i < len(p) else ""
            rec[hdr[i]] = raw.strip() or None if hdr[i] in ("NOME", "SETOR") else num_fn(raw)
        out[p[0].strip().upper()] = rec
    return out
