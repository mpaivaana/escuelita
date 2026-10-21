"""Carrega o conteúdo inicial (3 idiomas). Uso: python manage.py seed_content [--images DIR]"""
import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from content.models import ImpactStat, Pillar, Project, Service, SiteSettings, TeamMember

SEED = Path(__file__).resolve().parents[2] / "seed_content.json"


def split(data):
    """{'title': {'es':..,'en':..}} -> {'title_es':.., 'title_en':..}; escalares ficam iguais."""
    out = {}
    for key, val in data.items():
        if isinstance(val, dict):
            for lang, text in val.items():
                out[f"{key}_{lang}"] = text
        else:
            out[key] = val
    return out


class Command(BaseCommand):
    help = "Carga el contenido inicial del sitio si la base está vacía."

    def add_arguments(self, parser):
        parser.add_argument("--images", help="Carpeta con las imágenes de los proyectos")
        parser.add_argument("--force", action="store_true", help="Borra y vuelve a cargar todo")

    def handle(self, *args, **opts):
        data = json.loads(SEED.read_text(encoding="utf-8"))
        if SiteSettings.objects.exists() and not opts["force"]:
            # Bases ya pobladas antes de existir la sección de equipo
            if not TeamMember.objects.exists():
                self.seed_team(data)
                self.stdout.write(self.style.SUCCESS("Sección de equipo cargada."))
            else:
                self.stdout.write("Ya hay contenido; nada que hacer (usa --force para recargar).")
            return
        for model in (SiteSettings, Pillar, Project, Service, ImpactStat, TeamMember):
            model.objects.all().delete()

        SiteSettings.objects.create(**split(data["site"]))
        for i, item in enumerate(data["pillars"]):
            Pillar.objects.create(order=i, **split(item))
        img_dir = Path(opts["images"]) if opts.get("images") else None
        for i, item in enumerate(data["projects"]):
            image = item.pop("image", None)
            project = Project(order=i, **split(item))
            if img_dir and image and (img_dir / image).exists():
                with open(img_dir / image, "rb") as fh:
                    project.image.save(image, File(fh), save=False)
            project.save()
        for i, item in enumerate(data["services"]):
            Service.objects.create(order=i, **split(item))
        for i, item in enumerate(data["stats"]):
            ImpactStat.objects.create(order=i, **split(item))
        self.seed_team(data)
        self.stdout.write(self.style.SUCCESS("Contenido inicial cargado en es / en / pt."))

    def seed_team(self, data):
        s = SiteSettings.load()
        if s and not s.team_intro_es:
            for key in ("team_title", "team_intro"):
                for lang, text in data["site"][key].items():
                    setattr(s, f"{key}_{lang}", text)
            s.save()
        for i, item in enumerate(data.get("team", [])):
            TeamMember.objects.create(order=i, **split(item))
