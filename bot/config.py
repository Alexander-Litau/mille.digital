import os
from pathlib import Path

# Загружаем .env файл если есть
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().strip().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Токен бота из Max — получить у @MasterBot
BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN", "")

# Max Bot API
API_BASE = "https://platform-api.max.ru"

# URL мини-приложения комментариев
COMMENTS_APP_URL = "https://milledigital.ru/comments.html"

# Диплинк на мини-приложение через Max (открывается без подтверждения)
BOT_USERNAME = os.environ.get("MAX_BOT_USERNAME", "id381209292606_1_bot")
COMMENTS_DEEPLINK = f"https://max.ru/{BOT_USERNAME}"

# Firebase Realtime Database URL (из comments.html)
FIREBASE_DB_URL = "https://mille-digital-comments-default-rtdb.asia-southeast1.firebasedatabase.app"

# Часовой пояс для отложенного постинга (Иркутск, UTC+8)
TIMEZONE = "Asia/Irkutsk"

# Файл базы данных SQLite
DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")
