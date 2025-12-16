from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from catalog import views

urlpatterns = [
    path("admin/", admin.site.urls),

    # ТВОЯ регистрация (кастомная)
    path("signup/", views.signup, name="signup"),

    # Django auth (login/logout/password...)
    # ВАЖНО: подключаем ОДИН раз и под /accounts/
    path("accounts/", include("django.contrib.auth.urls")),

    # Твои страницы
    path("account/", views.account, name="account"),

    # Твои API
    path("api/orders/create/", views.api_create_order, name="api_create_order"),
    path("telegram/webhook/", views.telegram_webhook, name="telegram_webhook"),

    # Каталог
    path("", include("catalog.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
