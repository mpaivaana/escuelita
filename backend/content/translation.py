from modeltranslation.translator import TranslationOptions, register

from .models import BlogPost, ImpactStat, Pillar, Project, Service, SiteSettings, TeamMember


@register(SiteSettings)
class SiteSettingsTR(TranslationOptions):
    fields = ("about_title", "about_text", "projects_title", "projects_intro", "services_title",
              "services_intro", "impact_label", "team_title", "team_intro", "contact_title", "contact_intro")


@register(Pillar)
class PillarTR(TranslationOptions):
    fields = ("title", "text")


@register(Project)
class ProjectTR(TranslationOptions):
    fields = ("title", "partner", "summary")


@register(Service)
class ServiceTR(TranslationOptions):
    fields = ("title", "description")


@register(ImpactStat)
class ImpactStatTR(TranslationOptions):
    fields = ("label", "description")


@register(TeamMember)
class TeamMemberTR(TranslationOptions):
    fields = ("role", "bio")


@register(BlogPost)
class BlogPostTR(TranslationOptions):
    fields = ("title", "excerpt", "body")
