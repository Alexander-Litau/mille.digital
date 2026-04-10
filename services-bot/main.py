#!/usr/bin/env python3
"""
Бот MIL.LE Digital — услуги агентства.
Отправляет приветствие + обрабатывает заявки из мини-приложения через Firebase.
"""

import json
import os
import requests
import time
import threading
from config import API_BASE, BOT_TOKEN, BOT_USERNAME, MINI_APP_URL

FIREBASE_DB_URL = "https://mille-digital-comments-default-rtdb.asia-southeast1.firebasedatabase.app"
ADMIN_CHAT_ID = 159825772

# Хранилище постов с кнопками (message_id -> text_preview)
_data_dir = "/data" if os.path.isdir("/data") else os.path.dirname(__file__)
POSTS_FILE = os.path.join(_data_dir, "button_posts.json")


def load_posts():
    try:
        with open(POSTS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_posts(posts):
    with open(POSTS_FILE, "w") as f:
        json.dump(posts, f, ensure_ascii=False)


def _headers():
    return {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}


def send_message(chat_id, text, buttons=None):
    body = {"text": text}
    if buttons:
        body["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
    r = requests.post(f"{API_BASE}/messages", headers=_headers(), params={"chat_id": chat_id}, json=body)
    if not r.ok:
        print(f"[send] ERROR {r.status_code}: {r.text}")
    return r


def send_contact(chat_id, user_id, user_name):
    body = {"attachments": [{"type": "contact", "payload": {"name": user_name, "contact_id": int(user_id)}}]}
    r = requests.post(f"{API_BASE}/messages", headers=_headers(), params={"chat_id": chat_id}, json=body)
    if not r.ok:
        print(f"[contact] ERROR {r.status_code}: {r.text}")


def send_welcome(chat_id):
    text = (
        "Привет! Мы — MIL.LE Digital, агентство комплексного digital-присутствия.\n\n"
        "Что мы делаем:\n"
        "- Ведём каналы в MAX и Telegram\n"
        "- Создаём чат-ботов и мини-приложения\n"
        "- Запускаем рекламу в Яндекс Директ и Telegram Ads\n"
        "- Разрабатываем лендинги, которые продают\n\n"
        "Посмотрите все наши услуги и кейсы в приложении 👇"
    )
    send_message(chat_id, text)


def process_orders():
    """Проверить Firebase на новые заявки и отправить админу."""
    try:
        r = requests.get(f"{FIREBASE_DB_URL}/orders.json", timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return

        for order_id, order in data.items():
            try:
                user_name = order.get("user_name", "Аноним")
                user_tag = order.get("user_tag", "")
                user_id = order.get("user_id")
                platform = order.get("platform", "—")
                service = order.get("service", "Общая заявка")
                message = order.get("message", "")

                lines = [
                    "📬 Новая заявка из Mini App",
                    "",
                    f"👤 Клиент: {user_name}" + (f" ({user_tag})" if user_tag else ""),
                    f"📱 Платформа: {platform}",
                    f"⚡ Услуга: {service}",
                ]
                if message:
                    lines.extend(["", f"💬 Сообщение: {message}"])

                send_message(ADMIN_CHAT_ID, "\n".join(lines))

                # Отправляем контакт, чтобы можно было сразу написать
                if user_id:
                    send_contact(ADMIN_CHAT_ID, user_id, user_name)

                # Удаляем обработанную заявку
                requests.delete(f"{FIREBASE_DB_URL}/orders/{order_id}.json", timeout=10)
                print(f"[order] заявка {order_id} от {user_name} отправлена")

            except Exception as e:
                print(f"[order] ошибка обработки {order_id}: {e}")
                requests.delete(f"{FIREBASE_DB_URL}/orders/{order_id}.json", timeout=10)

    except Exception as e:
        print(f"[order] ошибка чтения заявок: {e}")


def orders_loop():
    """Фоновый цикл проверки заявок каждые 3 секунды."""
    while True:
        process_orders()
        time.sleep(3)


def get_updates(marker=None, timeout=30):
    params = {"timeout": timeout, "types": "message_created,message_callback,bot_started"}
    if marker:
        params["marker"] = marker
    try:
        r = requests.get(f"{API_BASE}/updates", headers=_headers(), params=params, timeout=timeout + 5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[updates] ошибка: {e}")
        time.sleep(3)
        return {}


def handle_forward(chat_id, link):
    """Пересланный пост — добавить кнопку."""
    fwd_message = link.get("message", {})
    fwd_mid = fwd_message.get("mid")
    if not fwd_mid:
        send_message(chat_id, "Не удалось определить ID поста.")
        return

    # Получаем текст поста для превью
    fwd_body = fwd_message.get("body", {})
    fwd_text = fwd_body.get("text", "") if isinstance(fwd_body, dict) else ""
    if not fwd_text:
        msg_info = requests.get(f"{API_BASE}/messages/{fwd_mid}", headers=_headers(), timeout=10)
        if msg_info.ok:
            fwd_text = msg_info.json().get("body", {}).get("text", "")

    try:
        buttons = [[{"type": "link", "text": "MIL.LE Digital", "url": f"https://max.ru/{BOT_USERNAME}"}]]
        attachments = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
        r = requests.put(f"{API_BASE}/messages", headers=_headers(), params={"message_id": fwd_mid}, json={"attachments": attachments})
        if r.ok:
            # Сохраняем пост
            posts = load_posts()
            preview = (fwd_text or "")[:40]
            if len(fwd_text or "") > 40:
                preview += "..."
            posts[fwd_mid] = preview or f"Пост {fwd_mid}"
            save_posts(posts)

            send_message(chat_id, "✅ Кнопка добавлена к посту!\n\n/off — убрать кнопку (для редактирования)\n/on — вернуть кнопку")
            print(f"[button] добавлена к {fwd_mid}")
        else:
            send_message(chat_id, f"Ошибка: {r.status_code}. Убедитесь, что бот — администратор канала.")
            print(f"[button] ERROR {r.status_code}: {r.text}")
    except Exception as e:
        send_message(chat_id, f"Ошибка: {e}")
        print(f"[button] ошибка: {e}")


def handle_off(chat_id):
    """Показать список постов для отключения кнопки."""
    posts = load_posts()
    if not posts:
        send_message(chat_id, "Нет постов с кнопками.")
        return

    buttons = []
    for mid, preview in posts.items():
        buttons.append([{"type": "callback", "text": preview, "payload": f"detach_{mid}"}])

    send_message(chat_id, "Выберите пост, с которого убрать кнопку:", buttons)


def handle_on(chat_id):
    """Показать список постов для подключения кнопки обратно."""
    posts = load_posts()
    if not posts:
        send_message(chat_id, "Нет сохранённых постов.")
        return

    buttons = []
    for mid, preview in posts.items():
        buttons.append([{"type": "callback", "text": preview, "payload": f"reattach_{mid}"}])

    send_message(chat_id, "Выберите пост, к которому вернуть кнопку:", buttons)


def handle_callback(update):
    """Обработать нажатие inline-кнопки."""
    callback = update.get("callback", {})
    payload = callback.get("payload", "")
    callback_id = callback.get("callback_id", "")
    chat_id = update.get("message", {}).get("recipient", {}).get("chat_id")

    # Ответить на callback чтобы убрать "часики"
    try:
        requests.post(f"{API_BASE}/answers", headers=_headers(), params={"callback_id": callback_id}, json={})
    except Exception:
        pass

    if not chat_id:
        return

    if payload.startswith("detach_"):
        mid = payload[7:]
        try:
            r = requests.put(f"{API_BASE}/messages", headers=_headers(), params={"message_id": mid}, json={"attachments": []})
            if r.ok:
                send_message(chat_id, "✅ Кнопка убрана. Можете редактировать пост.\n\nЧтобы вернуть кнопку — /on")
                print(f"[detach] кнопка убрана с {mid}")
            else:
                send_message(chat_id, f"Ошибка: {r.status_code}")
        except Exception as e:
            send_message(chat_id, f"Ошибка: {e}")

    elif payload.startswith("reattach_"):
        mid = payload[9:]
        try:
            buttons = [[{"type": "link", "text": "MIL.LE Digital", "url": f"https://max.ru/{BOT_USERNAME}"}]]
            attachments = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
            r = requests.put(f"{API_BASE}/messages", headers=_headers(), params={"message_id": mid}, json={"attachments": attachments})
            if r.ok:
                send_message(chat_id, "✅ Кнопка возвращена!")
                print(f"[reattach] кнопка возвращена к {mid}")
            else:
                send_message(chat_id, f"Ошибка: {r.status_code}")
        except Exception as e:
            send_message(chat_id, f"Ошибка: {e}")


def main():
    if not BOT_TOKEN:
        print("Ошибка: задайте MAX_BOT_TOKEN в .env")
        return

    print("Бот услуг запущен...")

    # Запускаем фоновую проверку заявок
    t = threading.Thread(target=orders_loop, daemon=True)
    t.start()
    print("[orders] проверка заявок запущена")

    marker = None

    try:
        while True:
            data = get_updates(marker=marker)
            updates = data.get("updates", [])
            marker = data.get("marker", marker)

            for update in updates:
                update_type = update.get("update_type", "")

                if update_type == "bot_started":
                    chat_id = update.get("chat_id")
                    user = update.get("user", {})
                    print(f"[bot_started] user={user.get('first_name')} chat_id={chat_id}")
                    if chat_id:
                        send_welcome(chat_id)

                elif update_type == "message_callback":
                    handle_callback(update)

                elif update_type == "message_created":
                    msg = update.get("message", {})
                    body = msg.get("body", {})
                    text = body.get("text", "").strip()
                    chat_id = msg.get("recipient", {}).get("chat_id")
                    link = msg.get("link") or body.get("link")

                    # Пересланный пост — добавить кнопку
                    if link and link.get("type") == "forward":
                        if chat_id:
                            handle_forward(chat_id, link)
                        continue

                    if chat_id and text == "/off":
                        handle_off(chat_id)
                    elif chat_id and text == "/on":
                        handle_on(chat_id)
                    elif chat_id and text in ("/start", "/help"):
                        send_welcome(chat_id)
                    elif chat_id and text == "/about":
                        send_message(chat_id, "MIL.LE Digital — агентство комплексного digital-присутствия.\n\nОткройте мини-приложение, чтобы узнать подробнее о наших услугах.")

    except KeyboardInterrupt:
        print("\nОстановка бота...")


if __name__ == "__main__":
    main()
