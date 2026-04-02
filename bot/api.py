import requests
import time
import random
import html as html_module
from config import API_BASE, BOT_TOKEN, COMMENTS_APP_URL, COMMENTS_DEEPLINK, FIREBASE_DB_URL


def _headers():
    return {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}


def markup_to_html(text, markup):
    """Конвертировать текст + markup массив в HTML-текст.

    markup — список вида:
      [{'from': 0, 'length': 6, 'type': 'strong'},
       {'from': 7, 'length': 6, 'type': 'emphasized'},
       {'from': 10, 'length': 5, 'type': 'link', 'url': '...'}]

    Возвращает HTML-строку с тегами.
    """
    if not markup:
        return text

    # Маппинг типов разметки на HTML-теги
    tag_map = {
        "strong": ("b", None),
        "emphasized": ("i", None),
        "strikethrough": ("s", None),
        "underline": ("u", None),
        "monospace": ("code", None),
        "code": ("code", None),
        "link": ("a", "url"),       # <a href="...">
        "mention": ("a", "url"),
    }

    # Собираем события открытия/закрытия тегов
    events = []  # (позиция, приоритет, 'open'/'close', tag, attr)
    for m in markup:
        mtype = m.get("type", "")
        start = m.get("from", 0)
        length = m.get("length", 0)
        end = start + length

        if mtype not in tag_map:
            continue

        tag, url_key = tag_map[mtype]
        url = m.get(url_key) if url_key else None

        # open: сортируем по позиции, потом open перед close при той же позиции
        events.append((start, 0, "open", tag, url))
        events.append((end, 1, "close", tag, None))

    # Сортируем: по позиции, потом close перед open при одной позиции
    events.sort(key=lambda e: (e[0], e[1]))

    # Строим результат
    result = []
    pos = 0
    for ev_pos, _, ev_type, tag, url in events:
        # Добавляем текст до этой позиции (экранируем HTML)
        if ev_pos > pos:
            result.append(html_module.escape(text[pos:ev_pos]))
            pos = ev_pos

        if ev_type == "open":
            if tag == "a" and url:
                result.append(f'<a href="{html_module.escape(url)}">')
            else:
                result.append(f"<{tag}>")
        else:
            result.append(f"</{tag}>")

    # Остаток текста
    if pos < len(text):
        result.append(html_module.escape(text[pos:]))

    return "".join(result)


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


def send_message(chat_id, text, attachments=None, markup=None):
    """Отправить сообщение в чат/канал."""
    params = {"chat_id": chat_id}
    if markup:
        # Конвертируем markup в HTML и отправляем с format: html
        body = {"text": markup_to_html(text, markup), "format": "html"}
    else:
        body = {"text": text}
    if attachments:
        body["attachments"] = attachments
    print(f"[send_message] chat_id={chat_id} body={body}")
    r = requests.post(f"{API_BASE}/messages", headers=_headers(), params=params, json=body)
    if not r.ok:
        print(f"[send_message] ERROR {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()


def send_message_with_keyboard(chat_id, text, buttons, markup=None):
    """Отправить сообщение с inline-клавиатурой."""
    attachments = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
    return send_message(chat_id, text, attachments=attachments, markup=markup)


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
        print(f"[get_message_info] mid={message_id} stat={data.get('stat')} body_keys={list(data.get('body', {}).keys()) if isinstance(data.get('body'), dict) else 'none'}")
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


def send_post_with_comments(chat_id, post_text, markup=None):
    """Опубликовать пост с кнопкой 'Прокомментировать'."""
    post_id = f"post_{int(time.time())}_{random.randint(1000, 9999)}"

    buttons = [
        [{"type": "link", "text": "Прокомментировать", "url": f"{COMMENTS_DEEPLINK}?startapp={post_id}"}]
    ]

    result = send_message_with_keyboard(chat_id, post_text, buttons, markup=markup)

    # Извлекаем message_id из ответа API
    message_id = None
    msg = result.get("message", {})
    message_id = msg.get("body", {}).get("mid") or msg.get("mid")

    # Сохраняем пост в Firebase с инфо о канале и статистикой
    save_post_to_firebase(post_id, post_text, chat_id, message_id)

    return result, post_id, message_id


def attach_comments_to_post(message_id, chat_id, post_text):
    """Подключить комментарии к существующему посту в канале.

    Редактирует оригинальный пост, добавляя кнопку 'Прокомментировать'.
    Сохраняет пост в Firebase.
    Возвращает post_id.
    """
    post_id = f"post_{int(time.time())}_{random.randint(1000, 9999)}"

    buttons = [
        [{"type": "link", "text": "Прокомментировать", "url": f"{COMMENTS_DEEPLINK}?startapp={post_id}"}]
    ]
    attachments = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]

    # Редактируем оригинальный пост — добавляем только кнопку, текст не трогаем
    params = {"message_id": message_id}
    body = {"attachments": attachments}
    print(f"[attach_comments] message_id={message_id} post_id={post_id}")
    r = requests.put(f"{API_BASE}/messages", headers=_headers(), params=params, json=body)
    if not r.ok:
        print(f"[attach_comments] ERROR {r.status_code}: {r.text}")
    r.raise_for_status()

    # Сохраняем пост в Firebase
    save_post_to_firebase(post_id, post_text, chat_id, message_id)

    return post_id


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


def edit_message_with_keyboard(message_id, text, post_id, markup=None):
    """Редактировать текст поста, сохраняя кнопку комментариев."""
    # Получаем текущее количество комментариев для кнопки
    count = get_comments_count(post_id) or 0
    if count == 0:
        btn_text = "Прокомментировать"
    else:
        btn_text = f"{count} {_pluralize_comments(count)}"

    buttons = [
        [{"type": "link", "text": btn_text, "url": f"{COMMENTS_DEEPLINK}?startapp={post_id}"}]
    ]
    attachments = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]

    body = {"attachments": attachments}
    if markup:
        body["text"] = markup_to_html(text, markup)
        body["format"] = "html"
    else:
        body["text"] = text

    params = {"message_id": message_id}
    print(f"[edit_message_with_keyboard] message_id={message_id} post_id={post_id}")
    r = requests.put(f"{API_BASE}/messages", headers=_headers(), params=params, json=body)
    if not r.ok:
        print(f"[edit_message_with_keyboard] ERROR {r.status_code}: {r.text}")
    r.raise_for_status()

    # Обновляем текст поста в Firebase
    try:
        fb_url = f"{FIREBASE_DB_URL}/posts/{post_id}/text.json"
        requests.put(fb_url, json=text, timeout=10)
    except Exception as e:
        print(f"[edit_message_with_keyboard] firebase error: {e}")

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
