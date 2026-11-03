"""Diagnóstico das integrações: banco de dados, banco de imagens (Cloudinary) e CMS.

Uso (no Console da Railway, ou localmente):
    python manage.py check_integrations                 # banco, conteúdo, configuração, ping na Cloudinary
    python manage.py check_integrations --write-test    # + sobe e apaga uma imagem de teste na Cloudinary
    python manage.py check_integrations --check-urls    # + confere se cada imagem usada no CMS realmente abre
    python manage.py check_integrations --front-url https://seu-site.vercel.app   # + confere o front

Termina com código 1 se houver alguma FALHA (serve para CI/healthcheck manual). AVISO não reprova.
"""
import io
import urllib.error
import urllib.request

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage, storages
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from PIL import Image

from content.models import BlogPost, ContactMessage, ImpactStat, Pillar, Project, Service, SiteSettings, TeamMember

OK, WARN, FAIL = "OK", "AVISO", "FALHA"


def http_status(url, method="HEAD", timeout=15):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "escuelita-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers
    except Exception as exc:  # DNS, timeout, TLS...
        return 0, {"error": str(exc)[:120]}


class Command(BaseCommand):
    help = "Verifica banco de dados, banco de imagens e CMS. Sai com código 1 se algo falhar."

    def add_arguments(self, parser):
        parser.add_argument("--write-test", action="store_true",
                            help="Sobe e apaga uma imagem de teste no armazenamento de imagens")
        parser.add_argument("--check-urls", action="store_true",
                            help="Confere se cada imagem referenciada no CMS abre (HEAD)")
        parser.add_argument("--front-url", help="URL pública do front (Vercel) para conferir a integração com o CMS")

    # -- util -------------------------------------------------------------------------------
    def report(self, level, msg):
        self.results.append(level)
        style = {OK: self.style.SUCCESS, WARN: self.style.WARNING, FAIL: self.style.ERROR}[level]
        self.stdout.write(f"  {style(f'[{level}]')} {msg}")

    def section(self, title):
        self.stdout.write(f"\n{self.style.MIGRATE_HEADING(title)}")

    # -- verificações -------------------------------------------------------------------------
    def check_database(self):
        self.section("Banco de dados")
        cfg = connection.settings_dict
        try:
            connection.ensure_connection()
        except Exception as exc:
            self.report(FAIL, f"não conectou ({connection.vendor}): {str(exc)[:160]}")
            return False
        self.report(OK, f"conectado: {connection.vendor} em {cfg.get('HOST') or 'arquivo local'}")
        if connection.vendor == "sqlite" and not settings.DEBUG:
            self.report(FAIL, "usando SQLite em produção: DATABASE_URL não está definida; os dados se perdem a cada deploy")
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            self.report(FAIL, f"{len(pending)} migração(ões) pendente(s): rode `python manage.py migrate`")
        else:
            self.report(OK, "todas as migrações aplicadas")
        try:  # escreve e desfaz: prova que o usuário do banco consegue gravar sem deixar rastro
            with transaction.atomic():
                ContactMessage.objects.create(name="check", email="check@example.com", subject="check", message="check")
                transaction.set_rollback(True)
            self.report(OK, "leitura e escrita funcionam (teste revertido, nada foi gravado)")
        except Exception as exc:
            self.report(FAIL, f"não conseguiu gravar: {str(exc)[:160]}")
        return True

    def check_content(self):
        self.section("Conteúdo do CMS")
        if SiteSettings.load():
            self.report(OK, "textos gerais (SiteSettings) existem")
        else:
            self.report(FAIL, "SiteSettings vazio: o site cai no conteúdo de exemplo. Rode `python manage.py seed_content`")
        for label, model in (("pilares", Pillar), ("projetos", Project), ("serviços", Service),
                             ("cifras de impacto", ImpactStat), ("equipe", TeamMember)):
            total, shown = model.objects.count(), model.objects.filter(published=True).count()
            level = OK if shown else WARN
            self.report(level, f"{label}: {shown} publicado(s) de {total}")
        self.report(OK, f"blog: {BlogPost.visible().count()} no ar, "
                        f"{BlogPost.objects.filter(published=False).count()} rascunho(s)")
        supers = User.objects.filter(is_superuser=True, is_active=True).count()
        self.report(OK if supers else FAIL, f"administradores ativos: {supers}")
        if not Group.objects.filter(name="Editores").exists():
            self.report(WARN, "grupo «Editores» não existe")
        pending = ContactMessage.objects.filter(handled=False).count()
        self.report(OK, f"mensagens de contato: {ContactMessage.objects.count()} ({pending} sem resposta)")

    def check_images(self, write_test, check_urls):
        self.section("Banco de imagens")
        storage = type(storages["default"]).__name__
        if settings.USE_CLOUDINARY:
            self.report(OK, f"armazenamento: Cloudinary ({storage})")
            try:
                import cloudinary.api
                cloudinary.api.ping()
                self.report(OK, "credenciais da Cloudinary aceitas (ping)")
            except Exception as exc:
                self.report(FAIL, f"Cloudinary recusou/não respondeu: {str(exc)[:160]}")
        else:
            level = WARN if settings.DEBUG else FAIL
            self.report(level, "CLOUDINARY_URL ausente/inválida: imagens vão para o disco do servidor e SE PERDEM a cada deploy")

        if write_test:
            try:
                buf = io.BytesIO()
                Image.new("RGB", (4, 4), (20, 120, 60)).save(buf, "PNG")
                name = default_storage.save("healthcheck/integration-test.png", ContentFile(buf.getvalue()))
                url = default_storage.url(name)
                if settings.USE_CLOUDINARY:
                    status, _ = http_status(url)
                    self.report(OK if status == 200 else FAIL, f"upload de teste: URL pública responde {status} ({url})")
                else:
                    self.report(OK, f"upload de teste gravado em disco ({name})")
                default_storage.delete(name)
                self.report(OK, "imagem de teste apagada")
            except Exception as exc:
                self.report(FAIL, f"upload de teste falhou: {str(exc)[:160]}")

        refs = []
        for obj in SiteSettings.objects.all():
            refs += [("Textos gerais", f, getattr(obj, f)) for f in ("hero_image", "impact_image")]
        refs += [(f"Proyecto «{o.title}»", "image", o.image) for o in Project.objects.all()]
        refs += [(f"Equipo «{o.name}»", "photo", o.photo) for o in TeamMember.objects.all()]
        refs += [(f"Blog «{o.title}»", "cover", o.cover) for o in BlogPost.objects.all()]
        used = [(who, field, f) for who, field, f in refs if f]
        self.report(OK, f"{len(used)} imagem(ns) referenciada(s) no banco")
        if not check_urls:
            if used:
                self.stdout.write("      (use --check-urls para conferir se cada uma abre)")
            return
        broken = 0
        for who, field, f in used:
            if settings.USE_CLOUDINARY:
                status, _ = http_status(f.url)
                good = status == 200
                detail = f"HTTP {status} {f.url}"
            else:
                good = default_storage.exists(f.name)
                detail = f"arquivo {'existe' if good else 'NÃO existe'} em disco: {f.name}"
            if not good:
                broken += 1
                self.report(FAIL, f"{who} · {field}: imagem quebrada ({detail}). Reenvie a imagem pelo gestor.")
        if not broken:
            self.report(OK, "todas as imagens referenciadas abrem")

    def check_config(self):
        self.section("Configuração")
        if settings.SECRET_KEY == "dev-only-insecure-key":
            self.report(FAIL if not settings.DEBUG else WARN, "DJANGO_SECRET_KEY é a chave padrão de desenvolvimento")
        else:
            self.report(OK, "DJANGO_SECRET_KEY definida")
        self.report(WARN if settings.DEBUG else OK, f"DJANGO_DEBUG={'True (desligue em produção)' if settings.DEBUG else 'False'}")
        self.report(WARN if settings.ADMIN_PATH == "admin/" else OK,
                    "ADMIN_PATH padrão (/admin/): use um endereço difícil de adivinhar" if settings.ADMIN_PATH == "admin/"
                    else "ADMIN_PATH personalizado")
        self.report(OK if settings.CONTACT_API_KEY else WARN,
                    "CONTACT_API_KEY definida (precisa ser igual na Vercel)" if settings.CONTACT_API_KEY
                    else "CONTACT_API_KEY vazia: qualquer um pode postar no formulário de contato")
        local = "localhost" in settings.FRONTEND_URL or "127.0.0.1" in settings.FRONTEND_URL
        self.report(WARN if local else OK, f"FRONTEND_URL={settings.FRONTEND_URL}"
                    + (" (aponta para localhost: os botões «Ver el sitio» do gestor quebram)" if local else ""))
        self.report(OK if settings.CSRF_TRUSTED_ORIGINS else WARN, f"CSRF_TRUSTED_ORIGINS={settings.CSRF_TRUSTED_ORIGINS}")

    def check_front(self, front_url):
        self.section(f"Front ({front_url})")
        front = front_url.rstrip("/")
        status, headers = http_status(f"{front}/es/", "GET")
        if status != 200:
            self.report(FAIL, f"/es/ respondeu {status}")
            return
        self.report(OK, "/es/ responde 200")
        source = headers.get("X-Content-Source")
        if source == "cms":
            self.report(OK, "o front está lendo o conteúdo do CMS (X-Content-Source: cms)")
        elif source in ("degraded", "seed"):
            self.report(FAIL, f"o front está mostrando conteúdo de EXEMPLO ({source}): confira API_URL na Vercel e se o backend responde")
        else:
            self.report(WARN, "o front não informa a origem do conteúdo (versão anterior ao cabeçalho X-Content-Source)")
        if headers.get("X-Content-Error"):
            self.report(FAIL, f"motivo informado pelo front: {headers.get('X-Content-Error')}")
        if headers.get("X-Content-Warning"):
            self.report(WARN, f"o front só funciona por causa da reserva: {headers.get('X-Content-Warning')}. Corrija API_URL na Vercel")
        for lang in ("en", "pt"):
            st, _ = http_status(f"{front}/{lang}/", "GET")
            self.report(OK if st == 200 else FAIL, f"/{lang}/ responde {st}")

    # -- execução -------------------------------------------------------------------------------
    def handle(self, *args, **opts):
        self.results = []
        if self.check_database():
            self.check_content()
        self.check_images(opts["write_test"], opts["check_urls"])
        self.check_config()
        if opts["front_url"]:
            self.check_front(opts["front_url"])
        fails, warns = self.results.count(FAIL), self.results.count(WARN)
        self.stdout.write("")
        summary = f"{self.results.count(OK)} ok, {warns} aviso(s), {fails} falha(s)"
        if fails:
            self.stdout.write(self.style.ERROR(f"RESULTADO: {summary}"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f"RESULTADO: {summary}"))
