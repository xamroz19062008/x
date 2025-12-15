import json
import requests
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .cart import Cart
from .models import Watch, Order, OrderItem


# =========================
# Регистрация
# =========================

class SignUpForm(UserCreationForm):
    username = forms.CharField(label="Логин", max_length=150)
    phone = forms.CharField(label="Телефон", max_length=32, required=False)

    class Meta:
        model = User
        fields = ("username", "password1", "password2", "phone")


def signup(request):
    """
    После успешной регистрации НЕ логиним автоматически,
    а отправляем на страницу логина.
    """
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()

            phone = form.cleaned_data.get("phone", "")
            if hasattr(user, "profile"):
                user.profile.phone = phone
                user.profile.save()

            return redirect("login")
    else:
        form = SignUpForm()

    return render(request, "registration/signup.html", {"form": form})


# =========================
# Страницы
# =========================

def index(request):
    return render(request, "index.html")


def catalog_page(request):
    return render(request, "catalog.html")


# =========================
# API часов
# =========================

def _serialize_watch(w: Watch) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "tag": w.tag,
        "description": w.description,
        "price": w.price,
        "currency": w.currency,
        "badge": w.badge,
        "image_url": w.image.url if w.image else "",
    }


def hero_watch(request):
    watch = (
        Watch.objects.filter(is_active=True, is_hero=True)
        .order_by("sort_order", "id")
        .first()
    )
    if not watch:
        return JsonResponse({"item": None})
    return JsonResponse({"item": _serialize_watch(watch)})


def watches_featured(request):
    watches = (
        Watch.objects.filter(is_active=True, is_featured=True)
        .order_by("sort_order", "id")[:3]
    )
    return JsonResponse({"items": [_serialize_watch(w) for w in watches]})


def watches_all(request):
    watches = Watch.objects.filter(is_active=True).order_by("sort_order", "id")
    return JsonResponse({"items": [_serialize_watch(w) for w in watches]})


# =========================
# Корзина
# =========================

@require_POST
def cart_add(request, watch_id):
    cart = Cart(request)
    quantity = int(request.POST.get("quantity", 1))
    update = request.POST.get("update") == "1"
    cart.add(watch_id=watch_id, quantity=quantity, update_quantity=update)
    return redirect("cart_detail")


def cart_remove(request, watch_id):
    cart = Cart(request)
    cart.remove(watch_id)
    return redirect("cart_detail")


def cart_detail(request):
    cart = Cart(request)
    form_initial = {}

    if request.user.is_authenticated and hasattr(request.user, "profile"):
        form_initial = {
            "location": request.user.profile.location,
            "phone": request.user.profile.phone,
        }

    return render(request, "cart.html", {"cart": cart, "errors": {}, "form": form_initial})


# =========================
# Telegram: отправка заказа (1 сообщение + фото ответом)
# =========================

def send_order_to_telegram(order: Order, request):
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)
    if not token or not chat_id:
        return

    lat = getattr(order, "latitude", None)
    lon = getattr(order, "longitude", None)
    has_coords = lat is not None and lon is not None

    items = list(order.items.select_related("watch").all())

    lines = [
        f"🧾 Новый заказ #{order.id}",
        f"Статус: {order.get_status_display()}",
        f"Создан: {order.created_at}",
        f"Телефон: {order.phone}",
        f"Адрес (текст): {order.location}",
    ]
    if has_coords:
        lines.append(f"Координаты: {lat}, {lon}")
        lines.append(f"Карта: https://www.google.com/maps?q={lat},{lon}")

    lines.append(f"Сумма: {order.total_amount} сум")
    lines.append("")
    lines.append("Товары:")
    for item in items:
        lines.append(f"• {item.watch.name} — {item.quantity} шт. × {item.price} сум")

    text = "\n".join(lines)

    # Кнопки (ВАЖНО: deliver/cancel соответствуют webhook ниже)
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Подтвердить", "callback_data": f"deliver:{order.id}"},
            {"text": "❌ Отказать",    "callback_data": f"cancel:{order.id}"},
        ]]
    }

    # 1) Главное сообщение (текст+кнопки) — берем message_id
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "reply_markup": keyboard},
        timeout=10,
    )
    data = r.json()
    msg_id = None
    if isinstance(data, dict) and data.get("ok") and data.get("result"):
        msg_id = data["result"].get("message_id")

    # 2) Фото товаров — reply на главное сообщение (чтобы выглядело как один блок)
    media = []
    files = {}
    idx = 0

    for it in items:
        if it.watch.image:
            idx += 1
            name = f"photo{idx}"
            try:
                files[name] = open(it.watch.image.path, "rb")
            except Exception:
                continue

            media.append({
                "type": "photo",
                "media": f"attach://{name}",
                "caption": f"{it.watch.name}\n{it.quantity} шт. × {it.price} сум",
            })

    for start in range(0, len(media), 10):
        batch = media[start:start + 10]

        batch_files = {}
        for m in batch:
            n = m["media"].replace("attach://", "")
            if n in files:
                batch_files[n] = files[n]

        payload = {"chat_id": chat_id, "media": json.dumps(batch)}
        if msg_id:
            payload["reply_to_message_id"] = msg_id

        requests.post(
            f"https://api.telegram.org/bot{token}/sendMediaGroup",
            data=payload,
            files=batch_files,
            timeout=25,
        )

    for f in files.values():
        try:
            f.close()
        except Exception:
            pass


# =========================
# Оформление заказа
# =========================

def checkout(request):
    cart = Cart(request)

    if request.method == "POST":
        if len(cart) == 0:
            return redirect("cart_detail")

        location = (request.POST.get("location") or "").strip()
        phone = (request.POST.get("phone") or "").strip()

        lat_raw = (request.POST.get("latitude") or "").strip()
        lon_raw = (request.POST.get("longitude") or "").strip()

        try:
            lat = float(lat_raw) if lat_raw else None
            lon = float(lon_raw) if lon_raw else None
        except ValueError:
            lat = None
            lon = None

        errors = {}
        if not cart:
            errors["cart"] = "Корзина пуста. Добавьте хотя бы одну модель."
        if not location:
            errors["location"] = "Укажите адрес доставки."
        if not phone:
            errors["phone"] = "Укажите номер телефона."
        if lat is None or lon is None:
            errors["map"] = "Выберите точку на карте."

        if errors:
            return render(
                request,
                "cart.html",
                {
                    "cart": cart,
                    "errors": errors,
                    "form": {
                        "location": location,
                        "phone": phone,
                        "latitude": lat_raw,
                        "longitude": lon_raw,
                    },
                },
                status=200,
            )

        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            location=location,
            phone=phone,
            latitude=lat,
            longitude=lon,
            status="waiting",
        )

        if request.user.is_authenticated and hasattr(request.user, "profile"):
            profile = request.user.profile
            profile.location = location
            profile.phone = phone
            profile.save()

        for item in cart:
            OrderItem.objects.create(
                order=order,
                watch=item["watch"],
                quantity=item["quantity"],
                price=item["price"],
            )

        # отправляем в Telegram ДО очистки корзины
        send_order_to_telegram(order, request)

        cart.clear()
        return redirect("account")

    return redirect("cart_detail")


# =========================
# Telegram Webhook: кнопки + архив
# =========================
@csrf_exempt
def api_create_order(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    location = (data.get("location") or "").strip()
    phone = (data.get("phone") or "").strip()
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    items = data.get("items") or []

    if not location or not phone or latitude is None or longitude is None or not items:
        return JsonResponse({"error": "Missing fields"}, status=400)

    # создаём заказ (если пользователь залогинен на backend — привяжется, иначе None)
    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        location=location,
        phone=phone,
        latitude=float(latitude),
        longitude=float(longitude),
        status="waiting",
    )

    # items ожидаем вида: [{id, price, quantity, ...}, ...]
    for it in items:
        watch_id = it.get("id")
        price = it.get("price", 0)
        quantity = it.get("quantity", 1)

        if not watch_id:
            continue

        OrderItem.objects.create(
            order=order,
            watch_id=watch_id,   # важно: watch_id, потому что у тебя ForeignKey watch
            quantity=int(quantity),
            price=int(price),
        )

    # отправка в Telegram (как у тебя уже сделано)
    send_order_to_telegram(order, request)

    return JsonResponse({"success": True, "order_id": order.id})

def _is_admin_telegram_update(update: dict) -> bool:
    admin_ids = getattr(settings, "TELEGRAM_ADMIN_IDS", [])
    if not admin_ids:
        return True  # если список не задан — не ограничиваем

    user_id = None
    if "message" in update:
        user_id = update["message"].get("from", {}).get("id")
    elif "callback_query" in update:
        user_id = update["callback_query"].get("from", {}).get("id")

    return user_id in admin_ids


def _set_order_status_safe(order: Order, status_value: str) -> bool:
    """
    Ставит статус, только если он есть в choices.
    Возвращает True если установили, иначе False.
    """
    try:
        choices = getattr(Order, "STATUS_CHOICES", None) or getattr(order, "STATUS_CHOICES", None)
        if choices:
            allowed = {k for (k, _) in choices}
            if status_value not in allowed:
                return False
        order.status = status_value
        order.save(update_fields=["status"])
        return True
    except Exception:
        return False


@csrf_exempt
def telegram_webhook(request):
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    if not token:
        return JsonResponse({"ok": True})

    try:
        update = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": True})

    if not _is_admin_telegram_update(update):
        return JsonResponse({"ok": True})

    # =====================================================
    # 1) CALLBACK QUERY (кнопки)
    # =====================================================
    if "callback_query" in update:
        cq = update["callback_query"]
        data = cq.get("data", "")
        cq_id = cq.get("id")
        message = cq.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")

        if ":" in data:
            action, value = data.split(":", 1)

            # -------------------------------------------------
            # ✅ ПОДТВЕРДИТЬ / ОТКАЗАТЬ
            # -------------------------------------------------
            if action in ("deliver", "cancel"):
                try:
                    order = Order.objects.get(id=int(value))
                except Exception:
                    requests.post(
                        f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                        json={"callback_query_id": cq_id, "text": "Заказ не найден"},
                    )
                    return JsonResponse({"ok": True})

                if action == "deliver":
                    ok = _set_order_status_safe(order, "delivered")
                    text = "✅ Заказ подтверждён (Доставлен)" if ok else "❗ Статус delivered не найден"
                else:
                    ok = _set_order_status_safe(order, "cancelled")
                    if not ok:
                        ok = _set_order_status_safe(order, "canceled")
                    text = "❌ Заказ отменён" if ok else "❗ Статус отмены не найден"

                requests.post(
                    f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                    json={"callback_query_id": cq_id, "text": text},
                )

                # убираем кнопки
                requests.post(
                    f"https://api.telegram.org/bot{token}/editMessageReplyMarkup",
                    json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "reply_markup": {"inline_keyboard": []},
                    },
                )

                return JsonResponse({"ok": True})

            # -------------------------------------------------
            # ✅ АРХИВ ЗАКАЗОВ (С ТОВАРАМИ)
            # -------------------------------------------------
            if action == "orders":
                now = timezone.now()

                if value == "hour":
                    qs = Order.objects.filter(created_at__gte=now - timedelta(hours=1))
                    title = "🕐 Заказы за последний час"
                elif value == "day":
                    qs = Order.objects.filter(created_at__gte=now - timedelta(days=1))
                    title = "📅 Заказы за последний день"
                else:
                    qs = Order.objects.filter(created_at__gte=now - timedelta(days=7))
                    title = "🗓 Заказы за последнюю неделю"

                qs = (
                    qs.order_by("-created_at")
                      .prefetch_related("items__watch")[:50]
                )

                if not qs:
                    msg = f"{title}\n\nНет заказов."
                else:
                    lines = [title, ""]
                    for o in qs:
                        goods = []
                        for it in o.items.all():
                            goods.append(f"{it.watch.name} ({it.quantity})")

                        goods_text = ", ".join(goods) if goods else "—"

                        lines.append(
                            f"#{o.id} | {o.created_at:%d.%m %H:%M} | "
                            f"{o.get_status_display()} | {o.total_amount} сум | "
                            f"{o.phone} | Товары: {goods_text}"
                        )

                    msg = "\n".join(lines)

                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": msg},
                )

                requests.post(
                    f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                    json={"callback_query_id": cq_id, "text": "Готово"},
                )

                return JsonResponse({"ok": True})

        # неизвестная кнопка
        requests.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={"callback_query_id": cq_id, "text": "Неизвестное действие"},
        )
        return JsonResponse({"ok": True})

    # =====================================================
    # 2) КОМАНДА /orders
    # =====================================================
    if "message" in update and update["message"].get("text"):
        chat_id = update["message"]["chat"]["id"]
        text = update["message"]["text"].strip()

        if text == "/orders":
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🕐 Последний час", "callback_data": "orders:hour"}],
                    [{"text": "📅 Последний день", "callback_data": "orders:day"}],
                    [{"text": "🗓 Последняя неделя", "callback_data": "orders:week"}],
                ]
            }

            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "📦 Архив заказов — выберите период:",
                    "reply_markup": keyboard,
                },
            )
            return JsonResponse({"ok": True})

    return JsonResponse({"ok": True})

# =========================
# Callback оплаты (пока заглушка)
# =========================

@csrf_exempt
def payment_callback(request):
    return JsonResponse({"result": "ok"})


# =========================
# Аккаунт / выход
# =========================

@login_required
def account(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "account.html", {
        "orders": orders,
    })



def logout_view(request):
    logout(request)
    return redirect("index")

def index(request):
    return redirect("https://YOUR_VERCEL_DOMAIN.vercel.app/index.html")

