"""Busca o conteúdo no CMS (Railway) com cache em memória e fallback local.

Configuração (variáveis lidas a cada chamada, para ser testável):
  API_URL  endereço do backend. Aceita valor "sujo" (aspas, espaços, /api/site/, /gestor-xxx): só o host importa.
  Na Vercel (variável VERCEL=1, definida pela própria plataforma) o backend de produção é tentado como reserva
  se API_URL estiver errada ou ausente, e o motivo de qualquer falha vai para o log e para o cabeçalho X-Content-Error.
"""
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

log = logging.getLogger("escuelita")
# Endereço público do backend de produção. Só é usado como reserva, e só dentro da Vercel.
DEFAULT_API_URL = "https://escuelita-production.up.railway.app"
LOCAL_HOSTS = ("localhost", "127.0.0.1")
TTL = int(os.getenv("CONTENT_TTL", "60"))
SEED_FILE = Path(__file__).resolve().parent.parent / "content" / "seed_content.json"
_cache: dict[str, tuple[float, dict]] = {}
# Última sondagem de backend: (quando, base que respondeu ou None, motivo da falha)
_probe: tuple[float, str | None, str] = (0.0, None, "")
PROBE_OK_TTL, PROBE_FAIL_TTL, PROBE_TIMEOUT = 300, 10, 4


def normalize_api_url(raw) -> str:
    """'  "https://x.up.railway.app/gestor-9fa656/ " ' -> 'https://x.up.railway.app'. Vazio se não der para entender."""
    raw = (raw or "").strip().strip("\"'").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parts = urlsplit(raw)
    if not parts.netloc or not parts.hostname:
        return ""
    scheme = parts.scheme
    if scheme == "http" and parts.hostname not in LOCAL_HOSTS:
        scheme = "https"  # um redirect 301 transformaria o POST do contato em GET
    return f"{scheme}://{parts.netloc}"


def candidate_bases() -> list[str]:
    """Backends a tentar, em ordem. Vazio = modo dev sem backend (usa o conteúdo de exemplo)."""
    bases = []
    configured = normalize_api_url(os.getenv("API_URL"))
    if configured:
        bases.append(configured)
    if os.getenv("VERCEL") and DEFAULT_API_URL not in bases:
        bases.append(DEFAULT_API_URL)
    return bases


def resolve_base() -> tuple[str | None, str]:
    """Qual backend está respondendo agora? Devolve (base, motivo_da_falha). Resultado guardado por alguns segundos."""
    global _probe
    when, base, error = _probe
    age = time.time() - when
    if base and age < PROBE_OK_TTL:
        return base, ""
    if not base and error and age < PROBE_FAIL_TTL:
        return None, error
    errors = []
    for candidate in candidate_bases():
        try:
            resp = requests.get(f"{candidate}/api/health/", timeout=PROBE_TIMEOUT)
            if resp.status_code == 200:
                _probe = (time.time(), candidate, "")
                if errors:
                    log.warning("CMS: usando %s porque API_URL falhou (%s)", candidate, "; ".join(errors))
                return candidate, ""
            errors.append(f"{candidate} -> HTTP {resp.status_code}")
        except Exception as exc:
            errors.append(f"{candidate} -> {type(exc).__name__}")
    error = "; ".join(errors) or "sem backend configurado"
    _probe = (time.time(), None, error)
    log.warning("CMS indisponível: %s", error)
    return None, error


def fallback_warning() -> str:
    """Não vazio quando o site só funciona porque a reserva entrou no lugar de um API_URL ausente ou errado."""
    _, base, _ = _probe
    wanted = normalize_api_url(os.getenv("API_URL"))
    if base and base != wanted:
        return f"API_URL {'incorreta' if wanted else 'ausente'}; usando {base}"
    return ""


def configured() -> bool:
    return bool(candidate_bases())


class Degraded(list):
    """Lista vazia devolvida quando o CMS não respondeu (para o front não cachear isso por muito tempo)."""

    def __init__(self, error=""):
        super().__init__()
        self.error = error


def is_degraded(obj) -> bool:
    """True se a página foi montada com o conteúdo de exemplo/vazio porque o CMS configurado não respondeu."""
    if isinstance(obj, Degraded):
        return True
    return configured() and isinstance(obj, dict) and obj.get("source") == "seed"


def error_of(obj) -> str:
    """Motivo curto (ASCII, vai em cabeçalho HTTP) da contingência; vazio se não houver."""
    text = getattr(obj, "error", "") if isinstance(obj, Degraded) else (obj.get("error", "") if isinstance(obj, dict) else "")
    return text.encode("ascii", "replace").decode()[:300]


def _t(value, lang):
    if isinstance(value, dict):
        return value.get(lang) or value.get("es") or ""
    return value


def _localize(obj, lang):
    return {k: _t(v, lang) for k, v in obj.items()}


def seed_content(lang: str) -> dict:
    """Conteúdo de exemplo (mesmo do seed do backend) para dev ou se o CMS cair."""
    raw = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    projects = []
    for p in raw["projects"]:
        item = _localize(p, lang)
        item["image"] = f"/static/img/{p['image']}" if p.get("image") else None
        item["featured"] = True
        projects.append(item)
    site = _localize(raw["site"], lang)
    site.update(hero_image=None, impact_image=None)
    team = []
    for m in raw.get("team", []):
        item = _localize(m, lang)
        words = item["name"].split()
        item.update(photo=f"/static/img/team/{m['photo']}" if m.get("photo") else None, linkedin="",
                    initials="".join(w[0] for w in (words[:1] + words[-1:] if len(words) > 1 else words)).upper())
        team.append(item)
    return {
        "source": "seed",
        "lang": lang,
        "site": site,
        "pillars": [_localize(p, lang) for p in raw["pillars"]],
        "projects": projects,
        "services": [_localize(s, lang) for s in raw["services"]],
        "stats": [_localize(s, lang) for s in raw["stats"]],
        "team": team,
    }


def get_content(lang: str) -> dict:
    hit = _cache.get(lang)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    if not configured():
        return seed_content(lang)
    base, error = resolve_base()
    if base:
        try:
            resp = requests.get(f"{base}/api/site/", params={"lang": lang}, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("site"):
                raise ValueError("CMS vazio (rode seed_content no backend)")
            data["source"] = "cms"
            _cache[lang] = (time.time(), data)
            return data
        except Exception as exc:
            error = f"{base}/api/site/ -> {type(exc).__name__}: {str(exc)[:120]}"
            log.warning("CMS: %s", error)
    # Neon/Railway podem estar "acordando": usa o último cache ou o seed
    if hit:
        return hit[1]
    fallback = seed_content(lang)
    fallback["error"] = error
    return fallback


def _seed_posts(lang: str) -> list[dict]:
    raw = json.loads(SEED_FILE.read_text(encoding="utf-8")).get("blog", [])
    posts = []
    for p in raw:
        item = _localize(p, lang)
        item["cover"] = f"/static/img/{p['cover']}" if p.get("cover") else None
        posts.append(item)
    return posts


def get_blog(lang: str) -> list[dict]:
    """Entradas publicadas (sem o corpo). Sem backend configurado, usa os exemplos do seed."""
    key = f"blog:{lang}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    if not configured():
        return [{k: v for k, v in p.items() if k != "body"} for p in _seed_posts(lang)]
    base, error = resolve_base()
    if base:
        try:
            resp = requests.get(f"{base}/api/blog/", params={"lang": lang}, timeout=8)
            resp.raise_for_status()
            posts = resp.json().get("posts", [])
            _cache[key] = (time.time(), posts)
            return posts
        except Exception as exc:
            error = f"{base}/api/blog/ -> {type(exc).__name__}: {str(exc)[:120]}"
            log.warning("CMS: %s", error)
    return hit[1] if hit else Degraded(error)  # nunca mostra exemplos falsos em produção


def get_post(lang: str, slug: str) -> dict | None:
    key = f"post:{lang}:{slug}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    if not configured():
        return next((p for p in _seed_posts(lang) if p["slug"] == slug), None)
    base, error = resolve_base()
    if not base:
        return hit[1] if hit else None
    try:
        resp = requests.get(f"{base}/api/blog/{slug}/", params={"lang": lang}, timeout=8)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        post = resp.json()
    except Exception as exc:
        log.warning("CMS: %s/api/blog/%s/ -> %s: %s", base, slug, type(exc).__name__, str(exc)[:120])
        return hit[1] if hit else None
    _cache[key] = (time.time(), post)
    return post


def send_contact(payload: dict) -> bool:
    if not configured():
        return True  # em dev sem backend, só simula
    base, error = resolve_base()
    if not base:
        log.warning("Contato não enviado: %s", error)
        return False
    try:
        resp = requests.post(
            f"{base}/api/contact/",
            json=payload,
            headers={"X-Contact-Key": os.getenv("CONTACT_API_KEY", "").strip()},
            timeout=10,
        )
    except requests.RequestException as exc:
        log.warning("Contato não enviado: %s -> %s", base, type(exc).__name__)
        return False
    if resp.status_code != 201:
        hint = " (CONTACT_API_KEY diferente da do backend?)" if resp.status_code == 403 else ""
        log.warning("Contato recusado pelo backend: HTTP %s%s", resp.status_code, hint)
    return resp.status_code == 201
