from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from catalog import views

urlpatterns = [
    path("admin/", admin.site.urls),

    # 🔑 АВТОРИЗАЦИЯ (короткие и понятные URL)
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("signup/", views.signup, name="signup"),
    path("account/", views.account, name="account"),

    # стандартные auth-урлы (пароли и т.д.)
    path("accounts/", include("django.contrib.auth.urls")),

    # API
    path("api/orders/create/", views.api_create_order, name="api_create_order"),
    path("telegram/webhook/", views.telegram_webhook, name="telegram_webhook"),

    # основной сайт
    path("", include("catalog.urls")),
]

# медиа
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
