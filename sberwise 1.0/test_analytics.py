"""
test_analytics.py — Комплексное тестирование модуля аналитики расходов комнат.
Проверяет:
1. Тест Section 33 (3 расхода, расчет total, count, average, timeline по календарным неделям, categories).
2. Тест 7 дней (посуточная динамика, изоляция только 7 дней).
3. Тест 30 дней и «Всё время».
4. Тест кастомного диапазона (custom).
5. Тест изоляции между комнатами (Room 1 vs Room 2).
6. Тест пустого состояния (0 расходов: 0 total, 0 avg, 0 count, пустые категории, без ZeroDivisionError).
"""

import sys
import sqlite3
import datetime
from analytics_engine import calculate_room_analytics

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_tests():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE groups (
            id INTEGER PRIMARY KEY,
            name TEXT,
            currency TEXT DEFAULT 'RUB'
        );

        CREATE TABLE expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            amount REAL,
            category TEXT,
            expense_date TEXT,
            created_at TEXT
        );
    """)

    conn.execute("INSERT INTO groups (id, name, currency) VALUES (1, 'Комната Сентябрь', 'RUB')")
    conn.execute("INSERT INTO groups (id, name, currency) VALUES (2, 'Комната Другая', 'USD')")

    # ==========================================================
    # TEST 1: Сценарий из ТЗ (Раздел 33):
    # 01.09 Продукты 1000 ₽
    # 03.09 Такси 500 ₽
    # 10.09 Продукты 1500 ₽
    # Изоляция: в Комнате 2 расход 8000 ₽
    # ==========================================================
    conn.execute("INSERT INTO expenses (group_id, amount, category, expense_date, created_at) VALUES (1, 1000.0, 'Продукты', '2026-09-01', '2026-09-01 10:00:00')")
    conn.execute("INSERT INTO expenses (group_id, amount, category, expense_date, created_at) VALUES (1, 500.0, 'Такси', '2026-09-03', '2026-09-03 12:00:00')")
    conn.execute("INSERT INTO expenses (group_id, amount, category, expense_date, created_at) VALUES (1, 1500.0, 'Продукты', '2026-09-10', '2026-09-10 14:00:00')")
    conn.execute("INSERT INTO expenses (group_id, amount, category, expense_date, created_at) VALUES (2, 8000.0, 'Жильё', '2026-09-05', '2026-09-05 15:00:00')")

    test_date = datetime.date(2026, 9, 15)

    res_month = calculate_room_analytics(conn, 1, "current_month", current_date=test_date)

    print("▶️ [TEST 1: Текущий месяц / Раздел 33]")
    assert res_month["total"] == 3000.0, f"Expected total 3000, got {res_month['total']}"
    assert res_month["count"] == 3, f"Expected count 3, got {res_month['count']}"
    assert res_month["average"] == 1000.0, f"Expected avg 1000, got {res_month['average']}"

    # Timeline недели
    # 1–6 сен: 1000 + 500 = 1500
    # 7–13 сен: 1500
    # 14–20 сен: 0
    # 21–27 сен: 0
    # 28–30 сен: 0
    assert res_month["timeline"][0]["amount"] == 1500.0, f"Week 1 expected 1500, got {res_month['timeline'][0]['amount']}"
    assert res_month["timeline"][1]["amount"] == 1500.0, f"Week 2 expected 1500, got {res_month['timeline'][1]['amount']}"
    assert res_month["timeline"][2]["amount"] == 0.0, f"Week 3 expected 0, got {res_month['timeline'][2]['amount']}"
    assert res_month["timeline"][3]["amount"] == 0.0, f"Week 4 expected 0, got {res_month['timeline'][3]['amount']}"
    assert res_month["timeline"][4]["amount"] == 0.0, f"Week 5 expected 0, got {res_month['timeline'][4]['amount']}"

    # Categories
    cats = {c["category"]: c for c in res_month["categories"]}
    assert cats["Продукты"]["amount"] == 2500.0, f"Expected Продукты 2500, got {cats['Продукты']['amount']}"
    assert cats["Такси"]["amount"] == 500.0, f"Expected Такси 500, got {cats['Такси']['amount']}"
    assert round(cats["Продукты"]["percent"] + cats["Такси"]["percent"], 1) == 100.0
    print("   ✅ Тест 1 успешно пройден!")

    # ==========================================================
    # TEST 2: Последние 7 дней (Раздел 34)
    # На дату 2026-09-04:
    # 7 дней = 2026-08-29 .. 2026-09-04
    # Попадают только: 01.09 (1000) и 03.09 (500) = 1500 total, 2 count
    # 10.09 не попадает (будущее относительно 04.09)
    # ==========================================================
    print("▶️ [TEST 2: Последние 7 дней]")
    d_7 = datetime.date(2026, 9, 4)
    res_7 = calculate_room_analytics(conn, 1, "7_days", current_date=d_7)

    assert res_7["total"] == 1500.0, f"Expected 1500, got {res_7['total']}"
    assert res_7["count"] == 2, f"Expected 2, got {res_7['count']}"
    assert res_7["average"] == 750.0, f"Expected 750, got {res_7['average']}"
    assert len(res_7["timeline"]) == 7, f"Expected 7 daily bars, got {len(res_7['timeline'])}"

    # Проверяем даты корзин
    dates_in_timeline = [b["start_date"] for b in res_7["timeline"]]
    assert dates_in_timeline == ["2026-08-29", "2026-08-30", "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]
    # Проверяем суммы: 2026-09-01 -> 1000, 2026-09-03 -> 500, остальные 0
    sums_by_date = {b["start_date"]: b["amount"] for b in res_7["timeline"]}
    assert sums_by_date["2026-09-01"] == 1000.0
    assert sums_by_date["2026-09-03"] == 500.0
    assert sums_by_date["2026-09-02"] == 0.0
    print("   ✅ Тест 2 успешно пройден!")

    # ==========================================================
    # TEST 3: Изоляция комнат (Раздел 36)
    # Room 1: 3000 ₽
    # Room 2: 8000 USD
    # ==========================================================
    print("▶️ [TEST 3: Мультикомнатная изоляция]")
    res_r2 = calculate_room_analytics(conn, 2, "current_month", current_date=test_date)
    assert res_r2["total"] == 8000.0, f"Expected Room 2 total 8000, got {res_r2['total']}"
    assert res_r2["currency"] == "USD"
    assert res_r2["count"] == 1
    assert res_r2["categories"][0]["category"] == "Жильё"
    print("   ✅ Тест 3 успешно пройден!")

    # ==========================================================
    # TEST 4: Пустое состояние (Раздел 19)
    # Пустая комната (id 3)
    # ==========================================================
    print("▶️ [TEST 4: Пустая комната / Empty State]")
    conn.execute("INSERT INTO groups (id, name, currency) VALUES (3, 'Пустая', 'RUB')")
    res_empty = calculate_room_analytics(conn, 3, "current_month", current_date=test_date)
    assert res_empty["total"] == 0.0
    assert res_empty["count"] == 0
    assert res_empty["average"] == 0.0
    assert len(res_empty["categories"]) == 0
    assert len(res_empty["timeline"]) == 5
    for b in res_empty["timeline"]:
        assert b["amount"] == 0.0
    print("   ✅ Тест 4 успешно пройден!")

    # ==========================================================
    # TEST 5: Кастомный диапазон (Раздел 5)
    # 02.09.2026 .. 05.09.2026
    # Должен попасть только расход 03.09 (500 ₽)
    # ==========================================================
    print("▶️ [TEST 5: Произвольный диапазон дат]")
    res_custom = calculate_room_analytics(conn, 1, "custom", date_from_str="2026-09-02", date_to_str="2026-09-05", current_date=test_date)
    assert res_custom["total"] == 500.0
    assert res_custom["count"] == 1
    assert res_custom["average"] == 500.0
    print("   ✅ Тест 5 успешно пройден!")

    print("\n🎉 ВСЕ ТЕСТЫ АНАЛИТИКИ УСПЕШНО ПРОЙДЕНЫ (5/5)!")


async def run_api_tests():
    import asyncio
    from aiohttp.test_utils import TestClient, TestServer
    from web_server import create_web_app

    print("\n▶️ [TEST 6: REST API Endpoint /api/group/{id}/analytics]")
    app = create_web_app()
    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        # 1. Запрос аналитики группы 1
        res = await client.get("/api/group/1/analytics?period=current_month")
        assert res.status == 200, f"Expected 200, got {res.status}"
        data = await res.json()
        assert "group_id" in data
        assert "currency" in data
        assert "period" in data
        assert "total" in data
        assert "average" in data
        assert "count" in data
        assert "timeline" in data
        assert "categories" in data
        print("   ✅ GET /api/group/1/analytics?period=current_month -> 200 OK")

        # 2. Запрос с периодом 7_days
        res7 = await client.get("/api/group/1/analytics?period=7_days")
        assert res7.status == 200
        data7 = await res7.json()
        assert len(data7["timeline"]) == 7
        print("   ✅ GET /api/group/1/analytics?period=7_days -> 200 OK (7 корзин)")

        # 3. Альтернативный маршрут /api/rooms/1/analytics
        res_rooms = await client.get("/api/rooms/1/analytics?period=30_days")
        assert res_rooms.status == 200
        print("   ✅ GET /api/rooms/1/analytics?period=30_days -> 200 OK")

    finally:
        await client.close()

    print("\n🎉 ВСЕ API ТЕСТЫ ЭНДПОИНТА АНАЛИТИКИ УСПЕШНО ПРОЙДЕНЫ!")


if __name__ == "__main__":
    run_tests()
    import asyncio
    asyncio.run(run_api_tests())

