"""Cria o grupo «Editores»: edita todo o conteúdo e o blog, sem acesso a usuários."""
from django.contrib.auth.management import create_permissions
from django.db import migrations

CONTENT_MODELS = ("sitesettings", "pillar", "project", "service", "impactstat", "teammember", "blogpost")


def create_group(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    group, _ = Group.objects.get_or_create(name="Editores")
    codenames = [f"{a}_{m}" for m in CONTENT_MODELS for a in ("add", "change", "delete", "view")]
    codenames += ["view_contactmessage", "change_contactmessage"]
    group.permissions.set(Permission.objects.filter(content_type__app_label="content", codename__in=codenames))


def remove_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name="Editores").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("content", "0004_blog_editor"),
    ]

    operations = [migrations.RunPython(create_group, remove_group)]
