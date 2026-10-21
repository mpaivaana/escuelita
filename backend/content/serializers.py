from rest_framework import serializers

from .models import ContactMessage, ImpactStat, Pillar, Project, Service, TeamMember


class ImageUrlMixin:
    def image_url(self, file):
        if not file:
            return None
        url = file.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request and url.startswith("/") else url


class PillarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pillar
        fields = ("title", "text", "icon")


class ProjectSerializer(ImageUrlMixin, serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ("slug", "title", "partner", "summary", "image", "year", "featured")

    def get_image(self, obj):
        return self.image_url(obj.image)


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("title", "description")


class ImpactStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImpactStat
        fields = ("value", "label", "description")


class TeamMemberSerializer(ImageUrlMixin, serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()

    class Meta:
        model = TeamMember
        fields = ("name", "role", "bio", "photo", "linkedin", "initials")

    def get_photo(self, obj):
        return self.image_url(obj.photo)

    def get_initials(self, obj):
        parts = [w for w in obj.name.split() if w[:1].isalpha()]
        return "".join(w[0] for w in (parts[:1] + parts[-1:] if len(parts) > 1 else parts)).upper()


class ContactMessageSerializer(serializers.ModelSerializer):
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)  # honeypot

    class Meta:
        model = ContactMessage
        fields = ("name", "email", "subject", "message", "language", "website")

    def validate_language(self, value):
        return value if value in {"es", "en", "pt"} else "es"

    def create(self, validated_data):
        validated_data.pop("website", None)
        return super().create(validated_data)
