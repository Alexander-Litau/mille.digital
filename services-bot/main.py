#!/usr/bin/env python3
"""
Бот MIL.LE Digital — услуги агентства.
Отправляет приветствие с кнопкой на мини-приложение.
"""

import requests
import time
from config import API_BASE, BOT_TOKEN, BOT_USERNAME, MINI_APP_URL


def _headers():
    return {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}


def send_message(chat_id, text, buttons=None, markup=None):
    body = {}
    if markup:
        from bot_markup import markup_to_html
        body["text"] = markup_to_html(text, markup)
        body["format"] = "html"
    else:
        body["text"] = text
    if buttons:
        body["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
    r = requests.post(f"{API_BASE}/messages", headers=_headers(), params={"chat_id": chat_id}, json=body)
    if not r.ok:
        print(f"[send] ERROR {r.status_code}: {r.text}")
    return r


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

                    if chat_id and text in ("/start", "/help"):
                        send_welcome(chat_id)
                    elif chat_id and text == "/about":
                        send_message(chat_id, "MIL.LE Digital — агентство комплексного digital-присутствия.\n\nОткройте мини-приложение, чтобы узнать подробнее о наших услугах.")

    except KeyboardInterrupt:
        print("\nОстановка бота...")


if __name__ == "__main__":
    main()
