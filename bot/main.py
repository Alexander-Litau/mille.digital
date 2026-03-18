#!/usr/bin/env python3
"""
Бот для постинга в каналы/чаты Макса с автоподключением комментариев.

Сценарий:
  1. /start — приветствие
  2. Пользователь пишет текст поста
  3. Бот спрашивает "Когда?" → Сейчас / Запланировать
  4. Бот спрашивает "Куда?" → пользователь вводит chat_id или выбирает сохранённый
  5. Пост публикуется с кнопкой "Комментарии"
"""

import re
from datetime import datetime
import api
import scheduler

# ─── Состояния пользователей ───
# user_id -> {state, draft_text, draft_time, ...}
users = {}


def get_user(user_id):
    if user_id not in users:
        users[user_id] = {"state": "idle"}
    return users[user_id]


def reset_user(user_id):
    users[user_id] = {"state": "idle"}


# ─── Обработка сообщений ───

def handle_message(update):
    """Обработать входящее сообщение."""
    msg = update.get("message", {})
    body = msg.get("body", {})
    text = body.get("text", "").strip()
    sender = msg.get("sender", {})
    user_id = str(sender.get("user_id", ""))
    chat_id = msg.get("recipient", {}).get("chat_id")

    if not user_id or not chat_id or not text:
        return

    u = get_user(user_id)

    # Команда /start
    if text == "/start":
        reset_user(user_id)
        api.send_message(
            chat_id,
            "Привет! Я помогу опубликовать пост с комментариями.\n\n"
            "Просто напишите мне текст поста, и я помогу его опубликовать.\n\n"
            "Команды:\n"
            "/post — создать новый пост\n"
            "/chats — управление каналами\n"
            "/help — помощь",
        )
        return

    # Команда /help
    if text == "/help":
        api.send_message(
            chat_id,
            "Как пользоваться:\n\n"
            "1. Напишите /post\n"
            "2. Отправьте текст поста\n"
            "3. Выберите когда опубликовать\n"
            "4. Укажите куда отправить\n"
            "5. Готово! К посту автоматически прикрепятся комментарии.\n\n"
            "/chats — добавить/посмотреть каналы\n"
            "/post — создать пост",
        )
        return

    # Команда /chats — управление каналами
    if text == "/chats":
        saved = scheduler.get_saved_chats(user_id)
        if saved:
            lines = ["Ваши сохранённые каналы:\n"]
            for cid, cname in saved:
                name_str = f" ({cname})" if cname else ""
                lines.append(f"  • {cid}{name_str}")
            lines.append("\nЧтобы добавить новый, отправьте:\n/addchat ID_КАНАЛА Название")
            api.send_message(chat_id, "\n".join(lines))
        else:
            api.send_message(
                chat_id,
                "У вас нет сохранённых каналов.\n\n"
                "Добавьте канал командой:\n"
                "/addchat ID_КАНАЛА Название\n\n"
                "Чтобы узнать ID канала, добавьте бота в канал как администратора.",
            )
        return

    # Команда /addchat
    if text.startswith("/addchat"):
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            api.send_message(chat_id, "Формат: /addchat ID_КАНАЛА Название\nПример: /addchat 123456789 Мой канал")
            return
        try:
            target_chat_id = int(parts[1])
        except ValueError:
            api.send_message(chat_id, "ID канала должен быть числом.")
            return
        chat_name = parts[2] if len(parts) > 2 else None
        scheduler.save_chat(user_id, target_chat_id, chat_name)
        api.send_message(chat_id, f"Канал {target_chat_id} сохранён!")
        return

    # Команда /post — начать создание поста
    if text == "/post":
        u["state"] = "waiting_text"
        api.send_message(chat_id, "Отправьте текст поста:")
        return

    # ─── Машина состояний ───

    state = u.get("state", "idle")

    # Ожидание текста поста
    if state == "waiting_text":
        u["draft_text"] = text
        u["state"] = "waiting_when"

        buttons = [
            [
                {"type": "callback", "text": "Сейчас", "payload": "when_now"},
                {"type": "callback", "text": "Запланировать", "payload": "when_schedule"},
            ]
        ]
        api.send_message_with_keyboard(
            chat_id, "Когда опубликовать?", buttons
        )
        return

    # Ожидание даты/времени
    if state == "waiting_schedule_time":
        dt = parse_datetime(text)
        if not dt:
            api.send_message(
                chat_id,
                "Не могу разобрать дату. Отправьте в формате:\n"
                "ДД.ММ.ГГГГ ЧЧ:ММ\nНапример: 25.03.2026 14:30",
            )
            return

        if dt <= datetime.now():
            api.send_message(chat_id, "Дата должна быть в будущем. Попробуйте ещё раз:")
            return

        u["draft_time"] = dt
        u["state"] = "waiting_where"
        ask_where(user_id, chat_id)
        return

    # Ожидание куда постить
    if state == "waiting_where":
        try:
            target_chat_id = int(text)
        except ValueError:
            api.send_message(chat_id, "Отправьте числовой ID канала/чата:")
            return

        publish_or_schedule(user_id, chat_id, target_chat_id)
        return

    # Если пользователь просто написал текст без команды — предложить создать пост
    if state == "idle":
        u["draft_text"] = text
        u["state"] = "waiting_when"
        buttons = [
            [
                {"type": "callback", "text": "Сейчас", "payload": "when_now"},
                {"type": "callback", "text": "Запланировать", "payload": "when_schedule"},
            ]
        ]
        api.send_message_with_keyboard(
            chat_id, "Отлично! Когда опубликовать этот пост?", buttons
        )
        return


def handle_callback(update):
    """Обработать нажатие inline-кнопки."""
    print(f"[callback] raw update: {update}")
    callback = update.get("callback", {})
    payload = callback.get("payload", "")
    callback_id = callback.get("callback_id", "")
    user_id = str(callback.get("user", {}).get("user_id", ""))
    chat_id = callback.get("message", {}).get("recipient", {}).get("chat_id")
    print(f"[callback] payload={payload} callback_id={callback_id} user_id={user_id} chat_id={chat_id}")

    if not user_id or not chat_id:
        return

    u = get_user(user_id)
    api.answer_callback(callback_id)

    if payload == "when_now" and u.get("state") == "waiting_when":
        u["draft_time"] = None  # Сейчас
        u["state"] = "waiting_where"
        ask_where(user_id, chat_id)

    elif payload == "when_schedule" and u.get("state") == "waiting_when":
        u["state"] = "waiting_schedule_time"
        api.send_message(
            chat_id,
            "Когда опубликовать? Отправьте дату и время:\n"
            "Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 25.03.2026 14:30",
        )

    elif payload.startswith("chat_") and u.get("state") == "waiting_where":
        target_chat_id = int(payload.replace("chat_", ""))
        publish_or_schedule(user_id, chat_id, target_chat_id)


def ask_where(user_id, chat_id):
    """Спросить пользователя куда отправить пост."""
    saved = scheduler.get_saved_chats(user_id)

    if saved:
        buttons = []
        for cid, cname in saved:
            label = cname or str(cid)
            buttons.append([{"type": "callback", "text": label, "payload": f"chat_{cid}"}])

        api.send_message_with_keyboard(
            chat_id,
            "Куда опубликовать? Выберите канал или отправьте ID чата:",
            buttons,
        )
    else:
        api.send_message(
            chat_id,
            "Куда опубликовать?\n\n"
            "Отправьте ID канала или чата (число).\n"
            "Бот должен быть добавлен в этот канал/чат как администратор.\n\n"
            "Совет: сохраните каналы командой /addchat для быстрого доступа.",
        )


def publish_or_schedule(user_id, bot_chat_id, target_chat_id):
    """Опубликовать пост сейчас или запланировать."""
    u = get_user(user_id)
    draft_text = u.get("draft_text", "")
    draft_time = u.get("draft_time")

    if not draft_text:
        api.send_message(bot_chat_id, "Ошибка: текст поста не найден. Начните заново с /post")
        reset_user(user_id)
        return

    if draft_time:
        # Запланировать
        post_db_id = scheduler.add_scheduled_post(target_chat_id, draft_text, draft_time)
        time_str = draft_time.strftime("%d.%m.%Y в %H:%M")
        api.send_message(
            bot_chat_id,
            f"Пост запланирован на {time_str}!\n"
            f"К нему автоматически подключатся комментарии.",
        )
    else:
        # Опубликовать сейчас
        try:
            result, post_id, message_id = api.send_post_with_comments(target_chat_id, draft_text)
            if message_id:
                scheduler.save_published_post(post_id, message_id, target_chat_id)
            api.send_message(
                bot_chat_id,
                "Пост опубликован! Комментарии подключены автоматически.",
            )
        except Exception as e:
            api.send_message(
                bot_chat_id,
                f"Ошибка при публикации: {e}\n"
                "Убедитесь, что бот добавлен в канал/чат как администратор.",
            )

    reset_user(user_id)


def parse_datetime(text):
    """Парсинг даты из текста. Поддерживает ДД.ММ.ГГГГ ЧЧ:ММ и другие форматы."""
    formats = [
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


# ─── Главный цикл ───

def main():
    print("Бот запущен...")

    scheduler.init_db()
    scheduler.start_scheduler()

    marker = None

    try:
        while True:
            data = api.get_updates(marker=marker)
            updates = data.get("updates", [])
            marker = data.get("marker", marker)

            for update in updates:
                update_type = update.get("update_type", "")

                if update_type == "message_created":
                    handle_message(update)
                elif update_type == "message_callback":
                    handle_callback(update)
    except KeyboardInterrupt:
        print("\nОстановка бота...")
        scheduler.stop_scheduler()


if __name__ == "__main__":
    main()
