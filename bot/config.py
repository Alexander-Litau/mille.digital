import os

# Токен бота из Max — получить у @MasterBot
BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN", "ВАШ_ТОКЕН_СЮДА")

# Max Bot API
API_BASE = "https://platform-api.max.ru"

# URL мини-приложения комментариев
COMMENTS_APP_URL = "https://milledigital.ru/comments.html"

# Диплинк на мини-приложение через Max (открывается без подтверждения)
BOT_USERNAME = os.environ.get("MAX_BOT_USERNAME", "id381209292606_1_bot")
COMMENTS_DEEPLINK = f"https://max.ru/{BOT_USERNAME}"

# Firebase Realtime Database URL (из comments.html)
FIREBASE_DB_URL = "https://mille-digital-comments-default-rtdb.asia-southeast1.firebasedatabase.app"

# Файл базы данных SQLite
DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")
