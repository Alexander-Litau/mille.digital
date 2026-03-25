"""
MAX Bot API обёртка для воронки mil.le digital.
Отправка сообщений, файлов, клавиатур, обработка callback-ов.
"""

import requests
import time
import os
from config import API_BASE, BOT_TOKEN, FIREBASE_DB_URL


def _headers():
    return {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}


def _headers_no_content_type():
    return {"Authorization": BOT_TOKEN}


# ─── Получение обновлений ───

def get_updates(marker=None, timeout=30):
    """Long polling для получения обновлений."""
    params = {
        "timeout": timeout,
        "types": "message_created,message_callback,bot_started",
    }
    if marker:
        params["marker"] = marker
    try:
        r = requests.get(
            f"{API_BASE}/updates",
            headers=_headers(),
            params=params,
            timeout=timeout + 5,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[get_updates] ошибка: {e}")
        time.sleep(3)
        return {}


# ─── Отправка сообщений ───

def send_message(chat_id, text, attachments=None, markup=None):
    """Отправить текстовое сообщение."""
    params = {"chat_id": chat_id}
    body = {"text": text}
    if attachments:
        body["attachments"] = attachments
    if markup:
        body["link"] = {"type": "forward"}  # не нужно, убираем
        # markup в MAX Bot API передаётся в format
        # Для простого текста не нужен
    print(f"[send_message] chat_id={chat_id} text={text[:50]}...")
    r = requests.post(
        f"{API_BASE}/messages", headers=_headers(), params=params, json=body
    )
    if not r.ok:
        print(f"[send_message] ERROR {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()


def send_message_with_keyboard(chat_id, text, buttons):
    """Отправить сообщение с inline-клавиатурой."""
    attachments = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
    return send_message(chat_id, text, attachments=attachments)


def answer_callback(callback_id, text=None):
    """Ответить на нажатие inline-кнопки."""
    params = {"callback_id": callback_id}
    body = {}
    if text:
        body["notification"] = text
    try:
        r = requests.post(
            f"{API_BASE}/answers", headers=_headers(), params=params, json=body
        )
        r.raise_for_status()
    except Exception as e:
        print(f"[answer_callback] ошибка: {e}")


# ─── Загрузка и отправка файлов ───

def upload_file(file_path):
    """Загрузить файл в MAX и получить token для отправки.

    1. POST /uploads → получаем URL для загрузки
    2. POST {url} → загружаем файл
    Возвращает token файла.
    """
    # Шаг 1: получить URL для загрузки (type передаётся как query-параметр)
    r = requests.post(
        f"{API_BASE}/uploads",
        headers=_headers(),
        params={"type": "file"},
    )
    r.raise_for_status()
    data = r.json()
    upload_url = data.get("url")

    if not upload_url:
        raise ValueError(f"Не получен URL для загрузки: {data}")

    # Шаг 2: загрузить файл на полученный URL
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        r2 = requests.post(
            upload_url,
            files={"file": (filename, f, "application/pdf")},
        )
    r2.raise_for_status()

    # Извлекаем token/fileId из ответа
    file_info = r2.json()
    print(f"[upload_file] Ответ загрузки: {file_info}")
    token = None

    if isinstance(file_info, dict):
        # MAX может вернуть token, fileId, или вложенную структуру
        token = (
            file_info.get("token")
            or file_info.get("fileId")
            or file_info.get("id")
        )
        if not token:
            payload = file_info.get("payload", {})
            token = payload.get("token") or payload.get("fileId")
        if not token and "photos" in file_info:
            # Для изображений
            photos = file_info["photos"]
            if isinstance(photos, dict):
                for v in photos.values():
                    if isinstance(v, dict) and "token" in v:
                        token = v["token"]
                        break

    if not token:
        raise ValueError(f"Не удалось получить token файла: {file_info}")

    print(f"[upload_file] {filename} загружен, token={token[:20]}...")
    return token


def send_file_message(chat_id, file_token, text=None, filename=None):
    """Отправить сообщение с файлом (по token из upload_file)."""
    attachment = {
        "type": "file",
        "payload": {"token": file_token},
    }
    if filename:
        attachment["filename"] = filename

    params = {"chat_id": chat_id}
    body = {"attachments": [attachment]}
    if text:
        body["text"] = text

    print(f"[send_file] chat_id={chat_id} filename={filename}")
    r = requests.post(
        f"{API_BASE}/messages", headers=_headers(), params=params, json=body
    )
    if not r.ok:
        print(f"[send_file] ERROR {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()


# ─── Firebase helpers ───

def firebase_get(path):
    """Прочитать данные из Firebase."""
    try:
        r = requests.get(f"{FIREBASE_DB_URL}/{path}.json", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[firebase_get] ошибка {path}: {e}")
        return None


def firebase_set(path, data):
    """Записать данные в Firebase (перезапись)."""
    try:
        r = requests.put(f"{FIREBASE_DB_URL}/{path}.json", json=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[firebase_set] ошибка {path}: {e}")
        return None


def firebase_update(path, data):
    """Обновить данные в Firebase (merge)."""
    try:
        r = requests.patch(f"{FIREBASE_DB_URL}/{path}.json", json=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[firebase_update] ошибка {path}: {e}")
        return None


def firebase_push(path, data):
    """Добавить запись в Firebase (автоматический ID)."""
    try:
        r = requests.post(f"{FIREBASE_DB_URL}/{path}.json", json=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[firebase_push] ошибка {path}: {e}")
        return None


def firebase_delete(path):
    """Удалить данные из Firebase."""
    try:
        r = requests.delete(f"{FIREBASE_DB_URL}/{path}.json", timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[firebase_delete] ошибка {path}: {e}")
