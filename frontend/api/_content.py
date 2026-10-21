"""Busca o conteúdo no CMS (Railway) com cache em memória e fallback local."""
import json
import os
import time
from pathlib import Path

import requests

API_URL = os.getenv("API_URL", "").rstrip("/")
TTL = int(os.getenv("CONTENT_TTL", "300"))
SEED_FILE = Path(__file__).resolve().parent.parent / "content" / "seed_content.json"
_cache: dict[str, tuple[float, dict]] = {}


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
    if not API_URL:
        return seed_content(lang)
    try:
        resp = requests.get(f"{API_URL}/api/site/", params={"lang": lang}, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("site"):
            raise ValueError("CMS vazio")
    except Exception:
        # Neon/Railway podem estar "acordando": usa o último cache ou o seed
        return hit[1] if hit else seed_content(lang)
    _cache[lang] = (time.time(), data)
    return data


def send_contact(payload: dict) -> bool:
    if not API_URL:
        return True  # em dev sem backend, só simula
    try:
        resp = requests.post(
            f"{API_URL}/api/contact/",
            json=payload,
            headers={"X-Contact-Key": os.getenv("CONTACT_API_KEY", "")},
            timeout=10,
        )
        return resp.status_code == 201
    except requests.RequestException:
        return False
