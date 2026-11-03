"""Testes do cliente do CMS e dos cabeçalhos de diagnóstico. Rodar: cd frontend && python -m unittest discover -s tests -v"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
import _content  # noqa: E402
import index  # noqa: E402

GOOD = "https://escuelita-production.up.railway.app"
CMS_DATA = {"lang": "es", "site": {"about_text": "x"}, "pillars": [], "projects": [], "services": [], "stats": [], "team": []}


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload = status, payload if payload is not None else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise _content.requests.HTTPError(f"HTTP {self.status_code}")


def fake_backend(up_hosts, fail_with=None):
    """requests.get falso: só os hosts em up_hosts respondem; os outros dão erro de rede (ou fail_with)."""
    calls = []

    def get(url, **kw):
        calls.append(url)
        host = url.split("/api/")[0]
        if host not in up_hosts:
            raise (fail_with or _content.requests.ConnectionError("dns"))
        if url.endswith("/api/health/"):
            return FakeResponse(200, {"status": "ok"})
        if "/api/site/" in url:
            return FakeResponse(200, CMS_DATA)
        if url.endswith("/api/blog/"):
            return FakeResponse(200, {"posts": []})
        return FakeResponse(404, {})

    get.calls = calls
    return get


class Base(unittest.TestCase):
    def setUp(self):
        _content._cache.clear()
        _content._probe = (0.0, None, "")
        self.addCleanup(mock.patch.stopall)

    def env(self, **values):
        base = {k: v for k, v in os.environ.items() if k not in ("API_URL", "VERCEL")}
        p = mock.patch.dict(os.environ, {**base, **values}, clear=True)
        p.start()


class NormalizeTests(unittest.TestCase):
    def test_dirty_values_become_a_clean_host(self):
        n = _content.normalize_api_url
        self.assertEqual(n(GOOD), GOOD)
        self.assertEqual(n(GOOD + "/"), GOOD)
        self.assertEqual(n(f'  "{GOOD}"  \n'), GOOD)
        self.assertEqual(n(f"'{GOOD}'"), GOOD)
        self.assertEqual(n(GOOD + "/gestor-9fa656"), GOOD)
        self.assertEqual(n(GOOD + "/api/site/?lang=es"), GOOD)
        self.assertEqual(n("escuelita-production.up.railway.app"), GOOD)
        self.assertEqual(n("http://escuelita-production.up.railway.app"), GOOD)  # http -> https

    def test_local_http_is_kept_and_garbage_is_ignored(self):
        self.assertEqual(_content.normalize_api_url("http://127.0.0.1:8000/"), "http://127.0.0.1:8000")
        for junk in ("", "   ", None, "https://", '""'):
            self.assertEqual(_content.normalize_api_url(junk), "", repr(junk))


class FallbackTests(Base):
    def test_dev_without_api_url_uses_seed_and_is_not_degraded(self):
        self.env()
        data = _content.get_content("es")
        self.assertEqual(data["source"], "seed")
        self.assertFalse(_content.is_degraded(data))

    def test_configured_backend_that_works(self):
        self.env(API_URL=f' "{GOOD}/" ')
        with mock.patch("_content.requests.get", fake_backend({GOOD})):
            data = _content.get_content("es")
        self.assertEqual(data["source"], "cms")
        self.assertFalse(_content.is_degraded(data))

    def test_wrong_api_url_on_vercel_falls_back_to_production_backend(self):
        self.env(API_URL="https://escuelita-cms.up.railway.app", VERCEL="1")
        with mock.patch("_content.requests.get", fake_backend({GOOD})):
            data = _content.get_content("es")
        self.assertEqual(data["source"], "cms")

    def test_wrong_api_url_off_vercel_is_degraded_with_reason(self):
        self.env(API_URL="https://escuelita-cms.up.railway.app")
        with mock.patch("_content.requests.get", fake_backend({GOOD})):
            data = _content.get_content("es")
        self.assertTrue(_content.is_degraded(data))
        self.assertIn("ConnectionError", _content.error_of(data))
        self.assertIn("escuelita-cms", _content.error_of(data))

    def test_everything_down_is_degraded_for_content_and_blog(self):
        self.env(API_URL=GOOD, VERCEL="1")
        with mock.patch("_content.requests.get", fake_backend(set())):
            content = _content.get_content("es")
            posts = _content.get_blog("es")
        self.assertTrue(_content.is_degraded(content) and _content.is_degraded(posts))
        self.assertEqual(list(posts), [])
        self.assertIn("ConnectionError", _content.error_of(posts))

    def test_failed_probe_is_remembered_briefly_to_avoid_slow_pages(self):
        self.env(API_URL=GOOD)
        fake = fake_backend(set())
        with mock.patch("_content.requests.get", fake):
            _content.get_content("es")
            n = len(fake.calls)
            _content.get_blog("es")
        self.assertEqual(len(fake.calls), n)  # não sondou de novo

    def test_unknown_post_is_none_not_an_error(self):
        self.env(API_URL=GOOD)
        with mock.patch("_content.requests.get", fake_backend({GOOD})):
            self.assertIsNone(_content.get_post("es", "nao-existe"))

    def test_contact_uses_the_working_backend_and_trims_the_key(self):
        self.env(API_URL="https://wrong.example.com", VERCEL="1", CONTACT_API_KEY="  k123\n")
        with mock.patch("_content.requests.get", fake_backend({GOOD})), \
                mock.patch("_content.requests.post", return_value=FakeResponse(201)) as post:
            self.assertTrue(_content.send_contact({"name": "a"}))
        self.assertTrue(post.call_args.args[0].startswith(GOOD))
        self.assertEqual(post.call_args.kwargs["headers"]["X-Contact-Key"], "k123")

    def test_contact_rejected_by_backend_returns_false(self):
        self.env(API_URL=GOOD)
        with mock.patch("_content.requests.get", fake_backend({GOOD})), \
                mock.patch("_content.requests.post", return_value=FakeResponse(403)):
            self.assertFalse(_content.send_contact({"name": "a"}))


class HeaderTests(Base):
    def setUp(self):
        super().setUp()
        self.client = index.app.test_client()

    def test_healthy_cms_sets_source_cms_without_error_header(self):
        self.env(API_URL=GOOD)
        with mock.patch("_content.requests.get", fake_backend({GOOD})):
            r = self.client.get("/es/")
        self.assertEqual(r.headers["X-Content-Source"], "cms")
        self.assertNotIn("X-Content-Error", r.headers)
        self.assertIn("s-maxage=60", r.headers["Cache-Control"])

    def test_fallback_in_use_is_flagged_in_a_header(self):
        self.env(API_URL="https://escuelita-cms.up.railway.app", VERCEL="1")
        with mock.patch("_content.requests.get", fake_backend({GOOD})):
            r = self.client.get("/es/")
        self.assertEqual(r.headers["X-Content-Source"], "cms")  # o site funciona...
        self.assertIn("incorreta", r.headers["X-Content-Warning"])  # ...mas o erro de configuração aparece
        self.assertIn(GOOD, r.headers["X-Content-Warning"])

    def test_missing_api_url_on_vercel_is_flagged_and_correct_one_is_not(self):
        self.env(VERCEL="1")
        with mock.patch("_content.requests.get", fake_backend({GOOD})):
            self.assertIn("ausente", self.client.get("/es/").headers["X-Content-Warning"])
        _content._probe = (0.0, None, "")
        self.env(API_URL=GOOD, VERCEL="1")
        with mock.patch("_content.requests.get", fake_backend({GOOD})):
            self.assertNotIn("X-Content-Warning", self.client.get("/es/").headers)

    def test_broken_cms_reports_reason_and_short_cache(self):
        self.env(API_URL="https://escuelita-cms.up.railway.app")
        with mock.patch("_content.requests.get", fake_backend(set())):
            for path in ("/es/", "/es/proyectos/", "/es/blog/"):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200, path)  # o site continua no ar
                self.assertEqual(r.headers["X-Content-Source"], "degraded", path)
                self.assertIn("escuelita-cms", r.headers["X-Content-Error"], path)
                self.assertIn("s-maxage=10", r.headers["Cache-Control"], path)


if __name__ == "__main__":
    unittest.main()
