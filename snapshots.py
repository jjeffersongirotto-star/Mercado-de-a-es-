"""Carrega snapshots gerados na máquina da rotina diária (branch `data` no GitHub -> fallback arquivo local data/).
Também é a fonte única dos endereços (branch `data`, app no Render) e de utilitários comuns ao servidor e aos scripts."""
import json, logging, os, re, time
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

log = logging.getLogger("screener.snap")
BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get("SNAPSHOT_RAW_BASE",
                     "https://raw.githubusercontent.com/jjeffersongirotto-star/Mercado-de-a-es-/data/data")  # branch `data`
APP_URL = os.environ.get("APP_URL") or os.environ.get("APP_API", "https://mercado-de-acoes.onrender.com").replace("/api/data", "")
TZ = ZoneInfo("America/Sao_Paulo")
_mem = {}  # nome -> (instante, payload, origem)
import threading
HEAVY = threading.RLock()  # cargas grandes (histórico de todas as ações, tabelas dos modelos): uma de cada vez (pico de memória)

def _gh_api(path):
    """Endereço da API do GitHub para um arquivo da branch `data` (path relativo a RAW, ex. "data/chat_log.jsonl")."""
    m = re.search(r"githubusercontent\.com/([^/]+)/([^/]+)/", RAW)
    return f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}/contents/{path}" if m else None

def gh_get(path, timeout=20):
    """Arquivo da branch `data` pela API (sem o cache do raw), com GITHUB_TOKEN -> (texto, sha) ou (None, None)."""
    tok, api = os.environ.get("GITHUB_TOKEN"), _gh_api(path)
    if not tok or not api: return None, None
    import base64
    try:
        r = requests.get(api, params={"ref": "data"}, headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}, timeout=timeout)
        if r.status_code != 200: return None, None
        j = r.json(); return base64.b64decode(j["content"]).decode(), j["sha"]
    except Exception as e:
        log.warning("GitHub %s: %s", path, e); return None, None

def gh_put(path, text, sha=None, msg="Atualização", timeout=30):
    """Grava um arquivo na branch `data` (GITHUB_TOKEN, variável do Render; a branch `data` não dispara publicação) -> True se gravou."""
    tok, api = os.environ.get("GITHUB_TOKEN"), _gh_api(path)
    if not tok or not api: return False
    import base64
    try:
        r = requests.put(api, headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}, timeout=timeout,
                         json={"message": msg, "branch": "data", **({"sha": sha} if sha else {}), "content": base64.b64encode(text.encode()).decode()})
        return r.status_code in (200, 201)
    except Exception as e:
        log.warning("GitHub %s: %s", path, e); return False

def when_sp(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "?"

_PREP = {"DE", "DA", "DO", "DAS", "DOS", "E", "EM"}
_WORD = {"SAO": "São", "SUL": "Sul", "RIO": "Rio", "MAR": "Mar", "LUZ": "Luz", "GAS": "Gás", "SOL": "Sol", "BOM": "Bom", "PAO": "Pão", "VIA": "Via", "LAR": "Lar"}
_DROP = re.compile(r"\s*(-\s*EM RECUPERA[CÇ][AÃ]O JUDICIAL|\bEM RECUPERA[CÇ][AÃ]O JUDICIAL)\s*$|\b(S\.?\s?A\.?|S/A|LTDA\.?|HOLDING|PARTICIPA[CÇ][OÕ]ES)(?=\s|$|[.,-])", re.I)

_END = re.compile(r"(?:[\s,&]+|^)(?:\(The\)|Inc|Incorporated|Corp|Corporation|Co|Company|Ltd|Limited|plc|p\.l\.c|AG|SE|N\.?V|KGaA|S\.?p\.?A|Group|Class [A-Z]|Series [A-Z]|Cl\.? [A-Z])\.?\s*$", re.I)

_POP = None

def _pop():
    global _POP
    if _POP is None:
        try: _POP = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nomes_populares.json"), encoding="utf-8"))
        except Exception: _POP = {}
    return _POP

def _pop_entry(ticker, country=None):
    """Entrada de nomes_populares.json: B3 (e BDR) pela raiz de 4 letras; EUA pelo ticker ("us:X" antes, para colisão com raiz da B3);
    outros países só com o prefixo do país ("de:SAP", "jp:7203") — o mesmo ticker em outra bolsa é outra empresa."""
    P, t = _pop(), (ticker or "").upper()
    c = (country or "").lower()
    if c in ("", "br") and re.fullmatch(r"[A-Z0-9]{4}\d{1,2}B?", t) and not t.isdigit(): return P.get(t[:4]) or P.get(t)
    if c in ("", "br"): c = "us"
    if c == "us": return P.get("us:" + t) or P.get(t)
    return P.get(c + ":" + t)

def nome_popular(ticker, n, country=None):
    """Nome pelo qual a empresa é conhecida (nomes_populares.json, fonte única: Petrobras, Itaú, Google, SpaceX…); sem entrada,
    nome_curto(n). Widget do app (/api/widget → s)."""
    e = _pop_entry(ticker, country)
    return (e if isinstance(e, str) else (e or {}).get("n")) or nome_curto(n)

def nome_busca(ticker, country=None):
    """Nome popular + aliases (texto extra da busca do site e apelidos do chat): "Meta | facebook | instagram"; "" sem entrada."""
    e = _pop_entry(ticker, country)
    if not e: return ""
    return e if isinstance(e, str) else " | ".join([e.get("n") or ""] + list(e.get("aliases") or []))

def nome_curto(n):
    """Nome da empresa para espaço pequeno (widget): sem S.A./S/A/Ltda/Holding/Participações; tudo maiúsculo vira
    Primeira Maiúscula (siglas de até 3 letras ficam, preposições em minúsculas); corta depois de ' - '. 'BCO' -> 'Banco'."""
    n = re.sub(r"\s+", " ", _DROP.sub(" ", (n or "").strip())).strip(" .,-")
    n = n.split(" - ")[0].strip(" .,-") or n  # 'B3 - BRASIL, BOLSA, BALCAO' -> 'B3'
    for _ in range(3):  # de fora: 'Toyota Motor Corporation' -> 'Toyota Motor', 'JPMorgan Chase & Co.' -> 'JPMorgan Chase'
        m = _END.sub("", n).strip(" .,&-")
        if not m or m == n: break
        n = m
    n = re.sub(r"(\s+(DE|DA|DO|DAS|DOS|E|EM))+$", "", n, flags=re.I)
    if not n or n != n.upper(): return n
    out = []
    for i, w in enumerate(n.split(" ")):
        u = w.upper()
        if u == "BCO": out.append("Banco")
        elif u == "CIA": out.append("Cia")
        elif u in _WORD: out.append(_WORD[u])
        elif i and u in _PREP: out.append(u.lower())
        elif len(re.sub(r"[^A-Z]", "", u)) <= 3 and u.isalpha(): out.append(u)
        else: out.append(w[:1] + w[1:].lower())
    return " ".join(out)

def br_num(s):
    """Número no formato brasileiro ('1.234,56', '7,12%', 'R$ 10') -> float; vazio/traço/inválido -> None."""
    if s is None: return None
    s = str(s).strip().replace("%", "").replace("R$", "").strip()
    if s in ("", "-", "—", "nan", "N/A"): return None
    try: return float(s.replace(".", "").replace(",", "."))
    except ValueError: return None

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

def version(name):
    """Versão do snapshot na branch `data` sem baixá-lo (HEAD: ETag = hash do conteúdo no GitHub) -> texto, ou None se o GitHub
    não respondeu. Quem guarda uma cópia grande (modelos.data) só baixa e monta de novo quando a versão muda."""
    try:
        r = requests.head(f"{RAW}/{name}.json", timeout=(10, 20), allow_redirects=True)
        if r.status_code != 200: return None
        return r.headers.get("ETag") or r.headers.get("Last-Modified") or None
    except Exception:
        return None

def drop(name):
    """Esquece um snapshot da memória (quem usa já guardou o que precisa, ex.: modelos.data)."""
    _mem.pop(name, None)

def invalidate():
    _mem.clear()
