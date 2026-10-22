"""Configuração do CMS de La Escuelita Ambiental Móvil."""
import os
from pathlib import Path

import dj_database_url
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-insecure-key")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.up.railway.app")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "https://*.up.railway.app")

INSTALLED_APPS = [
    "unfold",  # tema do gestor: precisa vir antes do admin
    "unfold.contrib.forms",
    "modeltranslation",  # precisa vir antes do admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "content",
]

USE_CLOUDINARY = bool(os.getenv("CLOUDINARY_URL"))
if USE_CLOUDINARY:
    INSTALLED_APPS += ["cloudinary_storage", "cloudinary"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# Banco: Neon (Postgres serverless). conn_max_age baixo porque a Neon hiberna.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# Idiomas: espanhol é o principal (fallback de tudo).
LANGUAGE_CODE = "es"  # o gestor fica sempre em espanhol (a API escolhe o idioma por ?lang=)
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGES = [("es", _("Español")), ("en", _("English")), ("pt", _("Português"))]
MODELTRANSLATION_DEFAULT_LANGUAGE = "es"
MODELTRANSLATION_FALLBACK_LANGUAGES = ("es",)
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"
        if USE_CLOUDINARY
        else "django.core.files.storage.FileSystemStorage"
    },
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5000")
CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS"]

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {"contact": "10/hour"},
}

CONTACT_API_KEY = os.getenv("CONTACT_API_KEY", "")

# Endereço do gestor de conteúdo. Em produção use algo difícil de adivinhar, ex. "gestor-8f3k2q".
ADMIN_PATH = os.getenv("ADMIN_PATH", "admin").strip("/") + "/"

# Endereço público do site (botões "Ver el sitio" e "Ver en el sitio" do gestor)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5000").rstrip("/")


def _static(path):
    return lambda request: static(path)


def _nav(title, icon, url_name, **extra):
    return {"title": title, "icon": icon, "link": reverse_lazy(url_name), **extra}


# Visual e menu do gestor (tema Unfold), nas cores da Escuelita
UNFOLD = {
    "SITE_TITLE": "Gestor de La Escuelita",
    "SITE_HEADER": "La Escuelita",
    "SITE_SUBHEADER": "Gestor de contenido",
    "SITE_URL": FRONTEND_URL,
    "SITE_LOGO": {"light": _static("admin_custom/logo-verde.svg"), "dark": _static("admin_custom/logo-blanco.svg")},
    "SITE_SYMBOL": "eco",
    "SITE_FAVICONS": [
        {"rel": "icon", "sizes": "any", "type": "image/svg+xml", "href": _static("admin_custom/isotipo.svg")},
        {"rel": "icon", "sizes": "32x32", "type": "image/png", "href": _static("admin_custom/favicon-32.png")},
        {"rel": "apple-touch-icon", "href": _static("admin_custom/apple-touch-icon.png")},
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "STYLES": [_static("admin_custom/escuelita.css")],
    "LOGIN": {"image": _static("admin_custom/login.jpg")},
    "DASHBOARD_CALLBACK": "content.dashboard.dashboard_callback",
    "COLORS": {
        "base": {
            "50": "oklch(98.5% .008 91.5)", "100": "oklch(95.8% .012 91.5)", "200": "oklch(91.5% .013 92)",
            "300": "oklch(86% .014 95)", "400": "oklch(70% .018 140)", "500": "oklch(55% .02 155)",
            "600": "oklch(45.2% .024 159)", "700": "oklch(37% .022 162)", "800": "oklch(28% .02 164)",
            "900": "oklch(23.5% .018 165)", "950": "oklch(15% .015 165)",
        },
        "primary": {
            "50": "oklch(97.5% .02 160)", "100": "oklch(94% .04 160)", "200": "oklch(88.5% .07 160)",
            "300": "oklch(80% .1 160)", "400": "oklch(68% .12 160)", "500": "oklch(57.2% .114 159)",
            "600": "oklch(51.7% .105 159.6)", "700": "oklch(45% .095 160)", "800": "oklch(41.7% .085 160)",
            "900": "oklch(34% .07 160)", "950": "oklch(25% .05 160)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {"items": [_nav("Inicio", "space_dashboard", "admin:index")]},
            {"title": "Blog", "items": [
                _nav("Entradas", "article", "admin:content_blogpost_changelist",
                     badge="content.dashboard.badge_drafts"),
                _nav("Nueva entrada", "edit_square", "admin:content_blogpost_add"),
            ]},
            {"title": "Contenido del sitio", "items": [
                _nav("Textos generales", "tune", "admin:content_sitesettings_changelist",
                     permission="content.dashboard.can_edit_site"),
                _nav("Misión, visión y valores", "flag", "admin:content_pillar_changelist"),
                _nav("Cifras de impacto", "monitoring", "admin:content_impactstat_changelist"),
                _nav("Proyectos", "folder_open", "admin:content_project_changelist"),
                _nav("Servicios", "handshake", "admin:content_service_changelist"),
                _nav("Equipo", "groups", "admin:content_teammember_changelist"),
            ]},
            {"title": "Mensajes", "items": [
                _nav("Formulario de contacto", "mail", "admin:content_contactmessage_changelist",
                     badge="content.dashboard.badge_messages"),
            ]},
            {"title": "Accesos", "items": [
                _nav("Usuarios", "person", "admin:auth_user_changelist", permission="content.dashboard.is_superuser"),
                _nav("Grupos y permisos", "admin_panel_settings", "admin:auth_group_changelist",
                     permission="content.dashboard.is_superuser"),
            ]},
        ],
    },
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
