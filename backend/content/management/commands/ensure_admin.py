"""Cria o primeiro administrador a partir de variáveis de ambiente, se ainda não existir.

Uso (roda a cada deploy na Railway): python manage.py ensure_admin
Variáveis: DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_PASSWORD e, opcional, DJANGO_SUPERUSER_EMAIL.
Nunca altera a senha de um usuário que já existe.
"""
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea el primer administrador con DJANGO_SUPERUSER_USERNAME y DJANGO_SUPERUSER_PASSWORD."

    def handle(self, *args, **opts):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
        if not username or not password:
            self.stdout.write("Sin DJANGO_SUPERUSER_USERNAME/PASSWORD; no se crea ningún administrador.")
            return
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"El usuario «{username}» ya existe; nada que hacer.")
            return
        User.objects.create_superuser(username, os.getenv("DJANGO_SUPERUSER_EMAIL", ""), password)
        self.stdout.write(self.style.SUCCESS(f"Administrador «{username}» creado."))
