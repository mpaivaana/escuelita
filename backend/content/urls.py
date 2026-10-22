from django.urls import path

from .views import BlogListView, BlogPostView, ContactView, HealthView, SiteContentView

urlpatterns = [
    path("site/", SiteContentView.as_view(), name="site-content"),
    path("blog/", BlogListView.as_view(), name="blog-list"),
    path("blog/<slug:slug>/", BlogPostView.as_view(), name="blog-post"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("health/", HealthView.as_view(), name="health"),
]
