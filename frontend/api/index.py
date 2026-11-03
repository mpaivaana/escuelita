"""Front-end público de La Escuelita Ambiental Móvil (Flask na Vercel)."""
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

import markdown
from flask import Flask, Response, abort, redirect, render_template, request, url_for
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _content import error_of, fallback_warning, get_blog, get_content, get_post, is_degraded, send_contact  # noqa: E402
from _i18n import LANG_NAMES, LANGS, MONTHS, PROJECTS_SLUG, UI, pick_lang  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
app = Flask(__name__, template_folder=str(ROOT / "templates"),
            static_folder=str(ROOT / "public" / "static"), static_url_path="/static")


class RestoreVercelPath:
    """Na Vercel, o rewrite de vercel.json entrega toda requisição como /api/index.
    O caminho original vem em ?__path=; aqui ele volta a ser o PATH_INFO do Flask."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query = parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        original = [v for k, v in query if k == "__path"]
        if original:
            environ["PATH_INFO"] = original[0] or "/"
            environ["SCRIPT_NAME"] = ""
            environ["QUERY_STRING"] = urlencode([(k, v) for k, v in query if k != "__path"])
        return self.wsgi_app(environ, start_response)


# Atrás da Vercel o esquema (https) e o host reais chegam em X-Forwarded-*; sem isso os links absolutos saem como http://
app.wsgi_app = RestoreVercelPath(ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1))


def _lang_urls(endpoint, external=False, **extra):
    if endpoint == "projects":
        return {code: url_for("projects", lang=code, slug=PROJECTS_SLUG[code], _external=external) for code in LANGS}
    return {code: url_for(endpoint, lang=code, _external=external, **extra) for code in LANGS}


def page_context(lang, endpoint, **extra):
    return {
        "lang": lang, "ui": UI[lang], "langs": LANGS, "lang_names": LANG_NAMES,
        "projects_slug": PROJECTS_SLUG[lang], "year": date.today().year,
        "lang_urls": _lang_urls(endpoint, **extra),
        # Absolutas: o hreflang e o canonical exigem URL completa
        "lang_urls_abs": _lang_urls(endpoint, external=True, **extra),
    }


HTML_BLOCK = re.compile(r"<(div|p|h[1-6]|ul|ol|blockquote|pre)\b", re.I)


H1_TAG = re.compile(r"<(/?)h1\b", re.I)


@app.template_filter("markdown")
def render_markdown(text):
    """Corpo das entradas do blog. O editor visual do CMS manda HTML (já limpo no backend);
    textos antigos ou de exemplo em Markdown são convertidos aqui.
    O título do post já é o <h1> da página; o botão de título do editor também gera <h1>, então
    os do corpo viram <h2> (o CSS de .prose trata os dois igual: sem mudança visual)."""
    text = text or ""
    html = text if HTML_BLOCK.search(text) else markdown.markdown(text, extensions=["sane_lists"], output_format="html")
    return Markup(H1_TAG.sub(r"<\1h2", html))


@app.template_filter("digits")
def only_digits(value):
    """+51 (999) 999-999 -> 51999999999 (formato que o wa.me exige)."""
    return re.sub(r"\D", "", str(value or ""))


@app.template_filter("pretty_date")
def pretty_date(value, lang="es"):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return value
    month = MONTHS[lang][d.month - 1]
    return f"{month} {d.day}, {d.year}" if lang == "en" else f"{d.day} de {month} de {d.year}"


def cached(html, source="cms", degraded=False, error=""):
    """Resposta cacheável pelo CDN. Se o CMS não respondeu (conteúdo de contingência), o cache é curto:
    assim uma queda passageira do backend não fica "congelada" no site por vários minutos."""
    resp = app.make_response(html)
    resp.headers["X-Content-Source"] = "degraded" if degraded else source
    if degraded and error:
        resp.headers["X-Content-Error"] = error  # motivo da falha do CMS (visível em DevTools > Rede)
    warning = fallback_warning()
    if warning:  # funcionando só por causa da reserva: avisa para o erro de configuração não ficar escondido
        resp.headers["X-Content-Warning"] = warning
    resp.headers["Cache-Control"] = ("public, s-maxage=10, stale-while-revalidate=30" if degraded
                                     else "public, s-maxage=60, stale-while-revalidate=600")
    return resp


@app.get("/favicon.ico")
def favicon():
    # Navegadores pedem /favicon.ico na raiz. O arquivo vive em /static/ (CDN da Vercel); a função
    # serverless não empacota public/, então redirecionar é o que funciona em produção e em dev.
    return redirect(url_for("static", filename="img/favicon.ico"), 301)


@app.get("/robots.txt")
def robots():
    body = f"User-agent: *\nAllow: /\n\nSitemap: {url_for('sitemap', _external=True)}\n"
    return Response(body, mimetype="text/plain", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/sitemap.xml")
def sitemap():
    """Home, projetos, blog e cada entrada publicada, nos 3 idiomas, com os alternates de hreflang."""
    def entry(urls):
        alts = "".join(f'<xhtml:link rel="alternate" hreflang="{c}" href="{u}"/>' for c, u in urls.items())
        return "".join(f"<url><loc>{u}</loc>{alts}</url>" for u in urls.values())

    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for endpoint in ("home", "projects", "blog"):
        xml.append(entry(_lang_urls(endpoint, external=True)))
    for post in get_blog("es"):  # o slug é o mesmo nos três idiomas
        xml.append(entry(_lang_urls("blog_post", external=True, slug=post["slug"])))
    xml.append("</urlset>")
    return Response("".join(xml), mimetype="application/xml", headers={"Cache-Control": "public, max-age=3600"})


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
    return html if status else cached(html, content.get("source", "cms"), is_degraded(content), error_of(content))


@app.get("/<lang>/<slug>/")
def projects(lang, slug):
    if lang not in LANGS or slug != PROJECTS_SLUG[lang]:
        abort(404)
    content = get_content(lang)
    return cached(render_template("projects.html", c=content, **page_context(lang, "projects")),
                  content.get("source", "cms"), is_degraded(content), error_of(content))


@app.get("/<lang>/blog/")
def blog(lang):
    if lang not in LANGS:
        abort(404)
    posts = get_blog(lang)
    return cached(render_template("blog.html", posts=posts, active_nav="blog", **page_context(lang, "blog")),
                  degraded=is_degraded(posts), error=error_of(posts))


@app.get("/<lang>/blog/<slug>/")
def blog_post(lang, slug):
    if lang not in LANGS:
        abort(404)
    post = get_post(lang, slug)
    if not post:
        abort(404)
    return cached(render_template("blog_post.html", post=post, active_nav="blog",
                                  **page_context(lang, "blog_post", slug=slug)))


@app.route("/<lang>/contacto", methods=["GET", "POST"], strict_slashes=False)
def contact(lang):
    if lang not in LANGS:
        abort(404)
    if request.method == "GET":  # alguém abriu o endereço do formulário direto
        return redirect(url_for("home", lang=lang) + "#contacto", 302)
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
