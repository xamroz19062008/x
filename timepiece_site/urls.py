from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from catalog import views  # один импорт, без дублей

urlpatterns = [
    path("admin/", admin.site.urls),

    # Django auth (login/logout/password reset...)
    path("accounts/", include("django.contrib.auth.urls")),

    # Ваша регистрация и аккаунт (оставляем ваши основные view)
    path("signup/", views.signup, name="signup"),
    path("account/", views.account, name="account"),

    # API + остальные пути из catalog/urls.py
    # (после исправления catalog/urls.py у вас здесь будут /api/watches/all/ и т.д.)
    path("api/", include("catalog.urls")),

    # Если webhook нужен именно по этому адресу — оставляем
    # (НО: если он уже есть внутри catalog/urls.py, то это дублирование)
    path("telegram/webhook/", views.telegram_webhook, name="telegram_webhook"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
