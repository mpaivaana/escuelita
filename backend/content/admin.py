from django.contrib import admin
from django.utils.html import format_html
from modeltranslation.admin import TabbedTranslationAdmin

from .models import ContactMessage, ImpactStat, Pillar, Project, Service, SiteSettings, TeamMember


class BaseAdmin(TabbedTranslationAdmin):
    """Cada campo traduzível aparece em abas: Español / English / Português."""

    class Media:
        css = {"all": ("admin_custom/escuelita.css",)}


@admin.register(SiteSettings)
class SiteSettingsAdmin(BaseAdmin):
    fieldsets = (
        ("Portada", {"fields": ("tagline", "hero_image")}),
        ("Quiénes somos", {"fields": ("about_title", "about_text")}),
        ("Proyectos", {"fields": ("projects_title", "projects_intro")}),
        ("Servicios", {"fields": ("services_title", "services_intro")}),
        ("Impacto", {"fields": ("impact_number", "impact_label", "impact_image")}),
        ("Equipo", {"fields": ("team_title", "team_intro")}),
        ("Contacto y redes", {"fields": ("contact_title", "contact_intro", "whatsapp", "email", "instagram")}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class OrderableAdmin(BaseAdmin):
    list_editable = ("order", "published")


@admin.register(Pillar)
class PillarAdmin(OrderableAdmin):
    list_display = ("title", "icon", "order", "published")


@admin.register(Project)
class ProjectAdmin(OrderableAdmin):
    list_display = ("thumb", "title", "partner", "year", "featured", "order", "published")
    list_display_links = ("thumb", "title")
    list_editable = ("featured", "order", "published")
    list_filter = ("featured", "published", "year")
    search_fields = ("title_es", "title_en", "title_pt", "partner")
    readonly_fields = ("slug",)

    @admin.display(description="")
    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width:64px;height:40px;object-fit:cover;border-radius:6px">',
                               obj.image.url)
        return "—"


@admin.register(Service)
class ServiceAdmin(OrderableAdmin):
    list_display = ("title", "order", "published")


@admin.register(ImpactStat)
class ImpactStatAdmin(OrderableAdmin):
    list_display = ("value", "label", "order", "published")


@admin.register(TeamMember)
class TeamMemberAdmin(OrderableAdmin):
    list_display = ("thumb", "name", "role", "order", "published")
    list_display_links = ("thumb", "name")
    search_fields = ("name", "role_es")

    @admin.display(description="")
    def thumb(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="width:40px;height:50px;object-fit:cover;border-radius:6px">',
                               obj.photo.url)
        return "—"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "name", "email", "subject", "language", "handled")
    list_filter = ("handled", "language")
    list_editable = ("handled",)
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("name", "email", "subject", "message", "language", "created_at")

    def has_add_permission(self, request):
        return False
