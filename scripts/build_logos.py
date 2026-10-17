"""Logos das empresas da B3 (widget do app Android; AGENTS.md tabela 1.3 → "Logo da empresa"). Etapa SEMANAL da rotina.
Cadeia, por empresa (4 letras do ticker), parando na primeira que der um logo de pelo menos 32 px:
  1. favicon do site oficial (campo Pagina_Web do FCA da CVM) pelo serviço de favicons do Google;
  2. ícone do próprio site (apple-touch-icon / link rel=icon); ícones repetidos em 3+ empresas (plataforma de RI) ficam de fora;
  3. brapi (icons.brapi.dev, por ticker; sem o genérico BRAPI.svg), desenhado como quadrado arredondado;
  4. outra classe da mesma empresa; senão nada (o widget desenha as iniciais).
Ações de fora (EUA, Reino Unido, Alemanha, Portugal, Japão: as mesmas do site, snapshots tradingview_<país>) e BDRs, por site da empresa:
  site = Yahoo (yfinance, campo website) ou Wikidata (P856), guardado em logos/sites.json (90 dias) →
  1. favicon (Google) → 2. ícone do site → 3. quadrado do TradingView (s3-symbol-logo, arredondado) → iniciais.
  BDR (B3, final 31–39) = logo da empresa de fora com o mesmo logo no TradingView; senão o quadrado. Logo de fora quase todo
  escuro ganha o fundo claro sozinho (contraste < 2:1 sobre o fundo do widget em mais de 90% dos pixels).
Ajustes à mão: scripts/logos_override/override.json (+ imagens da pasta): file (imagem própria), backing (fundo claro arredondado
para logo escuro quase invisível no fundo escuro), skip (etapas a pular).
Saída: <data>/logos/index.json (ticker -> arquivo, origem, fundo claro) e <data>/logos/<hash>.png (64×64, formato original,
fundo transparente). Uso: build_logos.py <pasta data> [--force]. Sem --force, não refaz se o índice tem menos de 7 dias."""
import concurrent.futures as cf, csv, hashlib, io, json, os, re, sys, zipfile
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import requests
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

HERE = os.path.dirname(os.path.abspath(__file__))
OVR_DIR = os.path.join(HERE, "logos_override")
SIZE, MIN_PX, RADIUS = 64, 32, 14
LIGHT = (226, 232, 240, 255)  # --c-txt do site: fundo claro dos logos escuros
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
      "Accept-Language": "pt-BR,pt;q=0.9"}
WEEK = 7 * 86400

# ---------- imagens ----------
def open_img(b):
    """bytes (PNG/ICO/JPG/GIF/WEBP/SVG) -> RGBA, ou None."""
    if b[:5] == b"<?xml" or b"<svg" in b[:600]:
        try:
            import resvg_py
            b = bytes(resvg_py.svg_to_bytes(svg_string=b.decode("utf-8", "ignore"), width=SIZE * 2, height=SIZE * 2))
        except Exception:
            return None
    try:
        im = Image.open(io.BytesIO(b))
        if im.format == "ICO":
            try: im.size = max(im.ico.sizes())
            except Exception: pass
        im.load()
        return im.convert("RGBA")
    except Exception:
        return None

def trim(im):
    """Corta só a margem totalmente transparente (o formato do logo fica)."""
    bb = im.getchannel("A").getbbox()
    return im.crop(bb) if bb else im

def fit(im, box=SIZE):
    """Cabe em box×box sem distorcer, centrado, fundo transparente."""
    im = trim(im)
    w, h = im.size
    k = min(box / w, box / h)
    im = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
    out = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    out.alpha_composite(im, ((box - im.size[0]) // 2, (box - im.size[1]) // 2))
    return out

def rounded_mask(size, r):
    m = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size * 4 - 1, size * 4 - 1), r * 4, fill=255)
    return m.resize((size, size), Image.LANCZOS)

def tile(im):
    """Quadrado da brapi -> quadrado arredondado."""
    t = im.resize((SIZE, SIZE), Image.LANCZOS)
    a = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    a.paste(t, (0, 0), rounded_mask(SIZE, RADIUS))
    return a

def backing(im):
    """Fundo claro arredondado com o logo dentro (logo escuro no fundo escuro do widget)."""
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(Image.new("RGBA", (SIZE, SIZE), LIGHT), (0, 0), rounded_mask(SIZE, RADIUS))
    inner = fit(im, SIZE - 12)
    out.alpha_composite(inner, (6, 6))
    return out

def png(im):
    b = io.BytesIO(); im.save(b, "PNG", optimize=True); return b.getvalue()

# ---------- fontes ----------
def dom(u):
    """Endereço do FCA ('www.ri.x.com.br/ri', 'a / b') -> domínio sem www./ri."""
    u = re.split(r"[\s;,]+", (u or "").strip())[0]
    if not u: return None
    if not u.startswith("http"): u = "https://" + u
    h = urlparse(u).netloc.lower().split(":")[0]
    for p in ("www.ri.", "ri.", "www.", "investidores.", "ir."):
        if h.startswith(p): h = h[len(p):]
    return h or None

def fca_sites():
    """ticker -> site oficial (FCA da CVM, ano atual e anterior) e raiz (4 letras) -> site."""
    web, tk = {}, {}
    y = datetime.now().year
    for year in (y - 1, y):
        try:
            r = requests.get(f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{year}.zip", timeout=(10, 120))
            r.raise_for_status()
            z = zipfile.ZipFile(io.BytesIO(r.content))
        except Exception as e:
            print(f"  FCA {year}: {e}"); continue
        rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), encoding="latin-1"), delimiter=";")
        for row in rd(f"fca_cia_aberta_geral_{year}.csv"):
            if row.get("Pagina_Web", "").strip(): web[row["CNPJ_Companhia"]] = row["Pagina_Web"].strip()
        for row in rd(f"fca_cia_aberta_valor_mobiliario_{year}.csv"):
            c = (row.get("Codigo_Negociacao") or "").strip().upper()
            if c: tk[c] = row["CNPJ_Companhia"]
    by_t = {t: web[c] for t, c in tk.items() if c in web}
    by_root = {}
    for t, s in by_t.items(): by_root.setdefault(t[:4], s)
    return by_t, by_root

def brapi_list():
    r = requests.get("https://brapi.dev/api/quote/list", params={"type": "stock", "limit": 3000}, timeout=(10, 60))
    r.raise_for_status()
    return {s["stock"].upper(): s.get("logo") for s in r.json().get("stocks", []) if s.get("stock")}

def get(url, timeout=12):
    try:
        r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
        return r if r.status_code == 200 and r.content else None
    except Exception:
        return None

def google_favicon(d):
    r = get(f"https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://www.{d}&size=128", 15)
    return r.content if r else None

def site_icons(site):
    """Ícones declarados no site (maior primeiro) + /favicon.ico. -> [bytes]."""
    out, seen = [], set()
    u = re.split(r"[\s;,]+", site.strip())[0]
    u = u if u.startswith("http") else "https://" + u
    d = dom(u)
    for base in dict.fromkeys([u, f"https://{urlparse(u).netloc}/", f"https://ri.{d}/", f"https://www.{d}/"]):
        r = get(base)
        if not r: continue
        cands = []
        for tag in re.findall(r"<link[^>]+>", r.text, re.I):
            rel, href = re.search(r'rel=["\']([^"\']+)', tag, re.I), re.search(r'href=["\']([^"\']+)', tag, re.I)
            if rel and href and "icon" in rel.group(1).lower():
                sz = re.search(r'sizes=["\'](\d+)', tag)
                cands.append((int(sz.group(1)) if sz else (999 if href.group(1).lower().endswith(".svg") else 0), urljoin(r.url, href.group(1).strip())))
        cands.append((0, urljoin(r.url, "/favicon.ico")))
        for _, h in sorted(cands, key=lambda x: -x[0])[:6]:
            if h in seen: continue
            seen.add(h)
            x = get(h, 10)
            if x and len(x.content) > 50: out.append(x.content)
        if out: break
    return out

# ---------- nitidez (1.11) ----------
def _on_grey(im):
    b = Image.new("RGBA", im.size, (128, 128, 128, 255)); b.alpha_composite(im); return b.convert("RGB")

def sharpness(im):
    """Variância do Laplaciano do logo já no 64×64 (maior = mais nítido; borrado/ampliado dá baixo)."""
    from PIL import ImageFilter, ImageStat
    g = _on_grey(fit(im)).convert("L").filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], 1, 128))
    return ImageStat.Stat(g).var[0]

def same_logo(a, b, tol=22):
    """Mesmo desenho e cores? (diferença média por canal a 24 px sobre cinza) — para trocar só a resolução, nunca o logo."""
    pa = _on_grey(fit(a)).resize((24, 24), Image.LANCZOS).tobytes(); pb = _on_grey(fit(b)).resize((24, 24), Image.LANCZOS).tobytes()
    return sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa) < tol

def small(im): return min(trim(im).size) < SIZE  # a fonte é menor que o logo publicado (seria ampliada = borrada)

def better(cur, cand):
    """O ícone do site substitui o favicon só se for maior, mais nítido e o mesmo logo."""
    return cur is None or (min(trim(cand).size) > min(trim(cur).size) and sharpness(cand) >= sharpness(cur) and same_logo(cur, cand))

def big_enough(im): return im is not None and min(trim(im).size) >= MIN_PX * 0.6 and max(im.size) >= MIN_PX

# ---------- montagem ----------
def build(data_dir, force=False):
    out_dir = os.path.join(data_dir, "logos")
    idx_path = os.path.join(out_dir, "index.json")
    ovr = json.load(open(os.path.join(OVR_DIR, "override.json"), encoding="utf-8"))
    ovr_hash = hashlib.sha1(json.dumps(ovr, sort_keys=True).encode() + b"".join(
        open(os.path.join(OVR_DIR, f), "rb").read() for f in sorted(os.listdir(OVR_DIR)) if f.endswith(".png"))).hexdigest()[:12]
    if not force and os.path.exists(idx_path):
        try:
            old = json.load(open(idx_path, encoding="utf-8"))
            age = datetime.now(timezone.utc).timestamp() - datetime.fromisoformat(old["fetched_at"].replace("Z", "+00:00")).timestamp()
            if age < WEEK and old.get("override") == ovr_hash:
                print(f"  logos: índice de {age / 86400:.1f} dias, nada a fazer (semanal; --force refaz)"); return True
        except Exception:
            pass
    bl = brapi_list()
    fund = {}
    try: fund = json.load(open(os.path.join(data_dir, "fundamentus.json"), encoding="utf-8")).get("rows") or {}
    except Exception: pass
    tickers = sorted(t for t in set(bl) | set(fund) if re.fullmatch(r"[A-Z0-9]{4}\d{1,2}B?", t))
    by_t, by_root = fca_sites()
    roots = sorted({t[:4] for t in tickers})
    site_of = {r: next((by_t[t] for t in tickers if t[:4] == r and t in by_t), by_root.get(r)) for r in roots}
    print(f"  logos: {len(tickers)} tickers, {len(roots)} empresas, {sum(1 for v in site_of.values() if v)} com site no FCA")
    skip = lambda r, st: st in ((ovr.get(r) or {}).get("skip") or [])
    generic = set(ovr.get("_generic") or [])
    is_gen = lambda im: hashlib.sha1(png(fit(im))).hexdigest()[:12] in generic

    # 1. favicon (Google)
    fav = {}
    def f1(r):
        s = site_of.get(r)
        if not s or skip(r, "favicon"): return r, None
        d = dom(s); b = google_favicon(d) if d else None
        return r, b
    with cf.ThreadPoolExecutor(12) as ex:
        for r, b in ex.map(f1, roots):
            if b: fav[r] = b
    gen = {h for h, n in _count(fav.values()).items() if n >= 5}  # o mesmo ícone em 5+ empresas = genérico
    chosen = {}  # raiz -> (imagem, origem)
    for r, b in fav.items():
        if hashlib.sha1(b).hexdigest() in gen: continue
        im = open_img(b)
        if big_enough(im) and not is_gen(im): chosen[r] = (im, "favicon")
    # 2. ícone do próprio site: quem ficou sem e quem tem favicon pequeno (seria ampliado/borrado; prefere a fonte maior)
    gap = [r for r in roots if (r not in chosen or small(chosen[r][0])) and site_of.get(r) and not skip(r, "site") and r not in ovr_files(ovr)]
    got = {}
    with cf.ThreadPoolExecutor(10) as ex:
        for r, lst in ex.map(lambda r: (r, site_icons(site_of[r])), gap): got[r] = lst
    cnt = _count([b for lst in got.values() for b in set(lst)], by=lambda b: b)
    gen2 = {h for h, n in cnt.items() if n >= 3}  # plataforma de RI (mesmo ícone em 3+ empresas)
    for r, lst in got.items():
        best = None
        for b in lst:
            if hashlib.sha1(b).hexdigest() in gen2: continue
            im = open_img(b)
            if big_enough(im) and not is_gen(im) and (best is None or min(im.size) > min(best.size)): best = im
        if best is not None and (r not in chosen or better(chosen[r][0], best)): chosen[r] = (best, "site")
    # imagens à mão
    for r in ovr_files(ovr):
        im = open_img(open(os.path.join(OVR_DIR, ovr[r]["file"]), "rb").read())
        if im is not None: chosen[r] = (im, "manual")
    # 3. brapi, por ticker (quem ainda está sem)
    per_t = {}
    need = [t for t in tickers if t[:4] not in chosen and bl.get(t) and not is_placeholder(bl[t]) and not skip(t[:4], "brapi")]
    with cf.ThreadPoolExecutor(8) as ex:
        for t, x in ex.map(lambda t: (t, get(bl[t], 15)), need):
            im = open_img(x.content) if x else None
            if im is not None: per_t[t] = (im, "brapi")
    # arquivos + índice
    os.makedirs(out_dir, exist_ok=True)
    files, idx = {}, {}
    def save(im, src, r):
        b = (ovr.get(r) or {}).get("backing", False)
        img = backing(im) if b else (tile(im) if src == "brapi" else fit(im))
        data = png(img); name = hashlib.sha1(data).hexdigest()[:12] + ".png"
        files[name] = data
        return {"f": name, "s": src, **({"b": 1} if b else {})}
    by_root_entry = {r: save(im, src, r) for r, (im, src) in chosen.items()}
    for t in tickers:
        if t[:4] in by_root_entry: idx[t] = by_root_entry[t[:4]]
        elif t in per_t: idx[t] = save(per_t[t][0], "brapi", t[:4])
    for t in tickers:  # 4. outra classe da mesma empresa
        if t not in idx:
            sib = next((idx[s] for s in tickers if s[:4] == t[:4] and s in idx and idx[s]["s"] != "classe"), None)
            if sib: idx[t] = {**sib, "s": "classe"}
    n_b3, fstats = len(idx), {"fora": 0}
    try:
        fstats = foreign(data_dir, out_dir, ovr, is_gen, files, idx)
    except Exception as e:  # ações de fora não derrubam as da B3
        print(f"  logos de fora: falhou ({type(e).__name__}: {e})")
    for f in os.listdir(out_dir):
        if f.endswith(".png") and f not in files: os.remove(os.path.join(out_dir, f))
    for name, data in files.items():
        p = os.path.join(out_dir, name)
        if not os.path.exists(p): open(p, "wb").write(data)
    stats = {s: sum(1 for v in idx.values() if v["s"] == s) for s in ("favicon", "site", "manual", "brapi", "classe", "tv", "bdr")}
    stats.update(tickers=len(tickers), com_logo=n_b3, iniciais=len(tickers) - n_b3, **fstats, arquivos=len(files), fundo_claro=sum(1 for v in idx.values() if v.get("b")))
    doc = {"fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "override": ovr_hash, "size": SIZE,
           "source": "favicon do site oficial (CVM FCA, serviço de favicons do Google) → ícone do site → brapi → outra classe; ajustes em scripts/logos_override",
           "stats": stats, "t": idx}
    json.dump(doc, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("  logos:", json.dumps(stats, ensure_ascii=False))
    return n_b3 >= 200

# ---------- ações de fora e BDRs ----------
FOREIGN = ("us", "gb", "de", "pt", "jp")  # ordem = prioridade se o mesmo ticker existe em dois países
SITE_TTL, SITE_RETRY = 90 * 86400, 14 * 86400
WD_EX = {"us": ("Q13677", "Q82059"), "gb": ("Q171240",), "de": ("Q151139", "Q155567"), "jp": ("Q217475",), "pt": ("Q2416688", "Q1059291", "Q1145434")}

def tv_logoids(market):
    """TradingView: ticker -> logoid de um mercado (uma consulta; ações e recibos de depósito)."""
    body = {"columns": ["name", "logoid"], "range": [0, 30000], "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr"]}],
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}}
    r = requests.post(f"https://scanner.tradingview.com/{market}/scan", json=body, headers=UA, timeout=(10, 60))
    r.raise_for_status()
    out = {}
    for x in r.json().get("data", []):
        n, l = x["d"][0], x["d"][1]
        if n and l and n not in out: out[n] = l
    return out

def wikidata_sites():
    """(país, ticker) -> site oficial (Wikidata: bolsa P414 com o ticker P249 e site P856)."""
    vals = " ".join("wd:" + q for qs in WD_EX.values() for q in qs)
    q = f"SELECT ?ex ?tk ?site WHERE {{ VALUES ?ex {{ {vals} }} ?c p:P414 ?st . ?st ps:P414 ?ex ; pq:P249 ?tk . ?c wdt:P856 ?site . }}"
    r = requests.get("https://query.wikidata.org/sparql", params={"query": q}, timeout=(10, 120),
                     headers={"Accept": "application/sparql-results+json", "User-Agent": "JGInvestingLogos/1.0 (jjeffersongirotto-star@users.noreply.github.com)"})
    r.raise_for_status()
    ex_c = {q: c for c, qs in WD_EX.items() for q in qs}
    out = {}
    for b in r.json()["results"]["bindings"]:
        c = ex_c.get(b["ex"]["value"].rsplit("/", 1)[-1])
        if c: out.setdefault((c, b["tk"]["value"].upper().strip()), b["site"]["value"])
    return out

YAHOO_MAX = 600  # por execução (semanal): o resto fica para as próximas; o Yahoo limita e também serve aos preços
_Y_STOP = []

def yahoo_site(sym):
    if _Y_STOP: return None
    try:
        import yfinance as yf
        return (yf.Ticker(sym).info or {}).get("website") or ""
    except Exception as e:
        if "Too Many Requests" in str(e) or "Rate limited" in str(e): _Y_STOP.append(1)  # limite: para por hoje
        return None  # erro (rede/limite): tenta de novo na próxima

def _lin(c):
    c /= 255; return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
_LB = 0.2126 * _lin(2) + 0.7152 * _lin(6) + 0.0722 * _lin(23)  # --bg-in do site (fundo do widget)

def too_dark(im):
    """Logo quase todo escuro (menos de 10% dos pixels com contraste 2:1 sobre o fundo do widget): some no fundo escuro."""
    a = fit(im, 48); px = [a.getpixel((x, y)) for y in range(a.height) for x in range(a.width)]
    op = [(r, g, b) for r, g, b, al in px if al > 128]
    if not op: return False
    ok = sum(1 for r, g, b in op if (0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b) + 0.05) / (_LB + 0.05) >= 2.0)
    return ok < 0.10 * len(op)

def foreign(data_dir, out_dir, ovr, is_gen, files, idx):
    import history, tradingview
    uni = {}  # ticker -> país (primeiro na ordem de FOREIGN)
    for c in FOREIGN:
        try: rows = json.load(open(os.path.join(data_dir, f"tradingview_{c}.json"), encoding="utf-8")).get("rows") or {}
        except Exception: rows = {}
        for t in rows:
            if t not in idx and t not in uni: uni[t] = c
    # sites (cache de 90 dias; falha/sem site: tenta de novo em 14 dias)
    sp = os.path.join(out_dir, "sites.json")
    try: cache = json.load(open(sp, encoding="utf-8"))
    except Exception: cache = {}
    now = datetime.now(timezone.utc).timestamp()
    key = lambda t: f"{uni[t]}:{t}"
    need = [t for t in uni if key(t) not in cache or now - cache[key(t)][1] > (SITE_TTL if cache[key(t)][0] else SITE_RETRY)]
    print(f"  logos de fora: {len(uni)} tickers; site a buscar no Yahoo: {len(need)} (até {YAHOO_MAX} agora)")
    need = need[:YAHOO_MAX]
    with cf.ThreadPoolExecutor(2) as ex:
        for t, w in zip(need, ex.map(lambda t: yahoo_site(history.ysym(t, uni[t])), need)):
            if w is not None: cache[key(t)] = [dom(w) or "", now, "yahoo"]
    miss = [t for t in uni if not (cache.get(key(t)) or [""])[0]]
    if miss:
        try:
            wd = wikidata_sites()
            for t in miss:
                for v in (t, t.rstrip("."), t.replace(".", "-"), t.replace(".", " ")):
                    if (uni[t], v) in wd: cache[key(t)] = [dom(wd[(uni[t], v)]) or "", now, "wikidata"]; break
        except Exception as e:
            print(f"  Wikidata: {e}")
    json.dump(cache, open(sp, "w", encoding="utf-8"), separators=(",", ":"))
    site = {t: (cache.get(key(t)) or [""])[0] for t in uni}
    doms = sorted({d for d in site.values() if d})
    skip = lambda d, st: st in ((ovr.get(d) or {}).get("skip") or [])
    # 1. favicon por domínio (Google); o mesmo ícone em 5+ domínios = genérico
    fav = {}
    with cf.ThreadPoolExecutor(16) as ex:
        for d, b in zip(doms, ex.map(lambda d: None if skip(d, "favicon") else google_favicon(d), doms)):
            if b: fav[d] = b
    gen = {h for h, n in _count(fav.values()).items() if n >= 5}
    chosen = {}
    for d, b in fav.items():
        if hashlib.sha1(b).hexdigest() in gen: continue
        im = open_img(b)
        if big_enough(im) and not is_gen(im): chosen[d] = (im, "favicon")
    # 2. ícone do próprio site
    gap = [d for d in doms if (d not in chosen or small(chosen[d][0])) and not skip(d, "site")]
    got = {}
    with cf.ThreadPoolExecutor(16) as ex:
        for d, lst in zip(gap, ex.map(lambda d: site_icons("https://" + d), gap)): got[d] = lst
    gen2 = {h for h, n in _count([b for lst in got.values() for b in set(lst)]).items() if n >= 3}
    for d, lst in got.items():
        best = None
        for b in lst:
            if hashlib.sha1(b).hexdigest() in gen2: continue
            im = open_img(b)
            if big_enough(im) and not is_gen(im) and (best is None or min(im.size) > min(best.size)): best = im
        if best is not None and (d not in chosen or better(chosen[d][0], best)): chosen[d] = (best, "site")
    for d in ovr_files(ovr):
        if "." in d: chosen[d] = (open_img(open(os.path.join(OVR_DIR, ovr[d]["file"]), "rb").read()), "manual")
    def save(im, src, k):
        o = ovr.get(k) or {}
        b = o.get("backing", src in ("favicon", "site") and too_dark(im))
        img = backing(im) if b else (tile(im) if src == "tv" else fit(im))
        data = png(img); name = hashlib.sha1(data).hexdigest()[:12] + ".png"
        files[name] = data
        return {"f": name, "s": src, **({"b": 1} if b else {})}
    by_dom = {d: save(im, src, d) for d, (im, src) in chosen.items() if im is not None}
    for t in uni:
        if site[t] in by_dom: idx[t] = by_dom[site[t]]
    # 3. quadrado do TradingView (por logoid) para quem ficou sem
    lid, mk = {}, {}
    for c in FOREIGN:
        try: m = mk[c] = tv_logoids(tradingview.COUNTRIES[c][0])
        except Exception as e: print(f"  TradingView {c}: {e}"); continue
        for t in uni:
            if uni[t] == c and t in m: lid[t] = m[t]
    try: br_lid = tv_logoids("brazil")
    except Exception: br_lid = {}
    tiles, svg = {}, {}
    def fetch_svgs(ls):
        ls = sorted({l for l in ls if l and l not in svg})
        with cf.ThreadPoolExecutor(8) as ex:
            for l, x in zip(ls, ex.map(lambda l: get(f"https://s3-symbol-logo.tradingview.com/{l}--big.svg", 15), ls)):
                svg[l] = x.content if x else None
    def tv_tile(l):
        if l not in tiles:
            if l not in svg: fetch_svgs([l])
            im = open_img(svg[l]) if svg[l] else None
            tiles[l] = save(im, "tv", l) if im is not None else None
        return tiles[l]
    rest = [t for t in uni if t not in idx and lid.get(t)]
    fetch_svgs(lid[t] for t in rest)
    for t in rest:
        e = tv_tile(lid[t])
        if e: idx[t] = e
    # outra classe da mesma empresa (o site mostra uma: GOOG, BRK.A; o favorito pode ser GOOGL, BRK.B)
    root = lambda t: re.split(r"[.\-/]", t)[0][:4]
    ncl = 0
    for c, m in mk.items():
        has = {}
        for t in uni:
            if uni[t] == c and t in idx and lid.get(t): has.setdefault((lid[t], root(t)), idx[t])
        for t2, l in m.items():
            e = has.get((l, root(t2)))
            if e and t2 not in idx and t2 not in uni: idx[t2] = {**e, "s": "classe"}; ncl += 1
    # BDRs: logo da empresa de fora com o mesmo logoid; senão o quadrado do TradingView
    try:
        r = requests.get("https://brapi.dev/api/quote/list", params={"type": "bdr", "limit": 3000}, timeout=(10, 60)); r.raise_for_status()
        bdrs = {x["stock"].upper() for x in r.json().get("stocks", []) if x.get("stock")}
    except Exception:
        bdrs = set()
    bdrs |= {t for t in br_lid if re.fullmatch(r"[A-Z0-9]{4}3[1-9]", t)}
    by_lid = {}
    for t, l in lid.items():
        if t in idx and l not in by_lid: by_lid[l] = idx[t]
    nb = 0
    fetch_svgs(br_lid.get(t) for t in bdrs if t not in idx and br_lid.get(t) not in by_lid)
    for t in sorted(bdrs):
        if t in idx or not re.fullmatch(r"[A-Z0-9]{4}3[1-9]", t): continue
        l = br_lid.get(t)
        if not l: continue
        e = by_lid.get(l)
        if e: idx[t] = {**e, "s": "bdr"}; nb += 1
        else:
            e = tv_tile(l)
            if e: idx[t] = e; nb += 1
    per = {c: [sum(1 for t in uni if uni[t] == c), sum(1 for t in uni if uni[t] == c and t in idx)] for c in FOREIGN}
    print(f"  logos de fora: por país [tickers, com logo] {per}; outras classes {ncl}; BDRs com logo {nb}")
    return {"paises": per, "classe_fora": ncl, "bdr": nb, "fora": len(uni)}

def is_placeholder(u): return u.rsplit("/", 1)[-1].upper() == "BRAPI.SVG"  # logo genérico da brapi

def ovr_files(ovr): return [r for r, v in ovr.items() if not r.startswith("_") and isinstance(v, dict) and v.get("file")]

def _count(items, by=None):
    c = {}
    for b in items:
        h = hashlib.sha1(b).hexdigest(); c[h] = c.get(h, 0) + 1
    return c

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    ok = build(a[0] if a else "data", force="--force" in sys.argv)
    sys.exit(0 if ok else 1)
