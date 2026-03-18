import requests
import time
import random
from config import API_BASE, BOT_TOKEN, COMMENTS_APP_URL, COMMENTS_DEEPLINK, FIREBASE_DB_URL


def _headers():
    return {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}


def get_updates(marker=None, timeout=30):
    """Long polling для получения обновлений от пользователей."""
    params = {"timeout": timeout, "types": "message_created,message_callback,bot_started"}
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
    print(f"[send_message] chat_id={chat_id} body={body}")
    r = requests.post(f"{API_BASE}/messages", headers=_headers(), params=params, json=body)
    if not r.ok:
        print(f"[send_message] ERROR {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()


def send_message_with_keyboard(chat_id, text, buttons):
    """Отправить сообщение с inline-клавиатурой."""
    attachments = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
    return send_message(chat_id, text, attachments=attachments)


def get_chat_info(chat_id):
    """Получить информацию о чате/канале."""
    try:
        r = requests.get(f"{API_BASE}/chats/{chat_id}", headers=_headers(), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[get_chat_info] ошибка: {e}")
        return {}


def get_message_info(message_id):
    """Получить информацию о сообщении (включая stat для каналов)."""
    try:
        r = requests.get(f"{API_BASE}/messages/{message_id}", headers=_headers(), timeout=10)
        r.raise_for_status()
        data = r.json()
        print(f"[get_message_info] mid={message_id} response_keys={list(data.keys()) if isinstance(data, dict) else 'not_dict'}")
        return data
    except Exception as e:
        print(f"[get_message_info] ошибка: {e}")
        return {}


def save_post_to_firebase(post_id, post_text, chat_id, message_id=None):
    """Сохранить пост в Firebase с информацией о канале и статистикой."""
    fb_data = {
        "text": post_text,
        "timestamp": int(time.time() * 1000),
        "chat_id": chat_id,
    }

    # Получаем инфо о канале
    chat_info = get_chat_info(chat_id)
    print(f"[firebase] chat_info: {chat_info}")
    if chat_info:
        fb_data["channel_name"] = chat_info.get("title", "")
        icon = chat_info.get("icon")
        if icon and isinstance(icon, dict):
            fb_data["channel_icon"] = icon.get("url", "")
        # Сохраняем ссылку на канал (полный URL)
        if chat_info.get("link"):
            fb_data["channel_link"] = chat_info["link"]

    # Получаем статистику сообщения (просмотры)
    if message_id:
        fb_data["message_id"] = message_id
        msg_info = get_message_info(message_id)
        if msg_info:
            stat = msg_info.get("stat")
            if stat and isinstance(stat, dict):
                fb_data["views"] = stat.get("views", 0)
            fb_data["msg_timestamp"] = msg_info.get("timestamp", fb_data["timestamp"])

    try:
        fb_url = f"{FIREBASE_DB_URL}/posts/{post_id}.json"
        requests.put(fb_url, json=fb_data, timeout=10)
        print(f"[firebase] пост {post_id} сохранён: channel={fb_data.get('channel_name')}")
    except Exception as e:
        print(f"[firebase] ошибка сохранения поста: {e}")


def update_post_stats_firebase(post_id, message_id):
    """Обновить статистику поста в Firebase (просмотры)."""
    msg_info = get_message_info(message_id)
    if not msg_info:
        return
    stat = msg_info.get("stat")
    if stat and isinstance(stat, dict):
        try:
            fb_url = f"{FIREBASE_DB_URL}/posts/{post_id}/views.json"
            requests.put(fb_url, json=stat.get("views", 0), timeout=10)
        except Exception as e:
            print(f"[firebase] ошибка обновления статистики: {e}")


def send_post_with_comments(chat_id, post_text):
    """Опубликовать пост с кнопкой 'Прокомментировать'."""
    post_id = f"post_{int(time.time())}_{random.randint(1000, 9999)}"

    buttons = [
        [{"type": "link", "text": "Прокомментировать", "url": f"{COMMENTS_DEEPLINK}?startapp={post_id}"}]
    ]

    result = send_message_with_keyboard(chat_id, post_text, buttons)

    # Извлекаем message_id из ответа API
    message_id = None
    msg = result.get("message", {})
    message_id = msg.get("body", {}).get("mid") or msg.get("mid")

    # Сохраняем пост в Firebase с инфо о канале и статистикой
    save_post_to_firebase(post_id, post_text, chat_id, message_id)

    return result, post_id, message_id


def edit_message(message_id, text=None, attachments=None):
    """Редактировать существующее сообщение."""
    params = {"message_id": message_id}
    body = {}
    if text is not None:
        body["text"] = text
    if attachments is not None:
        body["attachments"] = attachments
    print(f"[edit_message] message_id={message_id} body={body}")
    r = requests.put(
        f"{API_BASE}/messages", headers=_headers(), params=params, json=body
    )
    if not r.ok:
        print(f"[edit_message] ERROR {r.status_code}: {r.text}")
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
        [{"type": "link", "text": btn_text, "url": f"{COMMENTS_DEEPLINK}?startapp={post_id}"}]
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


def send_contact_profile(chat_id, target_user_id, target_name, post_id=""):
    """Отправить профиль пользователя как контакт + кнопку вернуться в комментарии."""
    # Отправляем контакт
    contact_attachment = {
        "type": "contact",
        "payload": {
            "name": target_name,
            "contact_id": int(target_user_id),
        }
    }

    try:
        params = {"chat_id": chat_id}
        body = {
            "attachments": [contact_attachment],
        }
        print(f"[send_contact] chat_id={chat_id} target={target_user_id} name={target_name}")
        r = requests.post(f"{API_BASE}/messages", headers=_headers(), params=params, json=body)
        if not r.ok:
            print(f"[send_contact] ERROR {r.status_code}: {r.text}")
            # Если контакт не работает, отправим просто текст
            body2 = {"text": f"Профиль 👆 {target_name}"}
            requests.post(f"{API_BASE}/messages", headers=_headers(), params=params, json=body2)
        else:
            r.raise_for_status()
    except Exception as e:
        print(f"[send_contact] ошибка: {e}")


def answer_callback(callback_id, text=None):
    """Ответить на нажатие inline-кнопки."""
    params = {"callback_id": callback_id}
    body = {}
    if text:
        body["notification"] = text
    try:
        r = requests.post(f"{API_BASE}/answers", headers=_headers(), params=params, json=body)
        r.raise_for_status()
    except Exception as e:
        print(f"[answer_callback] ошибка: {e}")
