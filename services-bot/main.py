#!/usr/bin/env python3
"""
Бот MIL.LE Digital — услуги агентства.
Отправляет приветствие + обрабатывает заявки из мини-приложения через WebApp.sendData().
"""

import json
import requests
from config import API_BASE, BOT_TOKEN, BOT_USERNAME, MINI_APP_URL

ADMIN_CHAT_ID = 159825772


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


def handle_order(order, chat_id, user):
    """Обработать заявку, пришедшую через WebApp.sendData()."""
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

    # Подтверждение клиенту
    if chat_id:
        send_message(chat_id, "✅ Спасибо за заявку! Мы скоро свяжемся с вами.")

    print(f"[order] заявка от {user_name}: {service}")


def get_updates(marker=None, timeout=30):
    params = {"timeout": timeout, "types": "message_created,bot_started"}
    if marker:
        params["marker"] = marker
    try:
        r = requests.get(f"{API_BASE}/updates", headers=_headers(), params=params, timeout=timeout + 5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[updates] ошибка: {e}")
        import time
        time.sleep(3)
        return {}


def main():
    if not BOT_TOKEN:
        print("Ошибка: задайте MAX_BOT_TOKEN в .env")
        return

    print("Бот услуг запущен...")

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

                elif update_type == "message_created":
                    msg = update.get("message", {})
                    body = msg.get("body", {})
                    text = body.get("text", "").strip()
                    chat_id = msg.get("recipient", {}).get("chat_id")
                    user = msg.get("sender", {})

                    # Пробуем распарсить как заявку из мини-приложения
                    try:
                        order = json.loads(text)
                        if isinstance(order, dict) and order.get("type") == "order":
                            handle_order(order, chat_id, user)
                            continue
                    except (json.JSONDecodeError, TypeError):
                        pass

                    # Обычные команды
                    if chat_id and text in ("/start", "/help"):
                        send_welcome(chat_id)
                    elif chat_id and text == "/about":
                        send_message(chat_id, "MIL.LE Digital — агентство комплексного digital-присутствия.\n\nОткройте мини-приложение, чтобы узнать подробнее о наших услугах.")

    except KeyboardInterrupt:
        print("\nОстановка бота...")


if __name__ == "__main__":
    main()
