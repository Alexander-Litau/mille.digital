import sqlite3
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
    conn.commit()
    conn.close()


def add_scheduled_post(chat_id, text, publish_at):
    """Добавить отложенный пост. publish_at — datetime объект."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO scheduled_posts (chat_id, text, publish_at) VALUES (?, ?, ?)",
        (chat_id, text, publish_at.isoformat()),
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
        "SELECT id, chat_id, text FROM scheduled_posts WHERE published = 0 AND publish_at <= ?",
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
    for post_db_id, chat_id, text in posts:
        try:
            result, post_id, message_id = api.send_post_with_comments(chat_id, text)
            mark_published(post_db_id)
            if message_id:
                save_published_post(post_id, message_id, chat_id)
            print(f"[scheduler] опубликован пост #{post_db_id} в чат {chat_id}")
        except Exception as e:
            print(f"[scheduler] ошибка публикации поста #{post_db_id}: {e}")


def update_comment_buttons():
    """Проверить Firebase и обновить кнопки комментариев на всех постах."""
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
    # Обновляем кнопки комментариев каждые 60 сек
    _scheduler.add_job(update_comment_buttons, "interval", seconds=60)
    _scheduler.start()
    print("[scheduler] планировщик запущен")


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
