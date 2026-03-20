import sqlite3
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from config import DB_PATH
import api


def init_db():
    """Создать таблицы если их нет."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            publish_at TEXT NOT NULL,
            published INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Миграция: добавить колонку text_format если её нет
    try:
        c.execute("ALTER TABLE scheduled_posts ADD COLUMN text_format TEXT")
    except sqlite3.OperationalError:
        pass  # Колонка уже существует

    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_chats (
            user_id TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            chat_name TEXT,
            PRIMARY KEY (user_id, chat_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS published_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT NOT NULL UNIQUE,
            message_id TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            last_comment_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_chats (
            user_id TEXT PRIMARY KEY,
            chat_id INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_user_chat(user_id, chat_id):
    """Сохранить маппинг user_id → chat_id (диалог с ботом)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO user_chats (user_id, chat_id) VALUES (?, ?)",
        (str(user_id), chat_id),
    )
    conn.commit()
    conn.close()


def get_user_chat_id(user_id):
    """Получить chat_id диалога пользователя с ботом."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM user_chats WHERE user_id = ?", (str(user_id),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def add_scheduled_post(chat_id, text, publish_at, text_format=None):
    """Добавить отложенный пост. publish_at — datetime объект."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    format_json = json.dumps(text_format) if text_format else None
    c.execute(
        "INSERT INTO scheduled_posts (chat_id, text, publish_at, text_format) VALUES (?, ?, ?, ?)",
        (chat_id, text, publish_at.isoformat(), format_json),
    )
    post_db_id = c.lastrowid
    conn.commit()
    conn.close()
    return post_db_id


def get_pending_posts():
    """Получить все неопубликованные посты, время которых наступило."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        "SELECT id, chat_id, text, text_format FROM scheduled_posts WHERE published = 0 AND publish_at <= ?",
        (now,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def mark_published(post_db_id):
    """Пометить пост как опубликованный."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE scheduled_posts SET published = 1 WHERE id = ?", (post_db_id,))
    conn.commit()
    conn.close()


def save_published_post(post_id, message_id, chat_id):
    """Сохранить опубликованный пост для отслеживания комментариев."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO published_posts (post_id, message_id, chat_id) VALUES (?, ?, ?)",
        (post_id, str(message_id), chat_id),
    )
    conn.commit()
    conn.close()


def get_all_published_posts():
    """Получить все опубликованные посты для проверки комментариев."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT post_id, message_id, chat_id, last_comment_count FROM published_posts")
    rows = c.fetchall()
    conn.close()
    return rows


def update_comment_count(post_id, count):
    """Обновить сохранённое количество комментариев."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE published_posts SET last_comment_count = ? WHERE post_id = ?",
        (count, post_id),
    )
    conn.commit()
    conn.close()


def save_chat(user_id, chat_id, chat_name=None):
    """Сохранить канал/чат для пользователя."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO saved_chats (user_id, chat_id, chat_name) VALUES (?, ?, ?)",
        (str(user_id), chat_id, chat_name),
    )
    conn.commit()
    conn.close()


def get_saved_chats(user_id):
    """Получить сохранённые каналы/чаты пользователя."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT chat_id, chat_name FROM saved_chats WHERE user_id = ?",
        (str(user_id),),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def publish_pending():
    """Проверить и опубликовать все ожидающие посты."""
    posts = get_pending_posts()
    for post_db_id, chat_id, text, format_json in posts:
        try:
            text_format = json.loads(format_json) if format_json else None
            result, post_id, message_id = api.send_post_with_comments(chat_id, text, text_format)
            mark_published(post_db_id)
            if message_id:
                save_published_post(post_id, message_id, chat_id)
            print(f"[scheduler] опубликован пост #{post_db_id} в чат {chat_id}")
        except Exception as e:
            print(f"[scheduler] ошибка публикации поста #{post_db_id}: {e}")


def process_profile_requests():
    """Проверить Firebase на запросы профилей и отправить контакты."""
    try:
        import requests as req
        from config import FIREBASE_DB_URL, COMMENTS_DEEPLINK
        url = f"{FIREBASE_DB_URL}/profile_requests.json"
        r = req.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return

        for request_id, request_data in data.items():
            try:
                requester_user_id = str(request_data.get("requester_user_id", ""))
                target_user_id = request_data.get("target_user_id")
                target_name = request_data.get("target_name", "Пользователь")
                post_id = request_data.get("post_id", "")

                # Найти chat_id для отправки сообщения
                chat_id = get_user_chat_id(requester_user_id)
                if not chat_id:
                    print(f"[profile] chat_id не найден для user_id={requester_user_id}")
                    # Помечаем ошибку — mini-app покажет кнопку "Открыть бота"
                    req.patch(f"{FIREBASE_DB_URL}/profile_requests/{request_id}.json",
                              json={"error": "no_chat"}, timeout=10)
                    continue

                # Отправляем контакт
                api.send_contact_profile(chat_id, target_user_id, target_name, post_id)
                print(f"[profile] отправлен профиль {target_name} (id={target_user_id}) -> user {requester_user_id}")

                # Удаляем запрос
                req.delete(f"{FIREBASE_DB_URL}/profile_requests/{request_id}.json", timeout=10)
            except Exception as e:
                print(f"[profile] ошибка обработки запроса {request_id}: {e}")
                # Удаляем проблемный запрос
                try:
                    req.delete(f"{FIREBASE_DB_URL}/profile_requests/{request_id}.json", timeout=10)
                except:
                    pass
    except Exception as e:
        print(f"[profile] ошибка чтения запросов: {e}")


def update_comment_buttons():
    """Проверить Firebase и обновить кнопки комментариев + статистику на всех постах."""
    posts = get_all_published_posts()
    for post_id, message_id, chat_id, last_count in posts:
        try:
            current_count = api.get_comments_count(post_id)
            if current_count is None:
                continue
            if current_count != last_count:
                api.update_comments_button(message_id, post_id, current_count)
                update_comment_count(post_id, current_count)
                print(f"[comments] пост {post_id}: {last_count} -> {current_count}")
            # Обновляем статистику (просмотры) в Firebase
            api.update_post_stats_firebase(post_id, message_id)
        except Exception as e:
            print(f"[comments] ошибка обновления поста {post_id}: {e}")


# Глобальный планировщик
_scheduler = None


def start_scheduler():
    """Запустить фоновый планировщик."""
    global _scheduler
    _scheduler = BackgroundScheduler()
    # Проверяем отложенные посты каждые 30 сек
    _scheduler.add_job(publish_pending, "interval", seconds=30)
    # Обновляем кнопки комментариев каждые 5 сек
    _scheduler.add_job(update_comment_buttons, "interval", seconds=5)
    # Проверяем запросы профилей каждые 2 сек
    _scheduler.add_job(process_profile_requests, "interval", seconds=2)
    _scheduler.start()
    print("[scheduler] планировщик запущен")


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
