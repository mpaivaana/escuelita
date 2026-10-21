"""Front-end público de La Escuelita Ambiental Móvil (Flask na Vercel)."""
import sys
from datetime import date
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, url_for

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _content import get_content, send_contact  # noqa: E402
from _i18n import LANG_NAMES, LANGS, PROJECTS_SLUG, UI, pick_lang  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
app = Flask(__name__, template_folder=str(ROOT / "templates"),
            static_folder=str(ROOT / "public" / "static"), static_url_path="/static")


def page_context(lang, endpoint, **extra):
    return {
        "lang": lang, "ui": UI[lang], "langs": LANGS, "lang_names": LANG_NAMES,
        "projects_slug": PROJECTS_SLUG[lang], "year": date.today().year,
        "lang_urls": {code: url_for(endpoint, lang=code, **extra) for code in LANGS}
        if endpoint != "projects" else {code: url_for("projects", lang=code, slug=PROJECTS_SLUG[code]) for code in LANGS},
    }


def cached(html):
    resp = app.make_response(html)
    resp.headers["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=86400"
    return resp


@app.get("/")
def root():
    return redirect(url_for("home", lang=pick_lang(request.headers.get("Accept-Language", ""))), 302)


@app.get("/<lang>/")
def home(lang):
    if lang not in LANGS:
        abort(404)
    content = get_content(lang)
    status = request.args.get("contacto")
    html = render_template("index.html", c=content, form_status=status, **page_context(lang, "home"))
    return html if status else cached(html)


@app.get("/<lang>/<slug>/")
def projects(lang, slug):
    if lang not in LANGS or slug != PROJECTS_SLUG[lang]:
        abort(404)
    content = get_content(lang)
    return cached(render_template("projects.html", c=content, **page_context(lang, "projects")))


@app.post("/<lang>/contacto")
def contact(lang):
    if lang not in LANGS:
        abort(404)
    form = request.form
    payload = {k: form.get(k, "").strip() for k in ("name", "email", "subject", "message", "website")}
    payload["language"] = lang
    ok = all(payload[k] for k in ("name", "email", "subject", "message")) and send_contact(payload)
    return redirect(url_for("home", lang=lang, contacto="ok" if ok else "error") + "#contacto", 303)


@app.errorhandler(404)
def not_found(_):
    lang = request.path.strip("/").split("/")[0]
    lang = lang if lang in LANGS else "es"
    return render_template("404.html", **page_context(lang, "home")), 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
