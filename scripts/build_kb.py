"""Base do chat sem IA -> data/kb.json (snapshot `kb` na branch data), a partir dos itens do conhecimento.json:
- resumo da Wikipedia (pt) de cada item;
- filmes, séries, animes e jogos: outros nomes da obra, personagens e elenco (Wikidata) e, quando a Wikidata traz poucos
  personagens, os títulos da página "Lista de personagens de …" (Wikipedia pt e en).
Roda na rotina diária, mas só baixa tudo de novo uma vez por semana; nos outros dias busca apenas os itens novos do conhecimento.json.
Uso: python scripts/build_kb.py <pasta data>     Textos da Wikipedia/Wikidata: licenças CC BY-SA / CC0."""
import json, os, re, sys, time
from datetime import datetime, timezone
from urllib.parse import quote
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from chat import norm, KB_CATS  # noqa: E402  (mesma normalização e mesmas categorias do chat)

WIKI = "https://pt.wikipedia.org"
WIKI_EN = "https://en.wikipedia.org"
WD = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "JGInvesting/1.0 (https://github.com/jjeffersongirotto-star/Mercado-de-a-es-)"}
WEEK = 6.5 * 86400
VERSION = 2  # formato do snapshot; mudou -> baixa tudo de novo
LANGS = "pt|pt-br|en"
# categoria -> palavra que ajuda a busca a achar a página certa
HINT = {"filmes": "filme", "series": "série de televisão", "animes": "anime", "jogos": "jogo eletrônico", "jogadores": "futebolista",
        "estudios": "empresa", "empresas": "empresa"}
WORKS = ("filmes", "series", "animes", "jogos")  # obras: personagens (e elenco nos filmes e séries)
MAX_P, MAX_C = 80, 25
# títulos de seção que não são personagens
NOT_CHAR = re.compile(r"\b(personagens?|protagonistas?|antagonistas?|vil[aõ]es|principais|secund[aá]rios|recorrentes|outros|demais|"
                      r"fam[ií]lia|aliados|inimigos|refer[eê]ncias|notas|liga[cç][oõ]es|ver tamb[eé]m|bibliografia|elenco|saga|arco|"
                      r"temporada|cap[ií]tulo|filme|s[eé]rie|cria[cç][aã]o|desenvolvimento|recep[cç][aã]o|characters?|main|supporting|"
                      r"recurring|other|minor|villains?|antagonists?|protagonists?|family|allies|enemies|references|notes|see also|"
                      r"external links|cast|season|arc|introduced|group|team|clan|organization|organiza[cç][aã]o|grupo|equipe|cl[aã])\b", re.I)


def get(url, **params):
    err = "HTTP 429"
    for i in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=25, params=params or None)
            if r.status_code == 429: time.sleep(5 * (i + 1)); continue
            return r
        except requests.RequestException as e:
            err = type(e).__name__; time.sleep(2)
    print(f"  falhou {url[:80]}: {err}", file=sys.stderr)
    return None


def items(K):
    """-> [(chave, nome para buscar, categoria)] de todos os itens do conhecimento.json (mesmas chaves do chat)."""
    out = []
    for cat, _ in KB_CATS:
        lst = (K.get("futebol") or {}).get("jogadores", []) if cat == "jogadores" else K.get(cat, [])
        for it in lst: out.append((f"{cat}|{norm(it['n'])}", it.get("w") or it["n"], cat))
    for root, d in (K.get("empresas") or {}).items():
        out.append((f"empresas|{root}", d.split(":")[0].strip(), "empresas"))
    return out


def summary(title, base=WIKI):
    r = get(f"{base}/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe='')}")
    if not r or r.status_code != 200: return None
    j = r.json()
    if j.get("type") != "standard" or not j.get("extract"): return None
    return {"t": j.get("title") or title, "x": re.sub(r"\s+", " ", j["extract"]).strip()[:1200],
            "u": ((j.get("content_urls") or {}).get("desktop") or {}).get("page", ""), "q": j.get("wikibase_item")}


def search(name, cat):
    r = get(f"{WIKI}/w/api.php", action="query", list="search", srsearch=f"{name} {HINT.get(cat, '')}".strip(), srlimit=3, format="json")
    if not r or r.status_code != 200: return None
    words = {w for w in re.findall(r"[a-z0-9]+", norm(name)) if len(w) >= 3} or set(re.findall(r"[a-z0-9]+", norm(name)))
    for h in (r.json().get("query") or {}).get("search", []):
        if words & set(re.findall(r"[a-z0-9]+", norm(h["title"]))):  # o título precisa ter alguma palavra do nome
            return summary(h["title"])
    return None


def entities(ids):
    """QIDs -> {QID: {"n": nome (pt, senão en), "a": outros nomes, "d": descrição}} (lotes de 50)."""
    out = {}
    for i in range(0, len(ids), 50):
        r = get(WD, action="wbgetentities", ids="|".join(ids[i:i + 50]), props="labels|aliases|descriptions|sitelinks",
                languages=LANGS, sitefilter="ptwiki|enwiki", format="json")
        if not r or r.status_code != 200: continue
        for q, e in (r.json().get("entities") or {}).items():
            lab = e.get("labels") or {}; n = next((lab[l]["value"] for l in ("pt-br", "pt", "en") if l in lab), None)
            if not n: continue
            al = {lab[l]["value"] for l in lab} | {a["value"] for l, v in (e.get("aliases") or {}).items() for a in v}
            de = e.get("descriptions") or {}
            out[q] = {"n": n, "a": sorted(al - {n})[:8], "d": next((de[l]["value"] for l in ("pt-br", "pt", "en") if l in de), ""),
                      "sl": {k: v["title"] for k, v in (e.get("sitelinks") or {}).items()}}
    return out


def claims(q, prop):
    r = get(WD, action="wbgetclaims", entity=q, property=prop, format="json")
    if not r or r.status_code != 200: return []
    out = []
    for c in (r.json().get("claims") or {}).get(prop, []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
        if v.get("id"): out.append(v["id"])
    return list(dict.fromkeys(out))


def list_page(base, title):
    """Títulos de seção de uma página de lista de personagens (cada seção costuma ser um personagem)."""
    r = get(f"{base}/w/api.php", action="parse", page=title, prop="sections", redirects=1, format="json")
    if not r or r.status_code != 200 or "error" in r.json(): return []
    out = []
    for s in (r.json().get("parse") or {}).get("sections", []):
        t = re.sub(r"<[^>]+>", "", s.get("line", "")).strip()
        if 2 < len(t) <= 40 and len(t.split()) <= 4 and not NOT_CHAR.search(t) and not re.search(r"\d{3,}", t): out.append(t)
    return out


def work(q, cat):
    """Outros nomes da obra, personagens e elenco (Wikidata) + lista de personagens (Wikipedia) -> {"al", "p", "c"}."""
    me = entities([q]).get(q) or {}
    pq = claims(q, "P674")[:MAX_P]
    chars = [dict(n=v["n"], a=v["a"], d=v["d"]) for v in entities(pq).values()]
    if len(chars) < 10 and cat in ("animes", "series", "jogos", "filmes"):  # poucos na Wikidata: completa com a página de lista
        have = {norm(c["n"]) for c in chars}
        sl = me.get("sl") or {}
        names = (list_page(WIKI, f"Lista de personagens de {sl['ptwiki']}") if sl.get("ptwiki") else []) + \
                (list_page(WIKI_EN, f"List of {sl['enwiki']} characters") if sl.get("enwiki") else [])
        for n in names:
            if norm(n) not in have and len(chars) < MAX_P: chars.append({"n": n}); have.add(norm(n))
    cast = []
    if cat in ("filmes", "series"):
        cq = claims(q, "P161")[:MAX_C]
        E = entities(cq)
        cast = [dict(n=E[x]["n"], d=E[x]["d"]) for x in cq if x in E]
    return {"al": me.get("a", []), "p": chars, "c": cast}


def fetch(name, cat):
    try:
        s = (search(name, cat) or summary(name)) if cat in WORKS else (summary(name) or search(name, cat))
        if s and cat in WORKS and s.get("q"): s.update(work(s["q"], cat))
        return s
    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"  {name}: {type(e).__name__}", file=sys.stderr)
        return None


def main(out_dir):
    K = json.load(open(os.path.join(HERE, "..", "conhecimento.json"), encoding="utf-8"))
    path = os.path.join(out_dir, "kb.json")
    old = {}
    if os.path.exists(path):
        try: old = json.load(open(path, encoding="utf-8"))
        except ValueError: old = {}
    try: age = time.time() - datetime.fromisoformat(old["fetched_at"].replace("Z", "+00:00")).timestamp()
    except (KeyError, ValueError): age = 1e12
    if old.get("v") != VERSION: age, old = 1e12, {}
    todo = items(K)
    keep = old.get("itens") or {}
    if age < WEEK:
        todo = [x for x in todo if x[0] not in keep]  # na semana: só os itens novos
        if not todo:
            print("kb: snapshot desta semana já existe; nada a buscar"); return 0
    got = dict(keep); miss = 0  # o que falhar agora fica com o resumo anterior
    for i, (key, name, cat) in enumerate(todo):
        s = fetch(name, cat)
        if s: got[key] = s
        else: miss += 1
        time.sleep(0.2)
        if i % 50 == 49: print(f"  {i + 1}/{len(todo)}")
    valid = {k for k, _, _ in items(K)}
    got = {k: v for k, v in got.items() if k in valid}  # itens que saíram do conhecimento.json saem da base
    if not got: print("kb: nada baixado", file=sys.stderr); return 1
    full = age >= WEEK and miss < len(todo) / 2  # renovação semanal que deu certo: conta a semana a partir de agora
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds") if full or not old.get("fetched_at") else old["fetched_at"]
    json.dump({"v": VERSION, "fetched_at": fetched, "fonte": "Wikipédia em português (CC BY-SA) e Wikidata (CC0)", "itens": got},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    np = sum(len(v.get("p", [])) for v in got.values()); nc = sum(len(v.get("c", [])) for v in got.values())
    print(f"kb: {len(got)} itens, {np} personagens, {nc} do elenco ({len(todo) - miss} baixados agora, {miss} sem página); "
          f"{os.path.getsize(path) / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data"))
