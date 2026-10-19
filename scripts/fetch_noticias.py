#!/usr/bin/env python3
"""Notícias da aba Notícias -> OUT/noticias.json (fonte única da aba e das notícias que os modelos leem; o servidor só repassa o arquivo).
Dois temas, cada item com "tema":
- "barsi": matérias sobre Luiz Barsi (RSS do Bing Notícias, título com "Barsi"), até MAX_BARSI, com imagem de capa (og:image) e
  resumo da própria página; links que deixam de abrir (HTTP 404/410) saem.
- "mercado": notícias de mercado em português das FONTES (RSS de cada uma; a que não responder fica de fora nesse dia; Bing
  Notícias em português é a reserva), só as que citam empresas ou palavras de mercado (MERCADO_RX). Cada item ganha "t"
  (tickers da B3 citados: código escrito no texto ou nome popular de nomes_populares.json), "tf" (empresas de fora citadas, "us:META")
  e "m" (mercados: "br" e/ou países de fora — classificar); os modelos da Previsão (B3) usam só as do mercado "br" (modelos.noticias_itens). Ficam as dos últimos DIAS dias, até MAX_MERCADO; marcos escolhidos à mão em noticias_marcos.json
  (fatos importantes antes da coleta diária) entram sempre.
Uso: fetch_noticias.py OUT_DIR   (rotina diária, bloco rápido; ~60 pedidos por execução)"""
import html, json, os, re, sys, time, unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse
import requests
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))

MAX_BARSI, MAX_MERCADO, DIAS, OG_MAX = 20, 300, 120, 40
RSS_BARSI = "https://www.bing.com/news/search?q=%22Luiz+Barsi%22&format=rss&setlang=pt-BR&cc=BR"
# Fontes de mercado (todas em português do Brasil): nome -> endereços do RSS, na ordem de tentativa
FONTES_RSS = {
    "Valor Econômico": ["https://pox.globo.com/rss/valor/", "https://valor.globo.com/rss/valor/"],
    "InfoMoney": ["https://www.infomoney.com.br/mercados/feed/", "https://www.infomoney.com.br/feed/"],
    "Reuters (Investing.com Brasil)": ["https://br.investing.com/rss/news_25.rss", "https://br.investing.com/rss/news.rss"],
    "Exame": ["https://exame.com/invest/mercados/feed/", "https://exame.com/feed/"],
    "Agência Brasil": ["https://agenciabrasil.ebc.com.br/rss/economia/feed.xml"],
}
RSS_RESERVA = "https://www.bing.com/news/search?q=Ibovespa+OR+%22a%C3%A7%C3%B5es%22+OR+B3&format=rss&setlang=pt-BR&cc=BR"
MERCADO_RX = re.compile(r"\b(ibovespa|bolsa|b3|a[cç][aãoõ]es|a[cç][aã]o|selic|copom|d[oó]lar|infla[cç][aã]o|ipca|juros|dividendo|provento|jcp|"
                        r"balan[cç]o|lucro|preju[ií]zo|trimestre|ipo|opa|recompra|fato relevante|cvm|mercado financeiro)\b", re.I)
VOC = json.load(open(os.path.join(os.path.dirname(HERE), "vocabulario.json"), encoding="utf-8"))["noticias"]
AMBIGUOS = set(VOC["nomes_ambiguos"])  # nomes que também são palavras comuns
import snapshots  # noqa: E402  (arquivo de notícias: começa da cópia da branch data)
import tradingview  # noqa: E402  (países do site: nome, índice e bolsa de cada um — sinais do mercado de fora)
PAISES = [c for c in tradingview.COUNTRIES if c != "br"]
SINAIS = {c: [tradingview.COUNTRIES[c][1].lower(), tradingview.YAHOO[c][2].lower(), *[b.lower() for b in tradingview.BOLSA[c].split("/")],
              *VOC["exterior"].get(c, [])] for c in PAISES}  # palavras de cada mercado de fora; Brasil: VOC["brasil"]
TICKER_RX = re.compile(r"\b([A-Z]{4}(?:3|4|5|6|11))\b")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}
FONTES = {"estadao.com.br": "Estadão", "seudinheiro.com": "Seu Dinheiro", "infomoney.com.br": "InfoMoney", "exame.com": "Exame",
          "valor.globo.com": "Valor Econômico", "moneytimes.com.br": "Money Times", "einvestidor": "Estadão E-Investidor",
          "bpmoney.com.br": "BP Money", "suno.com.br": "Suno", "opetroleo.com.br": "O Petróleo", "cnnbrasil.com.br": "CNN Brasil",
          "istoedinheiro.com.br": "IstoÉ Dinheiro", "forbes.com.br": "Forbes Brasil", "investnews.com.br": "InvestNews",
          "investing.com": "Reuters (Investing.com Brasil)", "agenciabrasil.ebc.com.br": "Agência Brasil"}


def get(url):
    for i in range(3):
        try: return requests.get(url, headers=UA, timeout=25, allow_redirects=True)
        except Exception: time.sleep(2 + 3 * i)
    return None


def meta(page, prop):
    for rx in (rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']+)', rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{prop}["\']'):
        m = re.search(rx, page, re.I)
        if m: return html.unescape(m.group(1)).strip()
    return None


def fonte(url):
    h = urlparse(url).netloc.lower().removeprefix("www.")
    return next((v for k, v in FONTES.items() if k in url), h)


def curto(t, n=220):
    t = re.sub(r"<[^>]+>", " ", html.unescape(t or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def chave(t):
    """título normalizado (sem acento, minúsculo, só letras e números): a mesma notícia em duas fontes entra uma vez só."""
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()[:90]


def itens_rss(texto):
    """-> [(título, link, data UTC, resumo, imagem do RSS ou None)] de um RSS."""
    out = []
    for x in re.findall(r"<item\b.*?>(.*?)</item>", texto, re.S):
        g = lambda tag: (lambda m: html.unescape(re.sub(r"^<!\[CDATA\[|\]\]>$", "", m.group(1).strip())).strip() if m else "")(re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", x, re.S))
        lk = g("link"); lk = (parse_qs(urlparse(lk).query).get("url") or [lk])[0]
        try: dt = parsedate_to_datetime(g("pubDate"))
        except Exception: continue
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        im = re.search(r'<(?:media:content|media:thumbnail|enclosure)[^>]+url=["\']([^"\']+)', x)
        out.append((curto(g("title"), 160), lk, dt, curto(g("description")), im.group(1) if im else None))
    return out


def empresas(rows, pop):
    """-> (tickers da B3 do site, [(nome, ticker)]): nome popular e apelidos de nomes_populares.json (raiz de 4 letras da B3),
    um ticker por empresa (o do universo do site); nomes que também são palavras comuns (AMBIGUOS: Vale, Rumo, Oi, Vivo…) só valem
    com o ticker escrito no texto; nomes de até 4 letras (Itaú, WEG) só com a grafia exata."""
    tk = {r["ticker"] for r in rows if re.fullmatch(r"[A-Z]{4}(3|4|5|6|11)", r.get("ticker") or "")}
    por_raiz = {}
    for r in rows:
        t = r.get("ticker") or ""
        if t in tk and (r.get("k1") or t[:4] not in por_raiz): por_raiz[t[:4]] = t
    nomes = []
    for raiz, t in por_raiz.items():
        e = pop.get(raiz)
        if not e: continue
        for n in [e] if isinstance(e, str) else [e.get("n")] + list(e.get("aliases") or []):
            if not n or n in AMBIGUOS: continue
            nomes.append((n, t, len(n) <= 4))  # nome curto (Itaú, WEG): só com a grafia exata
    nomes.sort(key=lambda x: -len(x[0]))
    return tk, nomes


def empresas_fora(pop, raizes_b3):
    """[(nome, "país:ticker", exato)] das empresas de fora de nomes_populares.json (EUA sem prefixo ou "us:", outros com o prefixo do país)."""
    out = []
    for k, e in pop.items():
        if k.startswith("_"): continue
        c, t = k.split(":", 1) if ":" in k else ("us", k)
        if c not in PAISES or (":" not in k and (k in raizes_b3 or re.search(r"\d", k))): continue  # sem prefixo: raiz da B3 ou de BDR (M1TA, B3SA) não é de fora
        for n in [e] if isinstance(e, str) else [e.get("n")] + list(e.get("aliases") or []):
            if n and n not in AMBIGUOS: out.append((n, f"{c}:{t}", len(n) <= 4))
    out.sort(key=lambda x: -len(x[0]))
    return out


def _tem(low, palavra):
    return re.search(r"(?<![\w&])" + re.escape(palavra) + r"(?![\w&])", low) is not None


def classificar(texto, tk, nomes, fora):
    """-> {t: tickers da B3, tf: empresas de fora ("us:META"), m: mercados ("br", "us", "jp"…)}. Fora = empresa de fora citada ou palavra do
    mercado de lá (país, índice, bolsa, VOC["exterior"]); Brasil = empresa da B3, palavra do Brasil (VOC["brasil"]) ou nenhum sinal de fora."""
    t = marcar(texto, tk, nomes); low = (texto or "").lower(); tf = set()
    for n, x, exato in fora:
        if re.search(r"(?<![\w])" + re.escape(n if exato else n.lower()) + r"(?![\w])", texto if exato else low): tf.add(x)
    m = {x.split(":")[0] for x in tf} | {c for c, ws in SINAIS.items() if any(_tem(low, w) for w in ws)}
    if t or any(_tem(low, w) for w in VOC["brasil"]) or not m: m.add("br")
    return {"t": t, "tf": sorted(tf), "m": sorted(m, key=lambda c: (c != "br", c))}


def marcar(texto, tk, nomes):
    """tickers da B3 citados no texto: código escrito (PETR4) ou nome popular (Petrobras, Itaú…), sem diferenciar maiúsculas."""
    achou = {m for m in TICKER_RX.findall(texto or "") if m in tk}
    low = (texto or "").lower()
    for n, t, exato in nomes:
        if re.search(r"(?<![\w])" + re.escape(n if exato else n.lower()) + r"(?![\w])", texto if exato else low): achou.add(t)
    return sorted(achou)


def arquivo(out, merc):
    """Arquivo de notícias que só cresce (OUT/noticias_arq.json; a aba guarda só DIAS dias): as de mercado ficam para sempre, no formato
    curto que os modelos leem (modelos.noticias_itens: data, empresas da B3 `t`, mercados `m`, texto). O Adaptativo aprende mais com o tempo."""
    p = os.path.join(out, "noticias_arq.json")
    try: A = json.load(open(p, encoding="utf-8"))
    except Exception:
        try: A = snapshots.load("noticias_arq")[0] or {}
        except Exception: A = {}
    L = A.get("itens") or []; vistos = {i["u"] for i in L}; n0 = len(L)
    for it in merc:
        if it.get("marco") or it["url"] in vistos: continue
        L.append({"d": it["data"], "t": it.get("t") or [], "m": it.get("m") or ["br"], "x": curto(f"{it['titulo']}. {it.get('resumo') or ''}", 300), "u": it["url"]})
        vistos.add(it["url"])
    L.sort(key=lambda i: i["d"])
    json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "itens": L}, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"noticias_arq: {len(L)} no arquivo ({len(L) - n0} novas)")


def main(out):
    p = os.path.join(out, "noticias.json")
    try: old = json.load(open(p, encoding="utf-8"))
    except Exception: old = {}
    agora = datetime.now(timezone.utc)
    velhos = old.get("itens") or []
    for it in velhos: it.setdefault("tema", "barsi")  # itens de antes dos temas: eram todos do Barsi
    # empresas do site (nomes e tickers) para marcar "t"
    try:
        from snaputil import APP_API
        rows = (requests.get(APP_API, timeout=180).json() or {}).get("rows") or []
    except Exception as e:
        rows = []; print("noticias: sem /api/data (notícias ficam sem empresas):", type(e).__name__)
    pop = json.load(open(os.path.join(os.path.dirname(HERE), "nomes_populares.json"), encoding="utf-8"))
    tk, nomes = empresas(rows, pop); fora = empresas_fora(pop, {t[:4] for t in tk})
    cl = lambda it: classificar(f"{it['titulo']}. {it.get('resumo') or ''}", tk, nomes, fora)
    # Barsi: como antes (link morto sai)
    barsi = []
    for it in [i for i in velhos if i["tema"] == "barsi"]:
        r = get(it["url"])
        if r is not None and r.status_code in (404, 410): continue
        barsi.append(it)
    urls = {it["url"] for it in velhos}; nb = 0
    r = get(RSS_BARSI)
    if r is not None and r.status_code == 200:
        for tit, url, dt, desc, _ in itens_rss(r.text):
            if "barsi" not in tit.lower() or (agora - dt).days > DIAS or url in urls: continue
            pg = get(url)
            if pg is None or pg.status_code != 200: continue
            img = meta(pg.text, "og:image")
            barsi.append({"tema": "barsi", "titulo": curto(meta(pg.text, "og:title") or tit, 160), "data": dt.date().isoformat(), "fonte": fonte(url),
                          "resumo": curto(meta(pg.text, "og:description") or desc), "url": url, "img": img if img and img.startswith("https://") else None})
            urls.add(url); nb += 1; time.sleep(1)
    # Mercado: fontes em português (+ reserva), só notícias de mercado
    merc = [i for i in velhos if i["tema"] == "mercado" and not i.get("marco") and (agora.date() - datetime.fromisoformat(i["data"]).date()).days <= DIAS]
    vistos = {chave(i["titulo"]) for i in merc} | {i["url"] for i in merc}
    novos, og, por_fonte = [], 0, {}
    feeds = [(n, u) for n, us in FONTES_RSS.items() for u in us] + [("Bing Notícias", RSS_RESERVA)]
    ok_fonte = set()
    for nome, u in feeds:
        if nome in ok_fonte: continue  # já respondeu pelo endereço anterior
        r = get(u)
        if r is None or r.status_code != 200 or "<item" not in r.text: continue
        ok_fonte.add(nome); n0 = len(novos)
        for tit, url, dt, desc, img in itens_rss(r.text):
            if (agora - dt).days > DIAS or url in vistos or chave(tit) in vistos: continue
            it = {"tema": "mercado", "titulo": tit, "data": dt.date().isoformat(), "fonte": fonte(url) if nome == "Bing Notícias" else nome,
                  "resumo": desc, "url": url, "img": img if img and img.startswith("https://") else None}
            it.update(cl(it))
            if not it["t"] and not it["tf"] and not MERCADO_RX.search(f"{tit}. {desc}"): continue  # fora do assunto mercado
            novos.append(it)
            vistos |= {url, chave(tit)}
        por_fonte[nome] = len(novos) - n0
    for it in novos:  # imagem e resumo da própria página, quando o RSS não traz (limite por execução)
        if it["img"] or og >= OG_MAX: continue
        pg = get(it["url"]); og += 1
        if pg is not None and pg.status_code == 200:
            img = meta(pg.text, "og:image"); it["img"] = img if img and img.startswith("https://") else None
            it["resumo"] = it["resumo"] or curto(meta(pg.text, "og:description"))
        time.sleep(0.5)
    for it in merc: it.update(cl(it))  # as já guardadas também: mesma regra de hoje (mercado e empresas)
    merc = sorted(merc + novos, key=lambda i: i["data"], reverse=True)[:MAX_MERCADO]
    try: marcos = json.load(open(os.path.join(HERE, "noticias_marcos.json"), encoding="utf-8"))["itens"]
    except Exception as e: marcos = []; print("noticias: sem marcos:", e)
    for m in marcos:
        m.update({"tema": "mercado", "marco": True}); m.update(cl(m))
    for it in barsi: it.update({"m": ["br"], "tf": []}); it.setdefault("t", [])
    itens = sorted(barsi, key=lambda i: i.get("data") or "", reverse=True)[:MAX_BARSI] + merc + marcos
    itens.sort(key=lambda i: i.get("data") or "0000", reverse=True)
    data = {"fetched_at": agora.isoformat(timespec="seconds"), "temas": {"mercado": "Mercado", "barsi": "Luiz Barsi"},
            "fontes": sorted(ok_fonte), "itens": itens}
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    arquivo(out, merc)
    print(f"noticias: {len(itens)} itens (Barsi {nb} novos; mercado {len(novos)} novos: {por_fonte}; fontes que responderam: {sorted(ok_fonte)})")
    return 0 if itens else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
