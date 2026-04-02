import os
from pathlib import Path

_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().strip().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN", "")
API_BASE = "https://platform-api.max.ru"
BOT_USERNAME = "id381209292606_2_bot"
MINI_APP_URL = "https://milledigital.ru/mini-app.html"
