from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from catalog import views as catalog_views
from catalog import views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Django auth (login/logout/password reset...)
    path("accounts/", include("django.contrib.auth.urls")),

    # Ваша регистрация и аккаунт (оставляем ваши основные view)
    path("signup/", catalog_views.signup, name="signup"),
    path("account/", catalog_views.account, name="account"),
    path("accounts/", include("django.contrib.auth.urls")),

    path("api/orders/create/", catalog_views.api_create_order, name="api_create_order"),
    path("telegram/webhook/", catalog_views.telegram_webhook, name="telegram_webhook"),
    path("", include("catalog.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
