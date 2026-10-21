from django.urls import path

from .views import ContactView, HealthView, SiteContentView

urlpatterns = [
    path("site/", SiteContentView.as_view(), name="site-content"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("health/", HealthView.as_view(), name="health"),
]
