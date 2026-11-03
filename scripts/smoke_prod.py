#!/usr/bin/env python3
"""Teste de fumaça do site no ar (front na Vercel + CMS/API na Railway). Só usa a biblioteca padrão.

    python scripts/smoke_prod.py \\
        --front https://escuelita-ten.vercel.app \\
        --api   https://escuelita-production.up.railway.app \\
        --admin-path gestor-9fa656

Opcional: --send-test-message envia UMA mensagem real pelo formulário do site (assunto «[TESTE] ...»);
ela aparece no gestor em «Formulario de contacto» e pode ser marcada como respondida.

Código de saída 1 se houver FALHA. AVISO não reprova.
"""
import argparse
import html
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

OK, WARN, FAIL = "OK   ", "AVISO", "FALHA"
results = []


def say(level, msg):
    results.append(level)
    print(f"[{level}] {msg}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(url, method="GET", data=None, headers=None, follow=True, timeout=30):
    """Devolve (status, headers, corpo). Nunca levanta exceção; status 0 = erro de rede."""
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, method=method, data=data,
                                 headers={"User-Agent": "escuelita-smoke/1.0", **(headers or {})})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.headers, resp.read() if method == "GET" else b""
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read() if method == "GET" else b""
    except Exception as exc:
        return 0, {}, str(exc).encode()


def expect(url, want=200, label=None, **kw):
    status, headers, body = fetch(url, **kw)
    wants = want if isinstance(want, (tuple, list)) else (want,)
    say(OK if status in wants else FAIL, f"{label or url} -> {status}" + ("" if status in wants else f" (esperado {want})"))
    return status, headers, body


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--front", required=True, help="URL do front (Vercel)")
    ap.add_argument("--api", required=True, help="URL do backend (Railway)")
    ap.add_argument("--admin-path", default="admin", help="ADMIN_PATH do backend (sem barras)")
    ap.add_argument("--send-test-message", action="store_true", help="Envia 1 mensagem real pelo formulário")
    a = ap.parse_args()
    front, api = a.front.rstrip("/"), a.api.rstrip("/")

    print(f"\n== Backend / API ({api})")
    expect(f"{api}/api/health/", label="health")
    site = {}
    for lang in ("es", "en", "pt"):
        status, _, body = expect(f"{api}/api/site/?lang={lang}", label=f"/api/site/?lang={lang}")
        if status == 200:
            site[lang] = json.loads(body)
    es = site.get("es")
    if es:
        for key in ("pillars", "projects", "services", "stats", "team"):
            say(OK if es[key] else WARN, f"{key}: {len(es[key])} item(ns) publicado(s)")
        say(OK if es["site"].get("about_text") else FAIL, "textos gerais (about_text) preenchidos")
        # Banco de imagens: toda imagem tem de ser URL absoluta https e abrir
        imgs = [p["image"] for p in es["projects"] if p.get("image")] + [m["photo"] for m in es["team"] if m.get("photo")]
        imgs += [es["site"][k] for k in ("hero_image", "impact_image") if es["site"].get(k)]
        say(OK if imgs else WARN, f"{len(imgs)} imagem(ns) do CMS na API")
        for url in imgs:
            if "cloudinary.com" not in url and urllib.parse.urlparse(url).netloc.endswith("railway.app"):
                say(FAIL, f"imagem no disco do servidor (some a cada deploy): {url}")
            elif not url.startswith("https://"):
                say(FAIL, f"imagem sem https: {url}")
            else:
                st, _, _ = fetch(url, "HEAD")
                say(OK if st == 200 else FAIL, f"imagem {st}: {url}")
        for lang in ("en", "pt"):
            if lang in site and site[lang]["site"].get("about_text") == es["site"].get("about_text"):
                say(WARN, f"texto «Nosotros» em {lang} igual ao espanhol: tradução não preenchida no gestor (o site usa o espanhol)")
    blog = fetch(f"{api}/api/blog/?lang=es")
    posts = json.loads(blog[2])["posts"] if blog[0] == 200 else []
    say(OK if blog[0] == 200 else FAIL, f"/api/blog/ -> {blog[0]} ({len(posts)} entrada(s) publicada(s))")

    print(f"\n== Gestor (CMS)")
    expect(f"{api}/{a.admin_path.strip('/')}/login/", label="tela de login do gestor")
    if a.admin_path.strip("/") != "admin":
        expect(f"{api}/admin/", want=404, label="/admin/ não deve existir")
    expect(f"{api}/api/contact/", want=(405, 403), label="GET no endpoint de contato é recusado")

    print(f"\n== Front ({front})")
    expect(f"{front}/", want=(301, 302, 307, 308), follow=False, label="/ redireciona para um idioma")
    pages = {}
    for path in ("/es/", "/en/", "/pt/", "/es/proyectos/", "/en/projects/", "/pt/projetos/",
                 "/es/blog/", "/en/blog/", "/pt/blog/"):
        st, headers, body = expect(f"{front}{path}", label=path)
        pages[path] = (st, headers, body.decode("utf-8", "replace"))
    expect(f"{front}/es/pagina-que-no-existe/", want=404, label="404 de página inexistente")
    for asset in ("/static/css/site.css", "/static/js/site.js", "/static/video/la-escuelita-intro-es.mp4",
                  "/static/img/logo-giz.svg", "/favicon.ico", "/robots.txt", "/sitemap.xml"):
        st, _, _ = expect(f"{front}{asset}", label=asset, method="HEAD" if asset.startswith("/static/") else "GET")

    print("\n== Integração Front <-> CMS")
    source = pages.get("/es/", (0, {}, ""))[1].get("X-Content-Source") if pages.get("/es/", (0,))[0] == 200 else None
    if pages.get("/es/", (0,))[0] == 200:
        reason = pages["/es/"][1].get("X-Content-Error")
        warning = pages["/es/"][1].get("X-Content-Warning")
        if warning:
            say(WARN, f"o front só funciona por causa da reserva: {warning}. Corrija API_URL na Vercel")
        if reason:
            say(FAIL, f"motivo informado pelo front: {reason}")
    if source == "cms":
        say(OK, "o front lê o conteúdo do CMS (X-Content-Source: cms)")
    elif source in ("degraded", "seed"):
        say(FAIL, f"o front mostra conteúdo de EXEMPLO ({source}): confira API_URL na Vercel e se a Railway responde")
    elif pages.get("/es/", (0,))[0] == 200:
        say(WARN, "o front ainda não envia X-Content-Source (publique a versão com esse cabeçalho para ter este controle)")
    if es and pages.get("/es/proyectos/", (0,))[0] == 200:
        body = pages["/es/proyectos/"][2]
        missing = [p["title"] for p in es["projects"] if html.escape(p["title"]) not in body and html.escape(p["title"], quote=False) not in body]
        say(OK if not missing else FAIL,
            "todos os projetos do CMS aparecem em /es/proyectos/" if not missing
            else f"projetos do CMS ausentes no front (cache de até ~1 min é normal; repita): {missing}")
    if es and pages.get("/es/", (0,))[0] == 200:
        phone = es["site"].get("whatsapp", "")
        digits = "".join(c for c in phone if c.isdigit())
        if digits:
            say(OK if f"wa.me/{digits}" in pages["/es/"][2] else WARN, f"link do WhatsApp do CMS na home (wa.me/{digits})")
    if posts and pages.get("/es/blog/", (0,))[0] == 200:
        missing = [p["slug"] for p in posts if f"/es/blog/{p['slug']}/" not in pages["/es/blog/"][2]]
        say(OK if not missing else WARN, "entradas do blog do CMS listadas no front" if not missing
            else f"entradas ainda não visíveis no front (cache ~1 min?): {missing}")
        st, _, _ = expect(f"{front}/es/blog/{posts[0]['slug']}/", label=f"entrada «{posts[0]['title'][:40]}»")

    if a.send_test_message:
        print("\n== Formulário de contato (mensagem real)")
        data = urllib.parse.urlencode({"name": "Teste automático", "email": "teste@example.com",
                                       "subject": "[TESTE] smoke_prod.py", "message": "Pode ignorar/marcar como respondida.",
                                       "website": ""}).encode()
        st, headers, _ = fetch(f"{front}/es/contacto", "POST", data, {"Content-Type": "application/x-www-form-urlencoded"}, follow=False)
        loc = headers.get("Location", "") if headers else ""
        say(OK if st in (302, 303) and "contacto=ok" in loc else FAIL,
            f"envio -> {st} {loc}" + ("" if "contacto=ok" in loc else "  (CONTACT_API_KEY igual nos dois lados? backend no ar?)"))

    fails, warns = results.count(FAIL), results.count(WARN)
    print(f"\nRESULTADO: {results.count(OK)} ok, {warns} aviso(s), {fails} falha(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
