import os

# Токен бота из MAX — получить у @MasterBot
BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN", "f9LHodD0cOIYW9cA7dL3zBY_w7T5hXgx0hTO9syZfhke-Yn0UUZOxgTK7hhLb71fUWEG7VgNxZ1KJm_NYNa4")

# Max Bot API
API_BASE = "https://platform-api.max.ru"

# Firebase Realtime Database URL (тот же проект, что и для комментариев)
FIREBASE_DB_URL = "https://mille-digital-comments-default-rtdb.asia-southeast1.firebasedatabase.app"

# Часовой пояс (Иркутск, UTC+8)
TIMEZONE = "Asia/Irkutsk"

# Ссылка на профиль Александра Литау в MAX
ADMIN_PROFILE_URL = "https://max.ru/u/f9LHodD0cOJjpA8IcT8R5DX13-0VsNHW-4ulnpIjGedGegtriCUrdGrIveo"

# ID администратора (для уведомлений о заявках на аудит)
# Заполнить после первого запуска — user_id Александра в MAX
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID", "")

# Пути к PDF-документам
DOCS_DIR = os.path.join(os.path.dirname(__file__), "documents")
DOC_PATHS = {
    "doc1": os.path.join(DOCS_DIR, "doc1.pdf"),
    "doc2": os.path.join(DOCS_DIR, "doc2.pdf"),
    "doc3": os.path.join(DOCS_DIR, "doc3.pdf"),
}

DOC_NAMES = {
    "doc1": "Обзор рынка MAX + 5 ошибок.pdf",
    "doc2": "Пошаговый план запуска канала в MAX.pdf",
    "doc3": "Контент-стратегия на 30 дней.pdf",
}

# Задержки между шагами воронки (в секундах)
# Для тестирования можно уменьшить до минут
FUNNEL_DELAYS = {
    "expert_insight": 3 * 3600,      # +3 часа после doc1
    "survey": 21 * 3600,             # +21 час после expert_insight (утро дня 1)
    "doc2": 2 * 3600,                # +2 часа после survey (или +3ч если не ответил)
    "doc2_no_answer": 3 * 3600,      # +3 часа если не ответил на опрос
    "mini_case": 6 * 3600,           # +6 часов после doc2
    "tip": 14 * 3600,                # +14 часов после mini_case (утро дня 2)
    "doc3": 2 * 3600,                # +2 часа после tip
    "offer": 3 * 3600,               # +3 часа после doc3
    "followup": 20 * 3600,           # +20 часов после offer (утро дня 3)
}
