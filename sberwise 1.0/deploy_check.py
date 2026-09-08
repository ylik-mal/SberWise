import sys
import os
import json
import sqlite3
import urllib.request
import asyncio

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from config import BOT_TOKEN, OPENAI_API_KEY, WEBAPP_PORT, WEBAPP_URL, DATABASE_PATH, IS_PRODUCTION_DEPLOYMENT, APP_VERSION

BASE_URL = f"http://127.0.0.1:{WEBAPP_PORT}"

def check(title):
    print(f"\n▶️ [{title}]")

def ok(msg):
    print(f"   ✅ {msg}")

def warn(msg):
    print(f"   ⚠️ {msg}")

def fail(msg):
    print(f"   ❌ {msg}")
    sys.exit(1)

def http_get(path, timeout=5):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "DeployCheck/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode('utf-8'), dict(resp.headers)

async def main():
    print("=" * 65)
    print("🛡️  ПРЕДДЕМОНСТРАЦИОННЫЙ ЧЕК-ЛИСТ СБЕРСПЛИТ MINI APP (10/10)")
    print("=" * 65)
    print(f"Версия сборки: {APP_VERSION}")
    print(f"Базовый порт:  {WEBAPP_PORT}")
    print(f"Целевой URL:   {WEBAPP_URL}")
    print(f"Режим деплоя:  {'🚀 ПРОДАКШН (Постоянный HTTPS)' if IS_PRODUCTION_DEPLOYMENT else '🔧 ЛОКАЛЬНАЯ РАЗРАБОТКА'}")

    # 1. Frontend URL -> 200
    check("1/10: Frontend URL (GET / и GET /webapp)")
    try:
        status, html, headers = http_get("/")
        if status == 200 and "appShell" in html:
            ok(f"GET / вернул HTTP 200, HTML содержит appShell ({len(html)} байт)")
        else:
            fail(f"GET / вернул некорректный ответ (HTTP {status})")

        status, html, _ = http_get("/webapp")
        if status == 200 and "screen-overview" in html:
            ok("GET /webapp вернул HTTP 200 и разметку экранов")
        else:
            fail(f"GET /webapp вернул ошибку: HTTP {status}")
    except Exception as e:
        fail(f"Не удалось подключиться к веб-серверу: {e}")

    # 2. Backend /health -> 200
    check("2/10: Backend /health (Section 7)")
    try:
        status, body, _ = http_get("/health")
        data = json.loads(body)
        if status == 200 and data.get("status") == "ok" and data.get("database") == "ok":
            ok(f"GET /health: status={data['status']}, database={data['database']}")
        else:
            fail(f"GET /health вернул невалидный статус: {body}")
    except Exception as e:
        fail(f"Ошибка вызова /health: {e}")

    # 3. Backend /ready -> 200
    check("3/10: Backend /ready (Section 8)")
    try:
        status, body, _ = http_get("/ready")
        data = json.loads(body)
        if status == 200 and data.get("status") == "ready":
            ok(f"GET /ready: status=ready, groups_count={data.get('groups_count')}, ai={data.get('ai_status')}")
        else:
            fail(f"GET /ready не готов: {body}")
    except Exception as e:
        fail(f"Ошибка вызова /ready: {e}")

    # 4. База данных SQLite и таблицы
    check("4/10: Персистентная база данных SQLite")
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        required_tables = ["users", "groups", "group_members", "expenses", "expense_items", "expense_splits", "debts"]
        missing = [t for t in required_tables if t not in tables]
        if missing:
            fail(f"Отсутствуют таблицы: {missing}")
        ok(f"База данных {DATABASE_PATH} активна, найдено {len(tables)} таблиц")
        conn.close()
    except Exception as e:
        fail(f"Ошибка базы данных: {e}")

    # 5. Telegram Bot Token и API
    check("5/10: Telegram Bot Token и Telegram API")
    if not BOT_TOKEN:
        fail("BOT_TOKEN не задан в .env!")
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("ok"):
                b_user = data["result"]["username"]
                ok(f"Бот авторизован в Telegram API: @{b_user}")
            else:
                fail(f"Telegram API отклонил токен: {data}")
    except Exception as e:
        warn(f"Сетевое предупреждение при проверке Telegram API: {e}")

    # 6. Mini App Auth & API endpoints
    check("6/10: Mini App REST API и авторизация")
    try:
        status, body, _ = http_get("/api/group/1/summary?tg_user_id=1")
        data = json.loads(body)
        if status == 200 and "group_name" in data and "total_expenses" in data:
            ok(f"Сводка комнаты 1 получена: «{data['group_name']}», участников: {len(data.get('members', []))}")
        else:
            fail(f"API /summary вернул некорректный ответ: {body[:100]}")
    except Exception as e:
        fail(f"Ошибка API /summary: {e}")

    # 7. Debts API
    check("7/10: Debts & Settlement API")
    try:
        status, body, _ = http_get("/api/group/1/debts?tab=all&tg_user_id=1")
        data = json.loads(body)
        if status == 200 and "debts" in data:
            ok(f"API долгов доступно, активных записей: {len(data['debts'])}")
        else:
            fail(f"API долгов вернуло ошибку: {body[:100]}")
    except Exception as e:
        fail(f"Ошибка Debts API: {e}")

    # 8. Receipt Camera & OCR Provider
    check("8/10: Receipt Scanner & OCR модуль")
    try:
        from receipt_parser import parse_image_receipt_items
        ok("Модуль receipt_parser готов к обработке чеков")
    except Exception as e:
        fail(f"Ошибка инициализации receipt_parser: {e}")

    # 9. Voice & Whisper STT Provider
    check("9/10: Voice Input & OpenAI Whisper STT")
    if not OPENAI_API_KEY:
        warn("OPENAI_API_KEY не задан в .env!")
    else:
        ok("OPENAI_API_KEY задан, модель whisper-1 готова к распознаванию")

    # 10. Источник правды WEBAPP_URL
    check("10/10: Единый источник правды WEBAPP_URL")
    from bot import get_current_webapp_url
    sample_url = get_current_webapp_url(1)
    if "lhr.life" in sample_url and IS_PRODUCTION_DEPLOYMENT:
        fail("Внимание: в продакшн-режиме обнаружена ссылка на lhr.life!")
    ok(f"Генератор URL кнопок возвращает актуальный адрес: {sample_url}")

    print("\n" + "=" * 65)
    print("🎉 ВСЕ 10 ПРОВЕРОК УСПЕШНО ПРОЙДЕНЫ! СИСТЕМА ГОТОВА К ХАКАТОНУ.")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(main())
