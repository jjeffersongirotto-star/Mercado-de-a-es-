"""TradingView scanner (endpoint público do screener, em lote). Usado ao vivo no servidor; se falhar,
cai para o snapshot da branch `data` (data/tradingview_<pais>.json) gerado pela rotina diária."""
import logging, math, time
import requests

log = logging.getLogger("screener.tv")

# id -> (mercado no scanner, nome, moeda padrão, limite por valor de mercado (None = todos))
COUNTRIES = {
    "br": ("brazil", "Brasil", "BRL", None),
    "us": ("america", "Estados Unidos", "USD", 1500),
    "gb": ("uk", "Reino Unido", "GBP", 800),
    "de": ("germany", "Alemanha", "EUR", 400),
    "pt": ("portugal", "Portugal", "EUR", None),
    "jp": ("japan", "Japão", "JPY", 1500),
}
COLS = ["name", "description", "type", "sector", "industry", "close", "change", "currency", "market_cap_basic",
        "average_volume_60d_calc", "dividends_yield_current", "price_earnings_ttm", "price_book_fq", "price_sales_current",
        "enterprise_value_ebitda_ttm", "enterprise_value_to_ebit_ttm", "ebit_ttm", "total_assets", "return_on_equity",
        "return_on_invested_capital", "return_on_assets", "gross_margin", "operating_margin", "net_margin", "current_ratio",
        "net_debt", "total_equity_fq", "total_revenue_cagr_5y", "net_income_cagr_5y", "book_value_per_share_fq",
        "earnings_per_share_diluted_ttm", "volume", "Value.Traded", "average_volume_10d_calc",
        "average_volume_30d_calc", "average_volume_90d_calc"]

def _n(x):
    try:
        f = float(x)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None

def _q(a, b):
    a, b = _n(a), _n(b)
    return a / b if a is not None and b not in (None, 0) else None

def to_vals(d):
    """Linha do scanner -> chaves do screener (mesmas unidades: % como número)."""
    px = _n(d["close"]); cur = d.get("currency") or ""
    if cur == "GBX" and px is not None:  # Londres cota em pence
        px /= 100; cur = "GBP"
    mc = _n(d["market_cap_basic"])
    pl = _n(d["price_earnings_ttm"]); l5 = _n(d["net_income_cagr_5y"])
    v = {"preco": px, "dy": _n(d["dividends_yield_current"]), "pl": pl, "pvp": _n(d["price_book_fq"]),
         "psr": _n(d["price_sales_current"]), "evebitda": _n(d["enterprise_value_ebitda_ttm"]),
         "evebit": _n(d["enterprise_value_to_ebit_ttm"]), "pebit": _q(mc, d["ebit_ttm"]), "pativo": _q(mc, d["total_assets"]),
         "roe": _n(d["return_on_equity"]), "roic": _n(d["return_on_invested_capital"]), "roa": _n(d["return_on_assets"]),
         "mbruta": _n(d["gross_margin"]), "mebit": _n(d["operating_margin"]), "mliq": _n(d["net_margin"]),
         "liqcorr": _n(d["current_ratio"]), "dlpl": _q(d["net_debt"], d["total_equity_fq"]) if (_n(d["total_equity_fq"]) or 0) > 0 else None,
         "dlebit": _q(d["net_debt"], d["ebit_ttm"]) if (_n(d["ebit_ttm"]) or 0) > 0 else None,
         "liq2m": (_n(d["average_volume_60d_calc"]) or 0) * (_n(d["close"]) or 0) or None,
         "cresc5a": _n(d["total_revenue_cagr_5y"]), "lucro5a": l5,
         "vpa": _n(d["book_value_per_share_fq"]), "lpa": _n(d["earnings_per_share_diluted_ttm"]),
         "peg": (pl / l5) if pl and l5 and pl > 0 and l5 > 0 else None,
         "patrliq": _n(d["total_equity_fq"]), "valmerc": mc}
    # volume financeiro (moeda local): dia = Value.Traded; médias = média de ações × cotação atual (aprox.)
    # dia = volume × cotação (igual ao Value.Traded do TradingView, mas sempre na moeda local; ex.: Londres em £)
    vq = _n(d.get("volume")); cl = _n(d["close"])
    v["voldia"] = vq * cl if vq is not None and cl is not None else _n(d.get("Value.Traded"))
    for k, c in (("vol10", "average_volume_10d_calc"), ("vol30", "average_volume_30d_calc"), ("vol90", "average_volume_90d_calc")):
        q = _n(d.get(c)); v[k] = q * _n(d["close"]) if q is not None and _n(d["close"]) is not None else None
        v["q_" + k] = round(q) if q is not None else None
    v["q_voldia"] = round(_n(d.get("volume"))) if _n(d.get("volume")) is not None else None
    if cur == "GBP":  # pence -> libras
        for k in ("liq2m", "voldia", "vol10", "vol30", "vol90"):  # todos calculados com a cotação em pence
            if v.get(k): v[k] /= 100
    v = {k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items() if x is not None}
    meta = {"nome": d.get("description"), "setor": d.get("sector"), "subsetor": d.get("industry"),
            "var": round(_n(d["change"]), 2) if _n(d["change"]) is not None else None, "cur": cur}
    return v, meta

def fetch(country, timeout=40):
    """-> {ticker: {"v": {...}, "m": {...}}} ao vivo."""
    market, _, _, limit = COUNTRIES[country]
    body = {"columns": COLS, "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}, "range": [0, limit or 5000]}
    if country != "br":
        body["filter"] = [{"left": "type", "operation": "equal", "right": "stock"},
                          {"left": "is_primary", "operation": "equal", "right": True},
                          {"left": "market_cap_basic", "operation": "nempty"}]
    r = requests.post(f"https://scanner.tradingview.com/{market}/scan", json=body, timeout=timeout,
                      headers={"User-Agent": "Mozilla/5.0", "Origin": "https://www.tradingview.com",
                               "Referer": "https://www.tradingview.com/"})
    r.raise_for_status()
    out = {}
    for it in r.json().get("data", []):
        d = dict(zip(COLS, it["d"]))
        t = it["s"].split(":", 1)[1]
        if t in out: continue
        v, m = to_vals(d)
        if len(v) >= 3: out[t] = {"v": v, "m": m}
    if len(out) < 10:
        raise RuntimeError(f"resposta vazia ({len(out)} papéis)")
    return out
