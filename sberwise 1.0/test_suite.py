"""
Автоматизированный комплексный тестовый набор для проверки всего проекта СберСплит.
Запуск: python test_suite.py
"""

import sys
import os
import sqlite3
import asyncio
from datetime import datetime

# Настройка UTF-8 для Windows консоли
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Подключаем модули проекта
from database import (
    init_db,
    get_db,
    get_or_create_user,
    get_or_create_group,
    add_member_to_group,
    add_expense,
    get_group_balances,
    get_category_totals,
    simplify_debts,
    add_settlement,
)
from ai_module import _rule_based_categorize, get_ai_engine_status
from scoring_engine import calculate_comprehensive_score, calculate_budget_forecast
from receipt_parser import parse_pdf_receipt
from web_server import create_web_app


def test_nlp_categorization():
    print("▶️ [1/5] Тестирование NLP-движка категоризации...")
    test_cases = [
        ("DNS цифровая и бытовая техника", "💻 Техника"),
        ("Оплата в PYATEROCHKA 11121", "🍞 Продукты"),
        ("Оплата в MONETKA Zlatoust", "🍞 Продукты"),
        ("Лукойл АЗС №74", "🚕 Транспорт"),
        ("Яндекс Go поездка", "🚕 Транспорт"),
        ("Аптека Живика таблетки", "💊 Здоровье"),
        ("Квартплата Энергосбыт", "💡 Коммуналка"),
        ("MTS MUSIC подписка", "📱 Связь"),
        ("Билеты в кино Синема", "🎬 Развлечения"),
        ("Читай-Город книги", "📚 Образование"),
    ]

    all_passed = True
    for text, expected_cat in test_cases:
        cat, _ = _rule_based_categorize(text)
        status = "✅" if cat == expected_cat else "❌"
        if cat != expected_cat:
            all_passed = False
            print(f"   {status} '{text}' -> получено '{cat}', ожидалось '{expected_cat}'")
    
    assert all_passed, "Тесты NLP не пройдены!"
    print("   ✅ Все 10 сценариев категоризации успешно пройдены!\n")


def test_database_and_balances():
    print("▶️ [2/5] Тестирование базы данных и балансов...")
    conn = get_db()
    
    # Создание тестовых участников
    u1 = get_or_create_user(conn, 999901, "test_alice", "Алиса")
    u2 = get_or_create_user(conn, 999902, "test_bob", "Боб")
    grp = get_or_create_group(conn, -999900, "Тестовая группа")
    
    add_member_to_group(conn, grp["id"], u1["id"])
    add_member_to_group(conn, grp["id"], u2["id"])

    # Алиса платит 1000 за обоих (по 500 на каждого)
    add_expense(conn, grp["id"], u1["id"], 1000.0, "Пицца", "🍞 Продукты", [u1["id"], u2["id"]])

    balances = get_group_balances(conn, grp["id"])
    assert round(balances[u1["id"]], 2) == 500.0, f"Ошибка баланса u1: {balances[u1['id']]}"
    assert round(balances[u2["id"]], 2) == -500.0, f"Ошибка баланса u2: {balances[u2['id']]}"

    # Упрощение долгов
    debts = simplify_debts(balances)
    assert len(debts) == 1
    assert debts[0][0] == u2["id"]  # Боб должен Алисе 500
    assert debts[0][1] == u1["id"]
    assert round(debts[0][2], 2) == 500.0

    # Боб возвращает 500
    add_settlement(conn, grp["id"], u2["id"], u1["id"], 500.0)
    balances_after = get_group_balances(conn, grp["id"])
    assert round(balances_after[u1["id"]], 2) == 0.0
    assert round(balances_after[u2["id"]], 2) == 0.0

    conn.close()
    print("   ✅ База данных, сплиты, сальдо и погашения работают на 100%!\n")


def test_scoring_engine():
    print("▶️ [3/5] Тестирование Альтернативного Скоринга Сбера (300-850)...")
    profile = calculate_comprehensive_score(
        user_id=1,
        user_display_name="Тестовый Пользователь",
        expenses_paid_count=12,
        expenses_paid_total=25000.0,
        user_share_total=12500.0,
        current_balance=2500.0,
        settlements_sent_count=3,
        settlements_sent_total=3000.0,
        settlements_received_count=2,
        verified_receipts_count=8,
        avg_days_to_settle=1.2,
    )

    assert 300 <= profile["score"] <= 850, f"Скоринг вне диапазона: {profile['score']}"
    assert profile["grade"] in ["AAA", "AA", "A", "B", "C"]
    assert "discipline" in profile["factors"]
    assert "velocity" in profile["factors"]
    assert "contribution" in profile["factors"]
    assert "transparency" in profile["factors"]

    # Тестирование прогноза бюджета
    forecast = calculate_budget_forecast(
        total_spent_month=32000.0,
        days_elapsed=10,
        days_in_month=30,
        target_budget=50000.0,
    )
    assert forecast["daily_burn_rate"] == 3200.0
    assert forecast["is_overbudget"] is True
    assert forecast["days_until_critical"] > 0

    print(f"   ✅ Скоринг рассчитан: {profile['score']} ({profile['grade']}) — {profile['badge']}")
    print(f"   ✅ Прогноз бюджета: расход {forecast['daily_burn_rate']:.0f}₽/день, критическая точка через {forecast['days_until_critical']} дн.\n")


async def test_webapp_and_api():
    print("▶️ [4/5] Тестирование WebApp и REST API endpoints...")
    from aiohttp import test_utils
    app = create_web_app()
    client = test_utils.TestClient(test_utils.TestServer(app))
    await client.start_server()

    # Health check
    res_health = await client.get("/api/health")
    assert res_health.status == 200

    # Summary API
    res_summary = await client.get("/api/group/1/summary")
    assert res_summary.status == 200
    data = await res_summary.json()
    assert "total_expenses" in data
    assert "scoring" in data
    assert "category_totals" in data

    # Static assets for Mini App
    res_index = await client.get("/webapp")
    assert res_index.status == 200
    assert "СберСплит" in (await res_index.text())

    res_css = await client.get("/style.css")
    assert res_css.status == 200

    res_js = await client.get("/app.js")
    assert res_js.status == 200

    await client.close()
    print("   ✅ REST API и статика Telegram Mini App проверены и отдаются без ошибок!\n")


async def test_ai_status_check():
    print("▶️ [5/5] Тестирование статуса AI-модулей...")
    status = await get_ai_engine_status()
    print(f"   ℹ️ Активный провайдер: {status['active_provider']}")
    print(f"   ℹ️ OpenAI: {status['openai']['status']} ({status['openai']['detail']})")
    print(f"   ℹ️ Локальный NLP: {status['local_nlp']['status']}")
    assert status["local_nlp"]["status"] == "active"
    print("   ✅ AI-модуль в боевой готовности!\n")


async def main():
    # Keep the suite self-contained: CI and fresh developer environments do
    # not have an initialized SQLite file yet.
    init_db()
    print("=" * 60)
    print("🚀 ЗАПУСК КОМПЛЕКСНОГО ТЕСТИРОВАНИЯ СБЕРСПЛИТ (КЕЙС 3)")
    print("=" * 60 + "\n")

    test_nlp_categorization()
    test_database_and_balances()
    test_scoring_engine()
    await test_webapp_and_api()
    await test_ai_status_check()

    print("=" * 60)
    print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО! СИСТЕМА 100% ГОТОВА К ДЕМО")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
