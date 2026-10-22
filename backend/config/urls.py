from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.templatetags.static import static as static_url
from django.urls import include, path

admin.site.site_header = "La Escuelita Ambiental Móvil"
admin.site.site_title = "Escuelita · Gestor de contenido"
admin.site.index_title = "Contenido del sitio"

urlpatterns = [
    # Sem página inicial: o gestor só abre pelo endereço definido em ADMIN_PATH
    path("favicon.ico", lambda r: redirect(static_url("admin_custom/favicon.ico"))),
    path("robots.txt", lambda r: HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")),
    path(settings.ADMIN_PATH, admin.site.urls),
    path("api/", include("content.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
