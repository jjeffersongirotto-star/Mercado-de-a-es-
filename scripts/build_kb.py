"""Base do chat sem IA: resumo da Wikipedia (pt) de cada item do conhecimento.json -> data/kb.json (snapshot `kb` na branch data).
Roda na rotina diária, mas só baixa tudo de novo uma vez por semana; nos outros dias busca apenas os itens novos do conhecimento.json.
Uso: python scripts/build_kb.py <pasta data>     Texto da Wikipedia: licença CC BY-SA (o chat cita a fonte)."""
import json, os, re, sys, time
from datetime import datetime, timezone
from urllib.parse import quote
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from chat import norm  # noqa: E402  (mesma normalização do chat)

WIKI = "https://pt.wikipedia.org"
UA = {"User-Agent": "JGInvesting/1.0 (https://github.com/jjeffersongirotto-star/Mercado-de-a-es-)"}
WEEK = 6.5 * 86400
# categoria do conhecimento.json -> palavra que ajuda a busca a achar a página certa
HINT = {"pessoas": "", "obras": "filme", "animes": "anime", "jogos": "jogo eletrônico", "temas": "", "jogadores": "futebolista", "empresas": "empresa"}


def items(K):
    """-> [(chave, nome para buscar, categoria)] de todos os itens do conhecimento.json."""
    out = []
    for cat in ("pessoas", "obras", "animes", "jogos", "temas"):
        for it in K.get(cat, []):
            out.append((f"{cat}|{norm(it['n'])}", it.get("w") or it["n"], cat))
    for it in (K.get("futebol") or {}).get("jogadores", []):
        out.append((f"jogadores|{norm(it['n'])}", it.get("w") or it["n"], "jogadores"))
    for root, d in (K.get("empresas") or {}).items():
        out.append((f"empresas|{root}", d.split(":")[0].strip(), "empresas"))
    return out


def summary(title):
    r = requests.get(f"{WIKI}/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe='')}", headers=UA, timeout=20)
    if r.status_code != 200: return None
    j = r.json()
    if j.get("type") != "standard" or not j.get("extract"): return None
    return {"t": j.get("title") or title, "x": re.sub(r"\s+", " ", j["extract"]).strip()[:1200],
            "u": ((j.get("content_urls") or {}).get("desktop") or {}).get("page", "")}


def search(name, cat):
    r = requests.get(f"{WIKI}/w/api.php", headers=UA, timeout=20, params={
        "action": "query", "list": "search", "srsearch": f"{name} {HINT.get(cat, '')}".strip(), "srlimit": 3, "format": "json"})
    if r.status_code != 200: return None
    words = {w for w in re.findall(r"[a-z0-9]+", norm(name)) if len(w) >= 3}
    for h in (r.json().get("query") or {}).get("search", []):
        if words & set(re.findall(r"[a-z0-9]+", norm(h["title"]))):  # o título precisa ter alguma palavra do nome
            return summary(h["title"])
    return None


def fetch(name, cat):
    try:
        return summary(name) or search(name, cat)
    except (requests.RequestException, ValueError) as e:
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
    json.dump({"fetched_at": fetched, "fonte": "Wikipédia em português (CC BY-SA)", "itens": got},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"kb: {len(got)} itens ({len(todo) - miss} baixados agora, {miss} sem página)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data"))
