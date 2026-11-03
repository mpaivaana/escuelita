"""Testes de regressão do CMS e da API pública. Rodar: python manage.py test"""
import io
import shutil
import tempfile
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import BlogPost, ContactMessage, SiteSettings, TeamMember

KEY = {"HTTP_X_CONTACT_KEY": "k123"}
GOOD = {"name": "Ana", "email": "ana@example.com", "subject": "Hola", "message": "Mensaje", "language": "pt"}


def png(name="c.png"):
    buf = io.BytesIO()
    Image.new("RGB", (32, 18), (20, 120, 60)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), "image/png")


class SeededTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=StringIO())


class PublicApiTests(SeededTestCase):
    def test_site_content_in_each_language(self):
        for lang in ("es", "en", "pt"):
            data = self.client.get("/api/site/", {"lang": lang}).json()
            self.assertEqual(data["lang"], lang)
            self.assertTrue(data["site"]["about_text"])
            self.assertTrue(data["pillars"] and data["services"] and data["stats"] and data["team"])

    def test_unknown_language_falls_back_to_spanish(self):
        self.assertEqual(self.client.get("/api/site/", {"lang": "xx"}).json()["lang"], "es")

    def test_unpublished_items_are_hidden(self):
        TeamMember.objects.update(published=False)
        self.assertEqual(self.client.get("/api/site/").json()["team"], [])

    def test_health(self):
        self.assertEqual(self.client.get("/api/health/").json(), {"status": "ok"})


class BlogTests(SeededTestCase):
    def test_draft_and_scheduled_posts_are_not_public(self):
        BlogPost.objects.create(title_es="Borrador", body_es="x", published=False)
        BlogPost.objects.create(title_es="Futuro", body_es="x", published=True,
                                published_at=timezone.now() + timedelta(days=3))
        ok = BlogPost.objects.create(title_es="Publicado", body_es="x", published=True)
        slugs = [p["slug"] for p in self.client.get("/api/blog/").json()["posts"]]
        self.assertEqual(slugs, [ok.slug])
        self.assertEqual(self.client.get("/api/blog/borrador/").status_code, 404)
        self.assertEqual(self.client.get("/api/blog/futuro/").status_code, 404)

    def test_slugs_are_unique_and_body_is_sanitized(self):
        a = BlogPost.objects.create(title_es="Hola mundo", body_es="<p>ok</p><script>alert(1)</script>", published=True)
        b = BlogPost.objects.create(title_es="Hola mundo", body_es="x", published=True)
        self.assertEqual((a.slug, b.slug), ("hola-mundo", "hola-mundo-2"))
        self.assertNotIn("<script", a.body_es)

    def test_translation_falls_back_to_spanish(self):
        p = BlogPost.objects.create(title_es="Solo es", body_es="<p>es</p>", published=True)
        self.assertEqual(self.client.get(f"/api/blog/{p.slug}/", {"lang": "pt"}).json()["title"], "Solo es")


@override_settings(CONTACT_API_KEY="k123")
class ContactTests(TestCase):
    def post(self, data=None, **extra):
        return self.client.post("/api/contact/", data or GOOD, content_type="application/json", **extra)

    def test_requires_shared_key(self):
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.post(HTTP_X_CONTACT_KEY="errada").status_code, 403)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_saves_valid_message(self):
        self.assertEqual(self.post(**KEY).status_code, 201)
        self.assertEqual(ContactMessage.objects.get().language, "pt")

    def test_rejects_bad_email_and_huge_message(self):
        self.assertEqual(self.post({**GOOD, "email": "x"}, **KEY).status_code, 400)
        self.assertEqual(self.post({**GOOD, "message": "a" * 5001}, **KEY).status_code, 400)

    def test_honeypot_is_silently_dropped(self):
        self.assertEqual(self.post({**GOOD, "website": "spam"}, **KEY).status_code, 201)
        self.assertEqual(ContactMessage.objects.count(), 0)


class CmsTests(SeededTestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("root", "r@x.com", "Pass12345!")
        self.editor = User.objects.create_user("ed", password="Pass12345!", is_staff=True)
        self.editor.groups.add(Group.objects.get(name="Editores"))

    def test_every_admin_page_renders_for_admin(self):
        self.client.force_login(self.admin)
        for model in ("pillar", "project", "service", "impactstat", "teammember", "blogpost", "contactmessage"):
            self.assertEqual(self.client.get(reverse(f"admin:content_{model}_changelist")).status_code, 200, model)
        for model in ("pillar", "project", "service", "impactstat", "teammember", "blogpost"):
            self.assertEqual(self.client.get(reverse(f"admin:content_{model}_add")).status_code, 200, model)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_editor_cannot_manage_users(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(reverse("admin:content_blogpost_add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:auth_user_changelist")).status_code, 403)

    def test_tagline_is_editable_in_cms_and_reaches_the_api(self):
        self.client.force_login(self.admin)
        site = SiteSettings.load()
        url = reverse("admin:content_sitesettings_change", args=[site.pk])
        self.assertContains(self.client.get(url), 'name="tagline"')
        data = {f"{f}_{lang}": getattr(site, f"{f}_{lang}") or "" for lang in ("es", "en", "pt")
                for f in ("about_text", "impact_label", "projects_title", "projects_intro", "services_title",
                          "services_intro", "team_title", "team_intro", "contact_intro")}
        data.update(tagline="Aprender jugando", impact_number="+1000", whatsapp="", email="", instagram="")
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.get("/api/site/").json()["site"]["tagline"], "Aprender jugando")

    def test_instagram_accepts_at_sign_or_full_url(self):
        site = SiteSettings.load()
        for typed in ("@laescuelita", "https://www.instagram.com/laescuelita/?hl=es", " laescuelita "):
            site.instagram = typed
            site.save()
            self.assertEqual(SiteSettings.load().instagram, "laescuelita", typed)

    def test_blog_post_with_cover_via_admin(self):
        media = tempfile.mkdtemp()  # não deixa lixo na pasta media/ de desenvolvimento
        self.addCleanup(shutil.rmtree, media, True)
        with override_settings(MEDIA_ROOT=media):
            self._create_post_with_cover()

    def _create_post_with_cover(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("admin:content_blogpost_add"), {
            "title_es": "Primer post", "title_en": "", "title_pt": "", "excerpt_es": "", "excerpt_en": "", "excerpt_pt": "",
            "body_es": "<p>Hola</p>", "body_en": "", "body_pt": "", "author": "Ana", "published": "on",
            "published_at_0": "2026-01-01", "published_at_1": "10:00:00", "cover": png()})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(BlogPost.objects.get(slug="primer-post").cover.name.startswith("blog/"))


class SeedTests(TestCase):
    def run_seed(self, *args):
        call_command("seed_content", *args, stdout=StringIO())

    def test_deleted_team_is_not_resurrected_by_the_next_deploy(self):
        self.run_seed()
        self.assertEqual(TeamMember.objects.count(), 4)
        TeamMember.objects.all().delete()
        self.run_seed()  # o start command da Railway roda isto a cada deploy
        self.assertEqual(TeamMember.objects.count(), 0)

    def test_team_flag_is_still_available_for_legacy_databases(self):
        self.run_seed()
        TeamMember.objects.all().delete()
        self.run_seed("--team")
        self.assertEqual(TeamMember.objects.count(), 4)


@override_settings(DEBUG=True)  # o runner força DEBUG=False; aqui simulamos um ambiente de desenvolvimento saudável
class CheckIntegrationsTests(SeededTestCase):
    def run_check(self, *args):
        out = StringIO()
        try:
            call_command("check_integrations", *args, stdout=out)
            code = 0
        except SystemExit as exc:
            code = exc.code
        return code, out.getvalue()

    def test_fails_without_an_admin_and_passes_with_one(self):
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("administradores ativos: 0", out)
        User.objects.create_superuser("root", "r@x.com", "Pass12345!")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("nada foi gravado", out)
        self.assertFalse(ContactMessage.objects.exists())  # o teste de escrita é revertido

    def test_detects_broken_image_references(self):
        User.objects.create_superuser("root", "r@x.com", "Pass12345!")
        from .models import Project
        Project.objects.filter(pk=Project.objects.first().pk).update(image="projects/sumiu.png")
        code, out = self.run_check("--check-urls")
        self.assertEqual(code, 1)
        self.assertIn("imagem quebrada", out)

    @override_settings(USE_CLOUDINARY=False, DEBUG=False)
    def test_ephemeral_disk_storage_is_a_failure_in_production(self):
        User.objects.create_superuser("root", "r@x.com", "Pass12345!")
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("SE PERDEM a cada deploy", out)

    @override_settings(USE_CLOUDINARY=True)
    def test_cloudinary_path_pings_and_upload_test_is_cleaned_up(self):
        User.objects.create_superuser("root", "r@x.com", "Pass12345!")
        with mock.patch("cloudinary.api.ping", return_value={"status": "ok"}) as ping, \
                mock.patch("content.management.commands.check_integrations.http_status", return_value=(200, {})), \
                mock.patch("content.management.commands.check_integrations.default_storage") as storage:
            storage.save.return_value = "healthcheck/integration-test"
            storage.url.return_value = "https://res.cloudinary.com/x/image/upload/v1/healthcheck/integration-test"
            code, out = self.run_check("--write-test")
        ping.assert_called_once()
        storage.delete.assert_called_once_with("healthcheck/integration-test")
        self.assertIn("URL pública responde 200", out)
        self.assertEqual(code, 0, out)
