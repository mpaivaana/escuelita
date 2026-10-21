"""Modelos editáveis pelo CMS.

Os campos de texto marcados em translation.py ganham automaticamente versões
_es, _en e _pt no banco (django-modeltranslation).
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Orderable(models.Model):
    order = models.PositiveIntegerField("orden", default=0, help_text="Menor número aparece primero.")
    published = models.BooleanField("publicado", default=True)

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class SiteSettings(models.Model):
    """Textos gerais do site. Existe apenas um registro."""

    tagline = models.CharField("firma bajo el logo", max_length=120, blank=True, default="")
    hero_image = models.ImageField("fondo de la portada", upload_to="site/", blank=True,
                                   help_text="Opcional. Si está vacío se usa la pizarra con flores.")

    about_title = models.CharField("título · quiénes somos", max_length=120)
    about_text = models.TextField("texto · quiénes somos")

    projects_title = models.CharField("título · proyectos", max_length=120)
    projects_intro = models.TextField("introducción · proyectos", blank=True)

    services_title = models.CharField("título · servicios", max_length=120)
    services_intro = models.TextField("introducción · servicios", blank=True)

    impact_number = models.CharField("cifra principal de impacto", max_length=20, default="+1000")
    impact_label = models.CharField("texto de la cifra principal", max_length=120)
    impact_image = models.ImageField("foto de impacto", upload_to="site/", blank=True)

    team_title = models.CharField("título · equipo", max_length=120, default="Nuestro equipo")
    team_intro = models.TextField("introducción · equipo", blank=True)

    contact_title = models.CharField("título · contacto", max_length=120)
    contact_intro = models.TextField("introducción · contacto", blank=True)

    whatsapp = models.CharField("WhatsApp", max_length=30, blank=True, help_text="Con código de país, ej. +51 999 999 999")
    email = models.EmailField("correo", blank=True)
    instagram = models.CharField("Instagram", max_length=60, blank=True, help_text="Solo el usuario, sin @")

    class Meta:
        verbose_name = "configuración general"
        verbose_name_plural = "configuración general"

    def __str__(self):
        return "Textos generales del sitio"

    def clean(self):
        if not self.pk and SiteSettings.objects.exists():
            raise ValidationError("Ya existe una configuración. Edita la existente.")

    @classmethod
    def load(cls):
        return cls.objects.first()


class Pillar(Orderable):
    ICONS = [("hands", "Manos / cuidado"), ("target", "Objetivo"), ("globe", "Planeta"), ("leaf", "Hoja")]
    title = models.CharField("título", max_length=80)
    text = models.TextField("texto")
    icon = models.CharField("ícono", max_length=20, choices=ICONS, default="leaf")

    class Meta(Orderable.Meta):
        verbose_name = "pilar (misión, visión, valores)"
        verbose_name_plural = "pilares (misión, visión, valores)"

    def __str__(self):
        return self.title


class Project(Orderable):
    title = models.CharField("título", max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    partner = models.CharField("en colaboración con", max_length=120, blank=True,
                               help_text="Nombre de la institución aliada.")
    summary = models.TextField("resumen", blank=True)
    image = models.ImageField("imagen", upload_to="projects/", blank=True)
    year = models.PositiveIntegerField("año", blank=True, null=True)
    featured = models.BooleanField("destacado en la portada", default=True)

    class Meta(Orderable.Meta):
        verbose_name = "proyecto"
        verbose_name_plural = "proyectos"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title_es or self.title)[:140]
        super().save(*args, **kwargs)


class Service(Orderable):
    title = models.CharField("título", max_length=120)
    description = models.TextField("descripción")

    class Meta(Orderable.Meta):
        verbose_name = "servicio"
        verbose_name_plural = "servicios"

    def __str__(self):
        return self.title


class ImpactStat(Orderable):
    value = models.CharField("cifra", max_length=20, help_text="Ej. +10")
    label = models.CharField("qué se mide", max_length=80, help_text="Ej. empresas aliadas")
    description = models.TextField("descripción", blank=True)

    class Meta(Orderable.Meta):
        verbose_name = "cifra de impacto"
        verbose_name_plural = "cifras de impacto"

    def __str__(self):
        return f"{self.value} {self.label}"


class TeamMember(Orderable):
    name = models.CharField("nombre", max_length=120)
    role = models.CharField("cargo", max_length=120)
    bio = models.TextField("breve presentación", blank=True, help_text="Una o dos frases.")
    photo = models.ImageField("foto", upload_to="team/", blank=True,
                              help_text="Vertical (4:5) de preferencia. Sin foto se muestran las iniciales.")
    linkedin = models.URLField("LinkedIn", blank=True)

    class Meta(Orderable.Meta):
        verbose_name = "integrante del equipo"
        verbose_name_plural = "equipo"

    def __str__(self):
        return self.name


class ContactMessage(models.Model):
    name = models.CharField("nombre", max_length=120)
    email = models.EmailField("correo")
    subject = models.CharField("asunto", max_length=160)
    message = models.TextField("mensaje")
    language = models.CharField("idioma", max_length=5, default="es")
    created_at = models.DateTimeField("recibido", auto_now_add=True)
    handled = models.BooleanField("respondido", default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "mensaje de contacto"
        verbose_name_plural = "mensajes de contacto"

    def __str__(self):
        return f"{self.name}: {self.subject}"
