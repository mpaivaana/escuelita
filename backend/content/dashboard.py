"""Painel inicial, contadores do menu lateral e permissões do gestor."""
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import BlogPost, ContactMessage, Project, SiteSettings, TeamMember


def is_superuser(request):
    return request.user.is_superuser


def can_edit_site(request):
    return request.user.has_perm("content.change_sitesettings")


def badge_drafts(request):
    n = BlogPost.objects.filter(published=False).count()
    return n or None


def badge_messages(request):
    n = ContactMessage.objects.filter(handled=False).count()
    return n or None


def dashboard_callback(request, context):
    now = timezone.now()
    posts = BlogPost.objects.all()
    site = SiteSettings.load()
    context.update({
        "frontend_url": settings.FRONTEND_URL,
        "greeting_name": request.user.first_name or request.user.username,
        "stats": [
            {"label": "Entradas publicadas", "value": posts.filter(published=True, published_at__lte=now).count(),
             "icon": "article", "link": reverse("admin:content_blogpost_changelist") + "?published__exact=1"},
            {"label": "Borradores", "value": posts.filter(published=False).count(),
             "icon": "edit_note", "link": reverse("admin:content_blogpost_changelist") + "?published__exact=0"},
            {"label": "Mensajes nuevos", "value": ContactMessage.objects.filter(handled=False).count(),
             "icon": "mail", "link": reverse("admin:content_contactmessage_changelist") + "?handled__exact=0"},
            {"label": "Proyectos en el sitio", "value": Project.objects.filter(published=True).count(),
             "icon": "folder_open", "link": reverse("admin:content_project_changelist")},
        ],
        "shortcuts": [
            {"title": "Escribir una entrada", "text": "Publica novedades e historias en el blog.",
             "icon": "edit_square", "link": reverse("admin:content_blogpost_add")},
            {"title": "Textos del sitio", "text": "Presentación, títulos, cifra principal y contactos.",
             "icon": "tune", "link": reverse("admin:content_sitesettings_change", args=[site.pk])
             if site else reverse("admin:content_sitesettings_add")},
            {"title": "Equipo", "text": "Fotos, cargos y presentaciones de las personas.",
             "icon": "groups", "link": reverse("admin:content_teammember_changelist")},
            {"title": "Proyectos", "text": "Iniciativas que aparecen en la portada.",
             "icon": "folder_open", "link": reverse("admin:content_project_changelist")},
        ],
        "recent_posts": posts.order_by("-updated_at")[:5],
        "recent_messages": ContactMessage.objects.order_by("-created_at")[:5],
    })
    return context
