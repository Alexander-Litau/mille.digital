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
from zoneinfo import ZoneInfo
from config import TIMEZONE
import api
import scheduler

TZ = ZoneInfo(TIMEZONE)

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
    markup = body.get("markup")  # Форматирование (жирный, курсив и т.д.)
    sender = msg.get("sender", {})
    user_id = str(sender.get("user_id", ""))
    chat_id = msg.get("recipient", {}).get("chat_id")

    if not user_id or not chat_id or not text:
        return

    # Сохраняем маппинг user_id → chat_id
    scheduler.save_user_chat(user_id, chat_id)

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
            "/edit — редактировать опубликованный пост\n"
            "/chats — управление каналами\n"
            "/help — помощь",
        )
        return

    # Команда /about
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
            "/post — создать пост\n"
            "/edit — редактировать опубликованный пост",
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

    # Команда /edit — редактировать опубликованный пост
    if text == "/edit":
        posts = scheduler.get_user_published_posts(user_id)
        if not posts:
            api.send_message(chat_id, "У вас нет опубликованных постов для редактирования.")
            return

        buttons = []
        for post_id, message_id, target_chat_id, post_text in posts:
            preview = (post_text or "")[:40]
            if len(post_text or "") > 40:
                preview += "..."
            if not preview:
                preview = f"Пост {post_id}"
            buttons.append([{"type": "callback", "text": preview, "payload": f"edit_{post_id}"}])

        u["state"] = "editing_select"
        api.send_message_with_keyboard(chat_id, "Выберите пост для редактирования:", buttons)
        return

    # Команда /post — начать создание поста
    if text == "/post":
        u["state"] = "waiting_text"
        api.send_message(chat_id, "Отправьте текст поста:")
        return

    # ─── Машина состояний ───

    state = u.get("state", "idle")

    # Ожидание нового текста для редактирования
    if state == "editing_text":
        edit_post_id = u.get("edit_post_id")
        edit_message_id = u.get("edit_message_id")
        if not edit_post_id or not edit_message_id:
            api.send_message(chat_id, "Ошибка. Попробуйте /edit заново.")
            reset_user(user_id)
            return
        try:
            api.edit_message_with_keyboard(edit_message_id, text, edit_post_id, markup=markup)
            scheduler.update_published_post_text(edit_post_id, text)
            api.send_message(chat_id, "Пост отредактирован!")
        except Exception as e:
            api.send_message(chat_id, f"Ошибка при редактировании: {e}")
        reset_user(user_id)
        return

    # Ожидание текста поста
    if state == "waiting_text":
        u["draft_text"] = text
        u["draft_markup"] = markup
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
        u["draft_markup"] = markup
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
    chat_id = update.get("message", {}).get("recipient", {}).get("chat_id")
    print(f"[callback] payload={payload} callback_id={callback_id} user_id={user_id} chat_id={chat_id}")

    if not user_id or not chat_id:
        return

    # Сохраняем маппинг user_id → chat_id
    scheduler.save_user_chat(user_id, chat_id)

    u = get_user(user_id)
    api.answer_callback(callback_id)

    if payload == "when_now" and u.get("state") == "waiting_when":
        u["draft_time"] = None  # Сейчас
        u["state"] = "waiting_where"
        ask_where(user_id, chat_id)

    elif payload == "when_schedule" and u.get("state") == "waiting_when":
        u["state"] = "waiting_schedule_day"
        show_day_picker(chat_id)

    elif payload.startswith("day_") and u.get("state") == "waiting_schedule_day":
        # payload: day_2026-03-25
        u["draft_date"] = payload.replace("day_", "")
        u["state"] = "waiting_schedule_hour"
        show_hour_picker(chat_id, u["draft_date"])

    elif payload.startswith("hour_") and u.get("state") == "waiting_schedule_hour":
        # payload: hour_14
        u["draft_hour"] = int(payload.replace("hour_", ""))
        u["state"] = "waiting_schedule_minute"
        show_minute_picker(chat_id, u["draft_date"], u["draft_hour"])

    elif payload.startswith("min_") and u.get("state") == "waiting_schedule_minute":
        # payload: min_30
        minute = int(payload.replace("min_", ""))
        dt = datetime.strptime(u["draft_date"], "%Y-%m-%d").replace(
            hour=u["draft_hour"], minute=minute
        )
        now = datetime.now(TZ).replace(tzinfo=None)
        if dt <= now:
            api.send_message(chat_id, "Это время уже прошло. Выберите другое.")
            u["state"] = "waiting_schedule_day"
            show_day_picker(chat_id)
        else:
            u["draft_time"] = dt
            u["state"] = "waiting_where"
            ask_where(user_id, chat_id)

    elif payload.startswith("edit_") and u.get("state") == "editing_select":
        selected_post_id = payload.replace("edit_", "", 1)
        # Найти message_id для этого поста
        posts = scheduler.get_user_published_posts(user_id)
        found = None
        for post_id, message_id, target_chat_id, post_text in posts:
            if post_id == selected_post_id:
                found = (post_id, message_id)
                break
        if not found:
            api.send_message(chat_id, "Пост не найден. Попробуйте /edit заново.")
            reset_user(user_id)
            return
        u["state"] = "editing_text"
        u["edit_post_id"] = found[0]
        u["edit_message_id"] = found[1]
        api.send_message(chat_id, "Отправьте новый текст для этого поста:")

    elif payload.startswith("chat_") and u.get("state") == "waiting_where":
        target_chat_id = int(payload.replace("chat_", ""))
        publish_or_schedule(user_id, chat_id, target_chat_id)


def show_day_picker(chat_id):
    """Показать кнопки выбора дня."""
    from datetime import timedelta
    now = datetime.now(TZ).replace(tzinfo=None)
    today = now.date()

    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    month_names = [
        "", "янв", "фев", "мар", "апр", "мая", "июн",
        "июл", "авг", "сен", "окт", "ноя", "дек"
    ]

    buttons = []
    row = []
    for i in range(7):
        d = today + timedelta(days=i)
        if i == 0:
            label = "Сегодня"
        elif i == 1:
            label = "Завтра"
        else:
            wd = day_names[d.weekday()]
            label = f"{wd}, {d.day} {month_names[d.month]}"
        row.append({"type": "callback", "text": label, "payload": f"day_{d.isoformat()}"})
        if len(row) == 2 or i == 6:
            buttons.append(row)
            row = []

    api.send_message_with_keyboard(chat_id, "Выберите день:", buttons)


def show_hour_picker(chat_id, date_str):
    """Показать кнопки выбора часа."""
    now = datetime.now(TZ).replace(tzinfo=None)
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    is_today = selected_date == now.date()
    current_hour = now.hour if is_today else -1

    buttons = []
    row = []
    for h in range(24):
        if is_today and h < current_hour:
            continue
        row.append({"type": "callback", "text": f"{h:02d}:00", "payload": f"hour_{h}"})
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    if not buttons:
        api.send_message(chat_id, "На сегодня уже нет доступных часов. Выберите другой день.")
        show_day_picker(chat_id)
        return

    month_names = [
        "", "янв", "фев", "мар", "апр", "мая", "июн",
        "июл", "авг", "сен", "окт", "ноя", "дек"
    ]
    label = f"{selected_date.day} {month_names[selected_date.month]}"
    api.send_message_with_keyboard(chat_id, f"{label} — выберите час:", buttons)


def show_minute_picker(chat_id, date_str, hour):
    """Показать кнопки выбора минут."""
    now = datetime.now(TZ).replace(tzinfo=None)
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    is_now_hour = selected_date == now.date() and hour == now.hour

    minutes = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
    buttons = []
    row = []
    for m in minutes:
        if is_now_hour and m <= now.minute:
            continue
        row.append({"type": "callback", "text": f"{hour:02d}:{m:02d}", "payload": f"min_{m}"})
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    if not buttons:
        api.send_message(chat_id, "На этот час уже нет доступных минут. Выберите другой час.")
        show_hour_picker(chat_id, date_str)
        return

    month_names = [
        "", "янв", "фев", "мар", "апр", "мая", "июн",
        "июл", "авг", "сен", "окт", "ноя", "дек"
    ]
    label = f"{selected_date.day} {month_names[selected_date.month]}"
    api.send_message_with_keyboard(chat_id, f"{label}, {hour:02d}:?? — выберите минуты:", buttons)


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
    draft_markup = u.get("draft_markup")
    draft_time = u.get("draft_time")

    if not draft_text:
        api.send_message(bot_chat_id, "Ошибка: текст поста не найден. Начните заново с /post")
        reset_user(user_id)
        return

    if draft_time:
        # Запланировать (сохраняем формат в JSON)
        post_db_id = scheduler.add_scheduled_post(target_chat_id, draft_text, draft_time, draft_markup)
        time_str = draft_time.strftime("%d.%m.%Y в %H:%M")
        api.send_message(
            bot_chat_id,
            f"Пост запланирован на {time_str}!\n"
            f"К нему автоматически подключатся комментарии.",
        )
    else:
        # Опубликовать сейчас
        try:
            result, post_id, message_id = api.send_post_with_comments(target_chat_id, draft_text, draft_markup)
            if message_id:
                scheduler.save_published_post(post_id, message_id, target_chat_id, user_id=user_id, post_text=draft_text)
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


def handle_bot_started(update):
    """Обработать событие запуска бота пользователем."""
    user = update.get("user", {})
    user_id = str(user.get("user_id", ""))
    chat_id = update.get("chat_id")

    if not user_id or not chat_id:
        return

    print(f"[bot_started] user_id={user_id} chat_id={chat_id}")

    # Сохраняем маппинг
    scheduler.save_user_chat(user_id, chat_id)
    reset_user(user_id)

    # Сразу обработать ожидающие запросы профилей для этого пользователя
    scheduler.process_profile_requests()

    # Отправляем приветствие с рекламой и кнопкой на мини-приложение
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
        "Хотите так же? Напишите нам — разберём вашу ситуацию и честно скажем, что имеет смысл, а что нет."
    )

    # Делаем "Александра Литау" кликабельной ссылкой на канал
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
                elif update_type == "bot_started":
                    handle_bot_started(update)
    except KeyboardInterrupt:
        print("\nОстановка бота...")
        scheduler.stop_scheduler()


if __name__ == "__main__":
    main()
