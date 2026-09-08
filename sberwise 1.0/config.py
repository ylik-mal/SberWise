import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_PATH = os.getenv("DATABASE_PATH", "expenses.db")

WEBAPP_PORT = int(os.getenv("PORT", os.getenv("WEBAPP_PORT", "8899")))

raw_webapp_url = os.getenv("WEBAPP_URL", "").strip()
if raw_webapp_url:
    cleaned = raw_webapp_url.rstrip("/")
    if cleaned.endswith("/webapp"):
        cleaned = cleaned[:-7]
    WEBAPP_BASE_URL = cleaned
    WEBAPP_URL = f"{cleaned}/webapp"
else:
    WEBAPP_BASE_URL = f"http://localhost:{WEBAPP_PORT}"
    WEBAPP_URL = f"{WEBAPP_BASE_URL}/webapp"

# Проверка: является ли текущий запуск постоянным продакшн-деплоем
IS_PRODUCTION_DEPLOYMENT = bool(
    WEBAPP_BASE_URL
    and WEBAPP_BASE_URL.lower().startswith("https://")
    and "lhr.life" not in WEBAPP_BASE_URL.lower()
)

APP_VERSION = os.getenv("APP_VERSION", "2.4.0-prod")

# Категории расходов
CATEGORIES = [
    "🍞 Продукты",
    "💻 Техника",
    "💡 Коммуналка",
    "🚕 Транспорт",
    "🎬 Развлечения",
    "💊 Здоровье",
    "👕 Одежда",
    "📚 Образование",
    "🏠 Аренда",
    "📱 Связь",
    "🔧 Другое",
]
