#!/usr/bin/env python3
"""
Бот для подключения комментариев к постам в каналах Макса.

Сценарий:
  1. Пользователь публикует пост в канале через интерфейс Max
  2. Пересылает пост боту
  3. Бот подключает к посту кнопку комментариев
"""

import api
import scheduler

# ─── Состояния пользователей ───
# user_id -> {state, ...}
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
    markup = body.get("markup")
    link = msg.get("link") or body.get("link")
    sender = msg.get("sender", {})
    user_id = str(sender.get("user_id", ""))
    chat_id = msg.get("recipient", {}).get("chat_id")

    if not user_id or not chat_id:
        return

    # Сохраняем маппинг user_id → chat_id
    scheduler.save_user_chat(user_id, chat_id)

    u = get_user(user_id)

    # Логируем пересланные сообщения для отладки
    if link:
        print(f"[forward] link={link}")
        print(f"[forward] full msg keys={list(msg.keys())}")
        print(f"[forward] body keys={list(body.keys())}")

    # ─── Пересланное сообщение — подключить комментарии ───
    if link and link.get("type") == "forward":
        handle_forward(user_id, chat_id, link, text)
        return

    # Если нет текста, ничего не делаем
    if not text:
        return

    # ─── Команды ───

    if text == "/start":
        reset_user(user_id)
        api.send_message(
            chat_id,
            "Привет! Я подключаю комментарии к постам в каналах.\n\n"
            "Как пользоваться:\n"
            "1. Опубликуйте пост в канале\n"
            "2. Перешлите его мне\n"
            "3. Готово — к посту подключатся комментарии!\n\n"
            "Команды:\n"
            "/off — отключить комментарии (для редактирования поста)\n"
            "/on — подключить комментарии обратно\n"
            "/chats — управление каналами\n"
            "/help — помощь",
        )
        return

    if text == "/about":
        buttons = [
            [{"type": "link", "text": "Открыть MIL.LE Digital", "url": "https://milledigital.ru/mini-app.html"}]
        ]
        api.send_message_with_keyboard(
            chat_id,
            "MIL.LE Digital — агентство комплексного Digital-присутствия\n\n"
            "Мы помогаем бизнесу и экспертам расти в Max:\n\n"
            "- Продвижение каналов в Max — подписчики, охваты, вовлечённость\n"
            "- Чат-боты и мини-приложения — автоматизация, каталоги, запись, оплата\n"
            "- Трафик на каналы — приводим целевую аудиторию\n"
            "- Комплексный маркетинг — стратегия, контент, реклама\n\n"
            "Нажмите кнопку ниже, чтобы узнать подробнее:",
            buttons,
        )
        return

    if text == "/help":
        api.send_message(
            chat_id,
            "Как подключить комментарии к посту:\n\n"
            "1. Опубликуйте пост в канале через Max\n"
            "2. Перешлите этот пост мне в личные сообщения\n"
            "3. Я подключу к нему кнопку комментариев\n\n"
            "Важно: бот должен быть администратором канала.\n\n"
            "Если нужно отредактировать пост:\n"
            "1. /off — отключить комментарии\n"
            "2. Отредактируйте пост в канале\n"
            "3. /on — подключить комментарии обратно\n\n"
            "/chats — добавить/посмотреть каналы",
        )
        return

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

    # Команда /off — отключить комментарии от поста
    if text == "/off":
        posts = scheduler.get_user_published_posts(user_id)
        if not posts:
            api.send_message(chat_id, "У вас нет постов с подключёнными комментариями.")
            return

        buttons = []
        for post_id, message_id, target_chat_id, post_text in posts:
            preview = (post_text or "")[:40]
            if len(post_text or "") > 40:
                preview += "..."
            if not preview:
                preview = f"Пост {post_id}"
            buttons.append([{"type": "callback", "text": preview, "payload": f"detach_{post_id}"}])

        api.send_message_with_keyboard(chat_id, "Выберите пост, от которого отключить комментарии:", buttons)
        return

    # Команда /on — подключить комментарии обратно
    if text == "/on":
        posts = scheduler.get_user_published_posts(user_id)
        if not posts:
            api.send_message(chat_id, "У вас нет постов.")
            return

        buttons = []
        for post_id, message_id, target_chat_id, post_text in posts:
            preview = (post_text or "")[:40]
            if len(post_text or "") > 40:
                preview += "..."
            if not preview:
                preview = f"Пост {post_id}"
            buttons.append([{"type": "callback", "text": preview, "payload": f"reattach_{post_id}"}])

        api.send_message_with_keyboard(chat_id, "Выберите пост, к которому подключить комментарии:", buttons)
        return

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

    # ─── Машина состояний ───
    state = u.get("state", "idle")

    if state == "idle":
        api.send_message(
            chat_id,
            "Перешлите мне пост из канала, и я подключу к нему комментарии.\n\n"
            "Или отправьте /help для справки.",
        )
        return


def handle_forward(user_id, chat_id, link, text):
    """Обработать пересланное сообщение — подключить комментарии."""
    # Извлекаем данные о пересланном сообщении
    fwd_message = link.get("message", {})
    fwd_mid = fwd_message.get("mid")
    fwd_chat_id = link.get("chat_id")

    # Текст может быть в разных местах структуры
    fwd_body = fwd_message.get("body", {})
    fwd_text = ""
    if isinstance(fwd_body, dict):
        fwd_text = fwd_body.get("text", "")

    # Логируем для отладки
    print(f"[forward] link keys={list(link.keys())}")
    print(f"[forward] fwd_message keys={list(fwd_message.keys()) if isinstance(fwd_message, dict) else 'not dict'}")
    print(f"[forward] fwd_mid={fwd_mid} fwd_chat_id={fwd_chat_id}")
    print(f"[forward] fwd_text={fwd_text[:80] if fwd_text else 'empty'}")
    print(f"[forward] body text={text[:80] if text else 'empty'}")

    if not fwd_mid:
        api.send_message(
            chat_id,
            "Не удалось определить ID сообщения.\n"
            "Убедитесь, что вы пересылаете пост из канала, где бот является администратором.",
        )
        return

    # Получаем полную информацию о сообщении через API, если текст не пришёл в link
    post_text = fwd_text or text
    actual_chat_id = fwd_chat_id
    if not post_text or not actual_chat_id:
        msg_info = api.get_message_info(fwd_mid)
        if msg_info:
            if not post_text:
                msg_body = msg_info.get("body", {})
                if isinstance(msg_body, dict):
                    post_text = msg_body.get("text", "")
            if not actual_chat_id:
                recipient = msg_info.get("recipient", {})
                actual_chat_id = recipient.get("chat_id")
        print(f"[forward] after API: post_text={post_text[:80] if post_text else 'empty'} actual_chat_id={actual_chat_id}")

    # Подключаем комментарии к оригинальному посту
    try:
        post_id = api.attach_comments_to_post(fwd_mid, actual_chat_id, post_text)
        scheduler.save_published_post(post_id, fwd_mid, actual_chat_id or 0, user_id=user_id, post_text=post_text)
        api.send_message(chat_id, "Комментарии подключены к посту!")
    except Exception as e:
        print(f"[forward] ошибка: {e}")
        api.send_message(
            chat_id,
            f"Ошибка при подключении комментариев: {e}\n"
            "Убедитесь, что бот добавлен в канал как администратор "
            "и пост опубликован менее 24 часов назад.",
        )


def handle_callback(update):
    """Обработать нажатие inline-кнопки."""
    print(f"[callback] raw update: {update}")
    callback = update.get("callback", {})
    payload = callback.get("payload", "")
    callback_id = callback.get("callback_id", "")
    user_id = str(callback.get("user", {}).get("user_id", ""))
    chat_id = update.get("message", {}).get("recipient", {}).get("chat_id")
    print(f"[callback] payload={payload} callback_id={callback_id} user_id={user_id} chat_id={chat_id}")

    if not user_id or not chat_id:
        return

    scheduler.save_user_chat(user_id, chat_id)
    api.answer_callback(callback_id)

    # Отключить комментарии
    if payload.startswith("detach_"):
        selected_post_id = payload.replace("detach_", "", 1)
        posts = scheduler.get_user_published_posts(user_id)
        for post_id, message_id, target_chat_id, post_text in posts:
            if post_id == selected_post_id:
                try:
                    api.detach_comments_from_post(message_id)
                    api.send_message(chat_id, "Комментарии отключены. Теперь можете отредактировать пост.\n\nЧтобы подключить обратно — /on")
                except Exception as e:
                    api.send_message(chat_id, f"Ошибка: {e}")
                return
        api.send_message(chat_id, "Пост не найден.")
        return

    # Подключить комментарии обратно
    if payload.startswith("reattach_"):
        selected_post_id = payload.replace("reattach_", "", 1)
        posts = scheduler.get_user_published_posts(user_id)
        for post_id, message_id, target_chat_id, post_text in posts:
            if post_id == selected_post_id:
                try:
                    api.reattach_comments_to_post(message_id, post_id)
                    api.send_message(chat_id, "Комментарии подключены обратно!")
                except Exception as e:
                    api.send_message(chat_id, f"Ошибка: {e}")
                return
        api.send_message(chat_id, "Пост не найден.")
        return


def handle_bot_started(update):
    """Обработать событие запуска бота пользователем."""
    user = update.get("user", {})
    user_id = str(user.get("user_id", ""))
    chat_id = update.get("chat_id")

    if not user_id or not chat_id:
        return

    print(f"[bot_started] user_id={user_id} chat_id={chat_id}")

    scheduler.save_user_chat(user_id, chat_id)
    reset_user(user_id)

    # Обработать ожидающие запросы профилей
    scheduler.process_profile_requests()

    # Приветствие
    buttons = [
        [{"type": "link", "text": "MIL.LE Digital — наши услуги", "url": "https://milledigital.ru/mini-app.html"}]
    ]

    welcome_text = (
        "Привет! Это бот от MIL.LE Digital — агентства комплексного Digital-присутствия.\n\n"
        "Что мы делаем:\n"
        "- Продвигаем каналы в Max\n"
        "- Создаём чат-ботов и мини-приложения\n"
        "- Ведём трафик на каналы в Max\n"
        "- Приводим клиентов через Max\n\n"
        "А ещё мы подключаем к каналам комментарии — как у основателя нашего агентства Александра Литау.\n\n"
        "Чтобы подключить комментарии — просто перешлите мне пост из канала!"
    )

    link_text = "Александра Литау"
    link_start = welcome_text.index(link_text)
    welcome_markup = [
        {"type": "link", "from": link_start, "length": len(link_text), "url": "https://max.ru/id381209292606_biz"}
    ]

    api.send_message_with_keyboard(
        chat_id,
        welcome_text,
        buttons,
        markup=welcome_markup,
    )


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
                elif update_type == "bot_started":
                    handle_bot_started(update)
    except KeyboardInterrupt:
        print("\nОстановка бота...")
        scheduler.stop_scheduler()


if __name__ == "__main__":
    main()
