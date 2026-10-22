"""Gestor de conteúdo (Django admin com o tema Unfold, em espanhol).

Os campos traduzíveis aparecem em abas por idioma; o resto fica abaixo, comum aos três.
"""
import re

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.db import models
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from modeltranslation.admin import TranslationAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.decorators import action, display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from unfold.widgets import UnfoldAdminTextareaWidget

from .models import BlogPost, ContactMessage, ImpactStat, Pillar, Project, Service, SiteSettings, TeamMember

LANGS = (("es", "Español"), ("en", "English"), ("pt", "Português"))
EDITORS_GROUP = "Editores"


def lang_tabs(*fields, note=None):
    """Uma aba por idioma com os campos traduzíveis. Inglês e português são opcionais."""
    tabs = []
    for code, name in LANGS:
        opts = {"fields": [f"{f}_{code}" for f in fields], "classes": ["tab"]}
        if code != "es":
            opts["description"] = note or "Opcional. Si lo dejas vacío, se muestra el texto en español."
        tabs.append((name, opts))
    return tuple(tabs)


def tab(title, *fields, description=None):
    """Aba comum (não traduzível) do formulário."""
    opts = {"fields": list(fields), "classes": ["tab"]}
    if description:
        opts["description"] = description
    return ((title, opts),)


def thumb(url, w=64, h=40, radius=8):
    if not url:
        return "—"
    return format_html('<img src="{}" style="width:{}px;height:{}px;object-fit:cover;border-radius:{}px">',
                       url, w, h, radius)


class BaseAdmin(ModelAdmin, TranslationAdmin):
    compressed_fields = True
    warn_unsaved_form = True

    labels = {}  # rótulos mais claros que o verbose_name do modelo, por campo

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.TextField) and "widget" not in kwargs:
            rows = 7 if db_field.name.startswith(("about_text", "text", "summary", "bio")) else 3
            kwargs["widget"] = UnfoldAdminTextareaWidget(attrs={"rows": rows})
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field is not None and field.label:
            # A aba já indica o idioma: "Título [es]" vira "Título"
            base = re.sub(r"_(es|en|pt)$", "", db_field.name)
            field.label = self.labels.get(base) or re.sub(r"\s*\[(es|en|pt)\]$", "", str(field.label))
        return field


class OrderableAdmin(BaseAdmin):
    list_editable = ("order", "published")
    list_filter_submit = True
    ordering = ("order", "id")

    @action(description="Mostrar en el sitio", icon="visibility")
    def make_published(self, request, queryset):
        queryset.update(published=True)

    @action(description="Ocultar del sitio", icon="visibility_off")
    def make_hidden(self, request, queryset):
        queryset.update(published=False)

    actions = ("make_published", "make_hidden")


# --- Textos generales (registro único) -----------------------------------------
@admin.register(SiteSettings)
class SiteSettingsAdmin(BaseAdmin):
    labels = {
        "about_text": "Presentación (sección Nosotros, al lado del video)",
        "impact_label": "Texto de la cifra principal (ej. personas impactadas)",
        "projects_title": "Título de Proyectos", "projects_intro": "Introducción de Proyectos",
        "services_title": "Título de Servicios", "services_intro": "Introducción de Servicios",
        "team_title": "Título de Equipo", "team_intro": "Introducción de Equipo",
        "contact_intro": "Texto de Contacto (sobre el formulario)",
        "hero_image": "Fondo de la portada (opcional)", "impact_number": "Cifra principal (ej. +1000)",
    }
    fieldsets = lang_tabs(
        "about_text", "impact_label", "projects_title", "projects_intro",
        "services_title", "services_intro", "team_title", "team_intro", "contact_intro",
    ) + tab("Portada, cifra y contacto", "hero_image", "impact_number", "whatsapp", "email", "instagram")

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Só existe um registro: abre direto o formulário
        obj = SiteSettings.load()
        if obj:
            return redirect(reverse("admin:content_sitesettings_change", args=[obj.pk]))
        return redirect(reverse("admin:content_sitesettings_add"))


# --- Secciones del sitio --------------------------------------------------------
@admin.register(Pillar)
class PillarAdmin(OrderableAdmin):
    list_display = ("title", "icon", "order", "published")
    fieldsets = lang_tabs("title", "text") + tab("Opciones", "icon", "order", "published")


@admin.register(Project)
class ProjectAdmin(OrderableAdmin):
    list_display = ("image_thumb", "title", "partner", "year", "featured", "order", "published")
    list_display_links = ("image_thumb", "title")
    list_editable = ("featured", "order", "published")
    list_filter = ("featured", "published", "year")
    search_fields = ("title_es", "title_en", "title_pt", "partner_es")
    fieldsets = lang_tabs("title", "partner", "summary") + tab(
        "Imagen y opciones", "image", "year", "featured", "order", "published")

    @display(description="")
    def image_thumb(self, obj):
        return thumb(obj.image.url if obj.image else None)


@admin.register(Service)
class ServiceAdmin(OrderableAdmin):
    list_display = ("title", "order", "published")
    fieldsets = lang_tabs("title", "description") + tab("Opciones", "order", "published")


@admin.register(ImpactStat)
class ImpactStatAdmin(OrderableAdmin):
    list_display = ("value", "label", "order", "published")
    fieldsets = tab("Cifra", "value", "order", "published") + lang_tabs("label")


@admin.register(TeamMember)
class TeamMemberAdmin(OrderableAdmin):
    list_display = ("photo_thumb", "name", "role", "order", "published")
    list_display_links = ("photo_thumb", "name")
    search_fields = ("name", "role_es")
    fieldsets = tab("Persona", "name", "photo", "linkedin", "order", "published") + lang_tabs("role", "bio")

    @display(description="")
    def photo_thumb(self, obj):
        return thumb(obj.photo.url if obj.photo else None, 40, 50)


# --- Blog -------------------------------------------------------------------------
@admin.register(BlogPost)
class BlogPostAdmin(BaseAdmin):
    list_display = ("cover_thumb", "title", "published_at", "status")
    list_display_links = ("cover_thumb", "title")
    list_filter = ("published",)
    list_filter_submit = True
    search_fields = ("title_es", "title_en", "title_pt", "author")
    date_hierarchy = "published_at"
    readonly_fields = ("slug", "updated_at")
    fieldsets = lang_tabs("title", "excerpt", "body") + tab(
        "Portada y publicación", "cover", "author", "published", "published_at", "slug", "updated_at",
        description="Marca «Publicado» para que aparezca en el sitio. Con una fecha futura, se publica sola ese día.")
    actions = ("publish", "unpublish")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name.startswith("body"):
            kwargs["widget"] = WysiwygWidget
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @display(description="")
    def cover_thumb(self, obj):
        return thumb(obj.cover.url if obj.cover else None, 64, 36)

    @display(description="Estado", label={"En el sitio": "success", "Programada": "info", "Borrador": "warning"})
    def status(self, obj):
        if not obj.published:
            return "Borrador"
        return "Programada" if obj.published_at > timezone.now() else "En el sitio"

    @action(description="Publicar", icon="publish")
    def publish(self, request, queryset):
        n = queryset.update(published=True)
        messages.success(request, f"{n} entrada(s) publicada(s).")

    @action(description="Pasar a borrador", icon="draft")
    def unpublish(self, request, queryset):
        n = queryset.update(published=False)
        messages.success(request, f"{n} entrada(s) pasada(s) a borrador.")


# --- Mensajes del formulario ----------------------------------------------------------
@admin.register(ContactMessage)
class ContactMessageAdmin(ModelAdmin):
    list_display = ("name", "subject", "email", "created_at", "state")
    list_filter = ("handled", "language")
    list_filter_submit = True
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("name", "email", "subject", "message", "language", "created_at")
    fields = ("name", "email", "subject", "message", "language", "created_at", "handled")
    actions = ("mark_handled",)

    def has_add_permission(self, request):
        return False

    @display(description="Estado", label={"Respondido": "success", "Nuevo": "danger"})
    def state(self, obj):
        return "Respondido" if obj.handled else "Nuevo"

    @action(description="Marcar como respondido", icon="done_all")
    def mark_handled(self, request, queryset):
        queryset.update(handled=True)


# --- Usuarios y roles -------------------------------------------------------------------
admin.site.unregister(User)
admin.site.unregister(Group)

ROLE_CHOICES = (
    ("editor", "Editor/a: edita el sitio y el blog"),
    ("admin", "Administrador/a: además crea y gestiona usuarios"),
)


class NewUserForm(UserCreationForm):
    role = forms.ChoiceField(label="Rol", choices=ROLE_CHOICES, initial="editor", widget=forms.RadioSelect)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = NewUserForm
    change_password_form = AdminPasswordChangeForm
    list_display = ("username", "full_name", "email", "role_label", "is_active", "last_login")
    list_filter = ("is_superuser", "is_active")
    list_filter_submit = True
    fieldsets = (
        ("Datos", {"fields": ("username", "first_name", "last_name", "email", "password")}),
        ("Acceso", {
            "fields": ("is_active", "is_superuser", "groups"),
            "description": "«Administrador/a» puede crear usuarios. Para editar contenido basta el grupo «Editores».",
        }),
        ("Historial", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"fields": ("first_name", "last_name", "email", "username", "role", "password1", "password2")}),
    )
    readonly_fields = ("last_login", "date_joined")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        labels = {
            "is_superuser": ("Administrador/a", "Acceso total, incluida la gestión de usuarios."),
            "is_active": ("Activo", "Desmárcalo para bloquear el acceso sin borrar la cuenta."),
            "groups": ("Grupos", None),
        }
        if field and db_field.name in labels:
            field.label, help_text = labels[db_field.name]
            if help_text:
                field.help_text = help_text
        return field

    @display(description="Nombre")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    @display(description="Rol", label={"Administrador/a": "primary", "Editor/a": "info", "Sin rol": "warning"})
    def role_label(self, obj):
        if obj.is_superuser:
            return "Administrador/a"
        return "Editor/a" if obj.groups.filter(name=EDITORS_GROUP).exists() else "Sin rol"

    def save_model(self, request, obj, form, change):
        obj.is_staff = True  # todo usuario creado aquí puede entrar al gestor
        if not change:
            obj.is_superuser = form.cleaned_data.get("role") == "admin"
        super().save_model(request, obj, form, change)
        if not change and not obj.is_superuser:
            group, _ = Group.objects.get_or_create(name=EDITORS_GROUP)
            obj.groups.add(group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
