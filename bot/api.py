import requests
import time
import random
from config import API_BASE, BOT_TOKEN, COMMENTS_APP_URL, FIREBASE_DB_URL


def _headers():
    return {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}


def get_updates(marker=None, timeout=30):
    """Long polling для получения обновлений от пользователей."""
    params = {"timeout": timeout, "types": "message_created,message_callback"}
    if marker:
        params["marker"] = marker
    try:
        r = requests.get(
            f"{API_BASE}/updates", headers=_headers(), params=params, timeout=timeout + 5
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[get_updates] ошибка: {e}")
        time.sleep(3)
        return {}


def send_message(chat_id, text, attachments=None):
    """Отправить сообщение в чат/канал."""
    params = {"chat_id": chat_id}
    body = {"text": text}
    if attachments:
        body["attachments"] = attachments
    r = requests.post(f"{API_BASE}/messages", headers=_headers(), params=params, json=body)
    r.raise_for_status()
    return r.json()


def send_message_with_keyboard(chat_id, text, buttons):
    """Отправить сообщение с inline-клавиатурой."""
    attachments = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
    return send_message(chat_id, text, attachments=attachments)


def send_post_with_comments(chat_id, post_text):
    """Опубликовать пост с кнопкой 'Прокомментировать'."""
    post_id = f"post_{int(time.time())}_{random.randint(1000, 9999)}"
    comments_url = f"{COMMENTS_APP_URL}?post={post_id}"

    buttons = [
        [{"type": "open_app", "text": "Прокомментировать", "url": comments_url}]
    ]

    result = send_message_with_keyboard(chat_id, post_text, buttons)

    # Извлекаем message_id из ответа API
    message_id = None
    msg = result.get("message", {})
    message_id = msg.get("body", {}).get("mid") or msg.get("mid")

    return result, post_id, message_id


def edit_message(message_id, text=None, attachments=None):
    """Редактировать существующее сообщение."""
    params = {"message_id": message_id}
    body = {}
    if text is not None:
        body["text"] = text
    if attachments is not None:
        body["attachments"] = attachments
    r = requests.put(
        f"{API_BASE}/messages", headers=_headers(), params=params, json=body
    )
    r.raise_for_status()
    return r.json()


def update_comments_button(message_id, post_id, count):
    """Обновить текст кнопки комментариев на сообщении."""
    comments_url = f"{COMMENTS_APP_URL}?post={post_id}"

    if count == 0:
        btn_text = "Прокомментировать"
    else:
        btn_text = f"{count} {_pluralize_comments(count)}"

    buttons = [
        [{"type": "open_app", "text": btn_text, "url": comments_url}]
    ]
    attachments = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]

    try:
        edit_message(message_id, attachments=attachments)
    except Exception as e:
        print(f"[update_comments_button] ошибка: {e}")


def get_comments_count(post_id):
    """Получить количество комментариев из Firebase REST API."""
    url = f"{FIREBASE_DB_URL}/comments/{post_id}.json?shallow=true"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return 0
        return len(data)
    except Exception as e:
        print(f"[get_comments_count] ошибка: {e}")
        return None


def _pluralize_comments(n):
    """Склонение слова 'комментарий'."""
    abs_n = abs(n) % 100
    last = abs_n % 10
    if 11 <= abs_n <= 19:
        return "комментариев"
    if last == 1:
        return "комментарий"
    if 2 <= last <= 4:
        return "комментария"
    return "комментариев"


def answer_callback(callback_id, text=None):
    """Ответить на нажатие inline-кнопки."""
    body = {"callback_id": callback_id}
    if text:
        body["message"] = text
    try:
        r = requests.post(f"{API_BASE}/answers", headers=_headers(), json=body)
        r.raise_for_status()
    except Exception as e:
        print(f"[answer_callback] ошибка: {e}")
