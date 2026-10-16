#!/usr/bin/env python3
"""Notícias sobre Luiz Barsi para a aba Notícias -> OUT/noticias.json (fonte única da aba; o servidor só repassa o arquivo).
Mantém os itens já publicados (resumos escritos à mão ficam como estão), acrescenta os novos do RSS do Bing Notícias
(título com "Barsi", até DIAS dias) com a imagem de capa da própria página (og:image) e o resumo da página (og:description, curto),
tira os links que deixaram de abrir (HTTP 404/410) e fica com os MAX mais recentes. ~20 pedidos por execução (rotina, bloco rápido).
Uso: fetch_noticias.py OUT_DIR"""
import html, json, os, re, sys, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse
import requests

TEMA, MAX, DIAS = "Luiz Barsi", 10, 120
RSS = "https://www.bing.com/news/search?q=%22Luiz+Barsi%22&format=rss&setlang=pt-BR&cc=BR"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}
FONTES = {"estadao.com.br": "Estadão", "seudinheiro.com": "Seu Dinheiro", "infomoney.com.br": "InfoMoney", "exame.com": "Exame",
          "valor.globo.com": "Valor Econômico", "moneytimes.com.br": "Money Times", "einvestidor": "Estadão E-Investidor",
          "bpmoney.com.br": "BP Money", "suno.com.br": "Suno", "opetroleo.com.br": "O Petróleo", "cnnbrasil.com.br": "CNN Brasil",
          "istoedinheiro.com.br": "IstoÉ Dinheiro", "forbes.com.br": "Forbes Brasil", "investnews.com.br": "InvestNews"}


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
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def main(out):
    p = os.path.join(out, "noticias.json")
    try: old = json.load(open(p, encoding="utf-8"))
    except Exception: old = {}
    itens = old.get("itens") or []
    ok = []
    for it in itens:  # link morto sai; erro de rede ou bloqueio mantém
        r = get(it["url"])
        if r is not None and r.status_code in (404, 410): continue
        ok.append(it)
    urls = {it["url"] for it in ok}
    r = get(RSS); novos = 0
    if r is not None and r.status_code == 200:
        agora = datetime.now(timezone.utc)
        for x in re.findall(r"<item>(.*?)</item>", r.text, re.S):
            g = lambda tag: (lambda m: html.unescape(m.group(1)).strip() if m else "")(re.search(rf"<{tag}>(.*?)</{tag}>", x, re.S))
            tit, lk, pub = g("title"), g("link"), g("pubDate")
            url = (parse_qs(urlparse(lk).query).get("url") or [lk])[0]
            try: dt = parsedate_to_datetime(pub)
            except Exception: continue
            if "barsi" not in tit.lower() or (agora - dt).days > DIAS or url in urls: continue
            pg = get(url)
            if pg is None or pg.status_code != 200: continue
            img = meta(pg.text, "og:image")
            ok.append({"titulo": curto(meta(pg.text, "og:title") or tit, 160), "data": dt.date().isoformat(), "fonte": fonte(url),
                       "resumo": curto(meta(pg.text, "og:description") or g("description")), "url": url,
                       "img": img if img and img.startswith("https://") else None})
            urls.add(url); novos += 1; time.sleep(1)
    ok.sort(key=lambda it: it.get("data") or "0000", reverse=True)
    data = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tema": TEMA, "itens": ok[:MAX]}
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"noticias: {len(data['itens'])} itens ({novos} novos)")
    return 0 if data["itens"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
