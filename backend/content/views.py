from django.conf import settings
from django.utils import translation
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import BlogPost, ImpactStat, Pillar, Project, Service, SiteSettings, TeamMember
from .serializers import (BlogPostListSerializer, BlogPostSerializer, ContactMessageSerializer, ImageUrlMixin,
                          ImpactStatSerializer, PillarSerializer, ProjectSerializer, ServiceSerializer,
                          TeamMemberSerializer)

SUPPORTED = {"es", "en", "pt"}
SITE_FIELDS = ("tagline", "about_title", "about_text", "projects_title", "projects_intro", "services_title",
               "services_intro", "impact_number", "impact_label", "team_title", "team_intro", "contact_title", "contact_intro",
               "whatsapp", "email", "instagram")


def get_lang(request):
    lang = request.query_params.get("lang", "es")
    return lang if lang in SUPPORTED else "es"


class SiteContentView(ImageUrlMixin, APIView):
    """Todo o conteúdo da home num único request: GET /api/site/?lang=es|en|pt"""

    def get(self, request):
        lang = get_lang(request)
        self.context = {"request": request}
        with translation.override(lang):
            s = SiteSettings.load()
            site = {f: getattr(s, f) for f in SITE_FIELDS} if s else {}
            if s:
                site["hero_image"] = self.image_url(s.hero_image)
                site["impact_image"] = self.image_url(s.impact_image)
            ctx = self.context
            data = {
                "lang": lang,
                "site": site,
                "pillars": PillarSerializer(Pillar.objects.filter(published=True), many=True).data,
                "projects": ProjectSerializer(Project.objects.filter(published=True), many=True, context=ctx).data,
                "services": ServiceSerializer(Service.objects.filter(published=True), many=True).data,
                "stats": ImpactStatSerializer(ImpactStat.objects.filter(published=True), many=True).data,
                "team": TeamMemberSerializer(TeamMember.objects.filter(published=True), many=True, context=ctx).data,
            }
        response = Response(data)
        response["Cache-Control"] = "public, max-age=60"
        return response


class BlogListView(APIView):
    """Entradas publicadas, mais recentes primeiro: GET /api/blog/?lang=es"""

    def get(self, request):
        lang = get_lang(request)
        with translation.override(lang):
            posts = BlogPostListSerializer(BlogPost.visible(), many=True, context={"request": request}).data
        response = Response({"lang": lang, "posts": posts})
        response["Cache-Control"] = "public, max-age=60"
        return response


class BlogPostView(APIView):
    """Uma entrada: GET /api/blog/<slug>/?lang=es"""

    def get(self, request, slug):
        lang = get_lang(request)
        post = BlogPost.visible().filter(slug=slug).first()
        if not post:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        with translation.override(lang):
            data = BlogPostSerializer(post, context={"request": request}).data
        response = Response(data)
        response["Cache-Control"] = "public, max-age=60"
        return response


class ContactView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact"

    def post(self, request):
        key = settings.CONTACT_API_KEY
        if key and request.headers.get("X-Contact-Key") != key:
            return Response({"detail": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        serializer = ContactMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("website"):  # robô preencheu o honeypot
            return Response({"ok": True}, status=status.HTTP_201_CREATED)
        serializer.save()
        return Response({"ok": True}, status=status.HTTP_201_CREATED)


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})
