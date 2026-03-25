#!/usr/bin/env python3
"""
Воронка-бот mil.le digital для мессенджера MAX.

Логика:
  1. Пользователь нажимает /start → приветствие, спрашиваем имя
  2. Имя → спрашиваем нишу
  3. Ниша → отправляем Документ 1 (сразу)
  4. Далее по расписанию: экспертный инсайт, опрос, Документ 2,
     мини-кейс, совет, Документ 3, оффер, дожим
  5. Слово "Аудит" → заявка на бесплатный разбор
"""

import api
import funnel
import scheduler
from config import ADMIN_USER_ID


def handle_update(update):
    """Обработать одно обновление от MAX Bot API."""
    update_type = update.get("update_type", "")

    if update_type == "bot_started":
        # Пользователь нажал Старт
        user = update.get("user", {})
        user_id = str(user.get("user_id", ""))
        chat_id = update.get("chat_id")

        if not user_id or not chat_id:
            return

        # Сохраняем chat_id администратора
        if ADMIN_USER_ID and user_id == ADMIN_USER_ID:
            api.firebase_set("funnel/admin/chat_id", chat_id)
            print(f"[main] Администратор {user_id} обнаружен, chat_id={chat_id}")

        funnel.handle_bot_started(user_id, chat_id)

    elif update_type == "message_created":
        # Текстовое сообщение
        msg = update.get("message", {})
        body = msg.get("body", {})
        text = body.get("text", "").strip()
        sender = msg.get("sender", {})
        user_id = str(sender.get("user_id", ""))
        chat_id = msg.get("recipient", {}).get("chat_id")

        if not user_id or not chat_id or not text:
            return

        # Сохраняем chat_id администратора
        if ADMIN_USER_ID and user_id == ADMIN_USER_ID:
            api.firebase_set("funnel/admin/chat_id", chat_id)

        # Команда /start — перенаправляем в bot_started
        if text == "/start":
            funnel.handle_bot_started(user_id, chat_id)
            return

        # Пробуем обработать в воронке
        handled = funnel.handle_message(user_id, chat_id, text)

        if not handled:
            # Пользователь не в воронке — общее сообщение
            api.send_message(
                chat_id,
                "Спасибо за сообщение! Если хотите получить бесплатный аудит "
                "вашего канала — напишите слово «Аудит»."
            )

    elif update_type == "message_callback":
        # Нажатие inline-кнопки
        callback = update.get("callback", {})
        payload = callback.get("payload", "")
        callback_id = callback.get("callback_id", "")
        user_id = str(callback.get("user", {}).get("user_id", ""))
        chat_id = update.get("message", {}).get("recipient", {}).get("chat_id")

        if not user_id or not chat_id:
            return

        funnel.handle_callback(user_id, chat_id, payload, callback_id)


def main():
    """Главный цикл бота."""
    print("=" * 50)
    print("mil.le digital — Funnel Bot")
    print("=" * 50)

    # Загружаем PDF-токены
    print("[main] Загрузка PDF-токенов...")
    funnel.ensure_file_tokens()

    # Запускаем планировщик
    scheduler.start_scheduler()

    # Long polling
    marker = None
    print("[main] Бот запущен, ожидаю сообщения...")

    try:
        while True:
            data = api.get_updates(marker=marker)
            updates = data.get("updates", [])
            marker = data.get("marker", marker)

            for update in updates:
                try:
                    handle_update(update)
                except Exception as e:
                    print(f"[main] Ошибка обработки: {e}")

    except KeyboardInterrupt:
        print("\n[main] Остановка бота...")
        scheduler.stop_scheduler()


if __name__ == "__main__":
    main()
