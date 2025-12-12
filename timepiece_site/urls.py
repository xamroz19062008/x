import os

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from catalog import views as catalog_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # logout должен быть до auth urls
    path("accounts/logout/", catalog_views.logout_view, name="logout"),

    # signup + стандартные auth urls
    path("accounts/signup/", catalog_views.signup, name="signup"),
    path("accounts/", include("django.contrib.auth.urls")),

    # telegram webhook (оставляем один!)
    path("telegram/webhook/", catalog_views.telegram_webhook, name="telegram_webhook"),

    # main app
    path("", include("catalog.urls")),
]

# ✅ MEDIA: локально в DEBUG, и на Render тоже (когда есть Persistent Disk)
if settings.DEBUG or os.getenv("RENDER") == "true":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
