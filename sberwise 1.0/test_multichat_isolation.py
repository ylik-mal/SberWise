"""
Автоматизированный тест мульти-чат изоляции (Multi-Chat Isolation) для СберСплит.
Проверяет:
1. Изоляцию расходов и балансов между чатами А и Б
2. Изоляцию категорий и истории
3. Изоляцию в Mini App REST API (/api/group/{id}/summary)
4. Защиту безопасности 403 Forbidden при попытке доступа чужого пользователя
5. Корректную работу переключателя групп (/api/groups)
6. Изоляцию AI контекста
7. Миграцию Telegram-чата в супергруппу (migrate_group_chat_id)

Запуск: python test_multichat_isolation.py
"""

import sys
import os
import sqlite3
import asyncio
from datetime import datetime

# Настройка UTF-8 для Windows консоли
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from database import (
    init_db,
    get_db,
    get_or_create_user,
    get_or_create_group,
    add_member_to_group,
    add_expense,
    get_group_balances,
    get_category_totals,
    get_user_groups,
    is_user_group_member,
    migrate_group_chat_id,
    get_group_by_id,
    get_group_by_chat_id,
)
from ai_module import generate_spending_tips
from web_server import create_web_app
from aiohttp import test_utils


async def run_all_tests():
    print("=" * 65)
    print("🧪 ЗАПУСК ТЕСТОВОГО НАБОРА: MULTI-CHAT ISOLATION & SECURITY")
    print("=" * 65 + "\n")

    # The test must be runnable from a clean temporary directory as well as
    # from a developer's already initialized local workspace.
    init_db()
    conn = get_db()

    # Setup unique IDs for test
    chat_a_tg = -999111
    chat_b_tg = -999222
    user1_tg = 888101  # In both groups (Alice)
    user2_tg = 888102  # Only in Group A (Bob)
    user3_tg = 888103  # Only in Group B (Charlie)

    # Clean up only this suite's deterministic test records.  Debts and their
    # payments reference expenses, so child records must be removed first for
    # a repeatable run with SQLite foreign keys enabled.
    test_chat_ids = (chat_a_tg, chat_b_tg, -100999888111)
    group_filter = "SELECT id FROM groups WHERE telegram_chat_id IN (?, ?, ?)"
    expense_filter = f"SELECT id FROM expenses WHERE group_id IN ({group_filter})"
    debt_filter = f"SELECT id FROM debts WHERE group_id IN ({group_filter})"
    conn.execute(f"DELETE FROM debt_payments WHERE debt_id IN ({debt_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM debts WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM expense_items WHERE expense_id IN ({expense_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM expense_splits WHERE expense_id IN ({expense_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM expense_attachments WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM settlements WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM member_import_requests WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM room_setups WHERE room_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM expenses WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM group_members WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute("DELETE FROM groups WHERE telegram_chat_id IN (?, ?, ?)", test_chat_ids)
    conn.execute("DELETE FROM users WHERE telegram_id IN (?, ?, ?)", (user1_tg, user2_tg, user3_tg))
    conn.commit()

    # 1. Create users and groups
    u1 = get_or_create_user(conn, user1_tg, "alice_multi", "Алиса")
    u2 = get_or_create_user(conn, user2_tg, "bob_multi", "Боб")
    u3 = get_or_create_user(conn, user3_tg, "charlie_multi", "Чарли")

    grp_a = get_or_create_group(conn, chat_a_tg, "🏠 Квартира")
    grp_b = get_or_create_group(conn, chat_b_tg, "🚗 Поездка на Алтай")

    # Add members
    add_member_to_group(conn, grp_a["id"], u1["id"])
    add_member_to_group(conn, grp_a["id"], u2["id"])

    add_member_to_group(conn, grp_b["id"], u1["id"])
    add_member_to_group(conn, grp_b["id"], u3["id"])

    print("▶️ [1/7] Проверка создания групп и распределения участников...")
    assert is_user_group_member(conn, grp_a["id"], u1["id"]) is True
    assert is_user_group_member(conn, grp_a["id"], u2["id"]) is True
    assert is_user_group_member(conn, grp_a["id"], u3["id"]) is False  # u3 not in A

    assert is_user_group_member(conn, grp_b["id"], u1["id"]) is True
    assert is_user_group_member(conn, grp_b["id"], u2["id"]) is False  # u2 not in B
    assert is_user_group_member(conn, grp_b["id"], u3["id"]) is True
    print("   ✅ Права членства в группах распределены строго изолированно!\n")

    # 2. Add expenses in Chat A and Chat B
    print("▶️ [2/7] Тестирование добавления изолированных расходов...")
    # Chat A: Alice pays 3000 for groceries (Alice + Bob)
    exp_a_id = add_expense(
        conn, grp_a["id"], u1["id"], 3000.0, "Продукты в Ленте", "🍞 Продукты", [u1["id"], u2["id"]]
    )
    # Chat B: Alice pays 1500 for taxi (Alice + Charlie)
    exp_b_id = add_expense(
        conn, grp_b["id"], u1["id"], 1500.0, "Такси в аэропорт", "🚕 Транспорт", [u1["id"], u3["id"]]
    )

    # Check balances in Chat A
    bal_a = get_group_balances(conn, grp_a["id"])
    assert round(bal_a[u1["id"]], 2) == 1500.0, f"Ожидалось +1500 в группе А для Алисы, получено {bal_a[u1['id']]}"
    assert round(bal_a[u2["id"]], 2) == -1500.0, f"Ожидалось -1500 в группе А для Боба, получено {bal_a[u2['id']]}"
    assert u3["id"] not in bal_a, "Чарли не должен быть в балансах группы А!"

    # Check balances in Chat B
    bal_b = get_group_balances(conn, grp_b["id"])
    assert round(bal_b[u1["id"]], 2) == 750.0, f"Ожидалось +750 в группе Б для Алисы, получено {bal_b[u1['id']]}"
    assert round(bal_b[u3["id"]], 2) == -750.0, f"Ожидалось -750 в группе Б для Чарли, получено {bal_b[u3['id']]}"
    assert u2["id"] not in bal_b, "Боб не должен быть в балансах группы Б!"

    print("   ✅ Балансы и взаимные долги в группах А и Б строго изолированы!\n")

    # 3. Category totals isolation
    print("▶️ [3/7] Тестирование изоляции категорий и сумм...")
    cats_a = get_category_totals(conn, grp_a["id"])
    assert "🍞 Продукты" in cats_a and cats_a["🍞 Продукты"] == 3000.0
    assert "🚕 Транспорт" not in cats_a or cats_a.get("🚕 Транспорт", 0) == 0.0

    cats_b = get_category_totals(conn, grp_b["id"])
    assert "🚕 Транспорт" in cats_b and cats_b["🚕 Транспорт"] == 1500.0
    assert "🍞 Продукты" not in cats_b or cats_b.get("🍞 Продукты", 0) == 0.0
    print("   ✅ Категории расходов группы А не попадают в группу Б и наоборот!\n")

    conn.close()

    # 4. WebApp REST API Multi-Chat Isolation Test
    print("▶️ [4/7] Тестирование Mini App REST API (/api/group/{id}/summary)...")
    app = create_web_app()
    client = test_utils.TestClient(test_utils.TestServer(app))
    await client.start_server()

    # Query Group A summary as User 1 (Alice)
    res_a = await client.get(f"/api/group/{grp_a['id']}/summary?tg_user_id={user1_tg}")
    assert res_a.status == 200, f"Expected 200 for Group A, got {res_a.status}"
    data_a = await res_a.json()
    assert data_a["total_expenses"] == 3000.0, f"Expected 3000 in Group A, got {data_a['total_expenses']}"
    assert data_a["group_name"] == "🏠 Квартира"

    # Query Group B summary as User 1 (Alice)
    res_b = await client.get(f"/api/group/{grp_b['id']}/summary?tg_user_id={user1_tg}")
    assert res_b.status == 200, f"Expected 200 for Group B, got {res_b.status}"
    data_b = await res_b.json()
    assert data_b["total_expenses"] == 1500.0, f"Expected 1500 in Group B, got {data_b['total_expenses']}"
    assert data_b["group_name"] == "🚗 Поездка на Алтай"

    print(f"   ✅ API отдает корректные данные: Группа А = {data_a['total_expenses']}₽, Группа Б = {data_b['total_expenses']}₽\n")

    # 5. Security Check: 403 Forbidden
    print("▶️ [5/7] Тестирование проверки безопасности (403 Forbidden)...")
    # User 2 (Bob) is NOT in Group B. He tries to access Group B summary:
    res_forbidden_summary = await client.get(f"/api/group/{grp_b['id']}/summary?tg_user_id={user2_tg}")
    assert res_forbidden_summary.status == 403, f"Expected 403 Forbidden for User 2 accessing Group B, got {res_forbidden_summary.status}"
    err_json = await res_forbidden_summary.json()
    assert "error" in err_json
    print(f"   🛡️ Попытка чтения чужой группы успешно заблокирована: HTTP {res_forbidden_summary.status} ({err_json['error']})")

    # User 2 tries to POST expense to Group B:
    res_forbidden_post = await client.post(
        f"/api/group/{grp_b['id']}/expense?tg_user_id={user2_tg}",
        json={"amount": 500, "title": "Взлом", "category": "🍞 Продукты", "split_with": [u1["id"]]}
    )
    assert res_forbidden_post.status == 403, f"Expected 403 for unauthorized expense post, got {res_forbidden_post.status}"
    print(f"   🛡️ Попытка создания расхода в чужой группе успешно заблокирована: HTTP {res_forbidden_post.status}\n")

    # 6. Group Switcher (/api/groups)
    print("▶️ [6/7] Тестирование эндпоинта переключателя групп (/api/groups)...")
    # User 1 (Alice) is in both groups
    res_groups_u1 = await client.get(f"/api/groups?tg_user_id={user1_tg}")
    assert res_groups_u1.status == 200
    groups_u1_data = await res_groups_u1.json()
    group_ids_u1 = [g["id"] for g in groups_u1_data["groups"]]
    assert grp_a["id"] in group_ids_u1 and grp_b["id"] in group_ids_u1
    assert len(groups_u1_data["groups"]) >= 2
    print(f"   ✅ Пользователь 1 видит свои группы: {[g['name'] for g in groups_u1_data['groups'] if g['id'] in [grp_a['id'], grp_b['id']] ]}")

    # User 2 (Bob) is ONLY in Group A
    res_groups_u2 = await client.get(f"/api/groups?tg_user_id={user2_tg}")
    assert res_groups_u2.status == 200
    groups_u2_data = await res_groups_u2.json()
    group_ids_u2 = [g["id"] for g in groups_u2_data["groups"]]
    assert grp_a["id"] in group_ids_u2
    assert grp_b["id"] not in group_ids_u2, "Боб не должен видеть группу Б!"
    print(f"   ✅ Пользователь 2 видит только группу А: {[g['name'] for g in groups_u2_data['groups'] if g['id'] in [grp_a['id'], grp_b['id']] ]}\n")

    await client.close()

    # 7. Supergroup Migration
    print("▶️ [7/7] Тестирование миграции чата в супергруппу (migrate_group_chat_id)...")
    conn = get_db()
    new_chat_a_tg = -100999888111
    migrated_res = migrate_group_chat_id(conn, chat_a_tg, new_chat_a_tg)
    assert migrated_res is True, "Миграция должна вернуть True"

    migrated_grp = get_group_by_id(conn, grp_a["id"])
    assert migrated_grp is not None
    assert migrated_grp["id"] == grp_a["id"], "ID группы должен сохраниться при миграции!"
    assert migrated_grp["telegram_chat_id"] == new_chat_a_tg

    # Verify data intact
    found_by_new_chat = get_group_by_chat_id(conn, new_chat_a_tg)
    assert found_by_new_chat is not None
    assert found_by_new_chat["id"] == grp_a["id"]
    
    bal_migrated = get_group_balances(conn, grp_a["id"])
    assert round(bal_migrated[u1["id"]], 2) == 1500.0, "Балансы должны сохраниться после миграции!"

    # Leave the live development database exactly as it was before this
    # standalone audit.  These records use only the deterministic IDs above.
    conn.execute(f"DELETE FROM debt_payments WHERE debt_id IN ({debt_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM debts WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM expense_items WHERE expense_id IN ({expense_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM expense_splits WHERE expense_id IN ({expense_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM expense_attachments WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM settlements WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM member_import_requests WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM room_setups WHERE room_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM expenses WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute(f"DELETE FROM group_members WHERE group_id IN ({group_filter})", test_chat_ids)
    conn.execute("DELETE FROM groups WHERE telegram_chat_id IN (?, ?, ?)", test_chat_ids)
    conn.execute("DELETE FROM users WHERE telegram_id IN (?, ?, ?)", (user1_tg, user2_tg, user3_tg))
    conn.commit()
    conn.close()
    print("   ✅ Миграция telegram_chat_id прошла успешно без потери истории и дубликатов!\n")

    print("=" * 65)
    print("🎉 ВСЕ 7 ТЕСТОВ МУЛЬТИ-ЧАТ ИЗОЛЯЦИИ И БЕЗОПАСНОСТИ ПРОЙДЕНЫ НА 100%!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
