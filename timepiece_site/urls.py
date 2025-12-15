from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from catalog import views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("accounts/signup/", views.signup, name="signup"),
    path("accounts/logout/", views.logout_view, name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),

    path("telegram/webhook/", views.telegram_webhook, name="telegram_webhook"),

    path("", include("catalog.urls")),
    path("api/orders/create/", views.api_create_order, name="api_create_order"),
    path("account/", views.account, name="account"),
    path("", include("django.contrib.auth.urls")),
]

# ⚠️ MEDIA ДОЛЖНЫ ОТДАВАТЬСЯ ВСЕГДА
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
