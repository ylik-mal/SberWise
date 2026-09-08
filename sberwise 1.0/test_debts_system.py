# test_debts_system.py
"""
Комплексный набор тестов для Системы Долгов (Debts System) в СберСплит:
1. Автоматическое создание долгов при совместной покупке (сплит на N участников)
2. Отсутствие долга плательщика самому себе (0 self-debts)
3. Идемпотентность создания долгов по расходу
4. Ручное создание долгов (включая внешних участников без TG ID)
5. Частичное погашение долга (статус partially_paid, логирование в debt_payments)
6. Полное погашение в 1 клик (статус paid, остановка напоминаний)
7. Отмена долга (статус cancelled)
8. Строгая мультичатовая изоляция (данные групп никогда не смешиваются)
9. Безопасность доступа (is_user_group_member)
10. Планировщик напоминаний и расчет интервалов
11. Pre-due предупреждение за 24 часа и расчет просрочки (overdue)
"""

import os
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.getcwd())

import database
from database import (
    init_db,
    get_or_create_user,
    get_or_create_group,
    add_member_to_group,
    add_expense,
    create_debt,
    get_debt_by_id,
    get_group_debts,
    add_debt_payment,
    mark_debt_paid,
    cancel_debt,
    get_debts_summary,
    get_pending_debt_reminders,
    update_debt_reminder_schedule,
    calculate_next_reminder,
    is_user_group_member,
)


class TestDebtsSystem(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_debts_{self._testMethodName}.db"
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

        self.orig_get_db = database.get_db
        def make_conn():
            c = sqlite3.connect(self.db_path)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys = ON")
            return c

        database.get_db = make_conn
        init_db()

        self.conn = database.get_db()

        # Setup test groups & users
        self.group1 = get_or_create_group(self.conn, chat_id=-1001, name="Семья")
        self.group2 = get_or_create_group(self.conn, chat_id=-1002, name="Друзья")

        self.user_a = get_or_create_user(self.conn, telegram_id=101, username="usera", display_name="Алиса")
        self.user_b = get_or_create_user(self.conn, telegram_id=102, username="userb", display_name="Борис")
        self.user_c = get_or_create_user(self.conn, telegram_id=103, username="userc", display_name="Виктор")
        self.outsider = get_or_create_user(self.conn, telegram_id=999, username="outsider", display_name="Чужой")

        # Group 1 members: A, B, C
        add_member_to_group(self.conn, self.group1["id"], self.user_a["id"])
        add_member_to_group(self.conn, self.group1["id"], self.user_b["id"])
        add_member_to_group(self.conn, self.group1["id"], self.user_c["id"])

        # Group 2 members: A, C
        add_member_to_group(self.conn, self.group2["id"], self.user_a["id"])
        add_member_to_group(self.conn, self.group2["id"], self.user_c["id"])

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass

        database.get_db = self.orig_get_db
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_01_auto_debt_creation_from_expense(self):
        """1. Автоматическое создание долгов при совместной покупке на N участников."""
        expense_id = add_expense(
            conn=self.conn,
            group_id=self.group1["id"],
            payer_id=self.user_a["id"],
            amount=3000.0,
            description="Ужин на троих",
            category="☕ Кафе",
            split_user_ids=[self.user_a["id"], self.user_b["id"], self.user_c["id"]],
        )
        self.assertIsNotNone(expense_id)

        debts = get_group_debts(self.conn, self.group1["id"], filter_tab="all")
        self.assertEqual(len(debts), 2, "Должно быть ровно 2 долга (Борис и Виктор должны Алисе)")

        for d in debts:
            self.assertNotEqual(d["creditor_user_id"], d["debtor_user_id"], "Плательщик не должен иметь долг перед собой")
            self.assertEqual(d["creditor_user_id"], self.user_a["id"], "Кредитор должен быть Алиса")
            self.assertEqual(d["remaining_amount"], 1000.0, "Каждый должен ровно по 1000 руб")
            self.assertEqual(d["original_amount"], 1000.0)
            self.assertEqual(d["status"], "active")
            self.assertEqual(d["expense_id"], expense_id)

        # Идемпотентность
        debts_after = get_group_debts(self.conn, self.group1["id"], filter_tab="all")
        self.assertEqual(len(debts_after), 2)

    def test_02_manual_debt_and_external_member(self):
        """2. Ручное создание долгов, включая внешнего человека без Telegram ID."""
        debt1 = create_debt(
            conn=self.conn,
            group_id=self.group1["id"],
            creditor_user_id=self.user_b["id"],
            creditor_name="Борис",
            debtor_user_id=self.user_c["id"],
            debtor_name="Виктор",
            amount=500.0,
            description="Такси из аэропорта",
            notification_frequency="daily",
            created_by_user_id=self.user_b["id"],
        )
        self.assertEqual(debt1["original_amount"], 500.0)
        self.assertEqual(debt1["remaining_amount"], 500.0)
        self.assertEqual(debt1["status"], "active")

        # Внешний должник (debtor_user_id = None)
        debt_ext = create_debt(
            conn=self.conn,
            group_id=self.group1["id"],
            creditor_user_id=self.user_a["id"],
            creditor_name="Алиса",
            debtor_user_id=None,
            debtor_name="Иван Не_в_Телеграм",
            amount=1200.0,
            description="Подарок",
            notification_frequency="none",
            created_by_user_id=self.user_a["id"],
        )
        self.assertIsNone(debt_ext["debtor_user_id"])
        self.assertEqual(debt_ext["debtor_name"], "Иван Не_в_Телеграм")

    def test_03_partial_repayment(self):
        """3. Частичное погашение долга (debt_payments, partially_paid)."""
        debt = create_debt(
            conn=self.conn,
            group_id=self.group1["id"],
            creditor_user_id=self.user_a["id"],
            creditor_name="Алиса",
            debtor_user_id=self.user_b["id"],
            debtor_name="Борис",
            amount=1000.0,
            description="Долг",
            created_by_user_id=self.user_a["id"],
        )

        updated_debt = add_debt_payment(
            conn=self.conn,
            debt_id=debt["id"],
            amount=400.0,
            created_by_user_id=self.user_b["id"],
            note="Часть перевела на карту",
        )
        self.assertEqual(updated_debt["remaining_amount"], 600.0)
        self.assertEqual(updated_debt["status"], "partially_paid")
        self.assertEqual(len(updated_debt["payments"]), 1)
        self.assertEqual(updated_debt["payments"][0]["amount"], 400.0)
        self.assertEqual(updated_debt["payments"][0]["note"], "Часть перевела на карту")

    def test_04_full_settlement(self):
        """4. Полное погашение долга в 1 клик (paid, остановка напоминаний)."""
        debt = create_debt(
            conn=self.conn,
            group_id=self.group1["id"],
            creditor_user_id=self.user_a["id"],
            creditor_name="Алиса",
            debtor_user_id=self.user_b["id"],
            debtor_name="Борис",
            amount=800.0,
            description="Кино",
            notification_frequency="daily",
            created_by_user_id=self.user_a["id"],
        )
        self.assertIsNotNone(debt["next_reminder_at"])

        paid_debt = mark_debt_paid(self.conn, debt["id"], user_id=self.user_a["id"])
        self.assertEqual(paid_debt["status"], "paid")
        self.assertEqual(paid_debt["remaining_amount"], 0.0)
        self.assertIsNotNone(paid_debt["paid_at"])
        self.assertIsNone(paid_debt["next_reminder_at"], "Напоминания должны быть отключены после погашения")

    def test_05_cancel_debt(self):
        """5. Отмена долга (status = cancelled)."""
        debt = create_debt(
            conn=self.conn,
            group_id=self.group1["id"],
            creditor_user_id=self.user_a["id"],
            creditor_name="Алиса",
            debtor_user_id=self.user_b["id"],
            debtor_name="Борис",
            amount=300.0,
            description="Ошибочный долг",
            created_by_user_id=self.user_a["id"],
        )
        cancelled = cancel_debt(self.conn, debt["id"], user_id=self.user_a["id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertIsNone(cancelled["next_reminder_at"])

    def test_06_multi_chat_isolation(self):
        """6. Строгая изоляция: долги Группы 1 не видны в Группе 2."""
        create_debt(
            conn=self.conn,
            group_id=self.group1["id"],
            creditor_user_id=self.user_a["id"],
            creditor_name="Алиса",
            debtor_user_id=self.user_c["id"],
            debtor_name="Виктор",
            amount=2500.0,
            description="Группа 1 аренда",
            created_by_user_id=self.user_a["id"],
        )

        create_debt(
            conn=self.conn,
            group_id=self.group2["id"],
            creditor_user_id=self.user_c["id"],
            creditor_name="Виктор",
            debtor_user_id=self.user_a["id"],
            debtor_name="Алиса",
            amount=700.0,
            description="Группа 2 бензин",
            created_by_user_id=self.user_c["id"],
        )

        g1_debts = get_group_debts(self.conn, self.group1["id"], filter_tab="all")
        self.assertEqual(len(g1_debts), 1)
        self.assertEqual(g1_debts[0]["description"], "Группа 1 аренда")

        g1_summary_a = get_debts_summary(self.conn, self.group1["id"], user_id=self.user_a["id"])
        self.assertEqual(g1_summary_a["totalOwedToMe"], 2500.0)
        self.assertEqual(g1_summary_a["totalIOwe"], 0.0)

        g2_debts = get_group_debts(self.conn, self.group2["id"], filter_tab="all")
        self.assertEqual(len(g2_debts), 1)
        self.assertEqual(g2_debts[0]["description"], "Группа 2 бензин")

        g2_summary_a = get_debts_summary(self.conn, self.group2["id"], user_id=self.user_a["id"])
        self.assertEqual(g2_summary_a["totalOwedToMe"], 0.0)
        self.assertEqual(g2_summary_a["totalIOwe"], 700.0)

    def test_07_security_membership(self):
        """7. Проверка прав доступа is_user_group_member."""
        self.assertTrue(is_user_group_member(self.conn, self.group1["id"], self.user_a["id"]))
        self.assertTrue(is_user_group_member(self.conn, self.group1["id"], self.user_b["id"]))
        self.assertFalse(is_user_group_member(self.conn, self.group2["id"], self.user_b["id"]))
        self.assertFalse(is_user_group_member(self.conn, self.group1["id"], self.outsider["id"]))
        self.assertFalse(is_user_group_member(self.conn, self.group2["id"], self.outsider["id"]))

    def test_08_reminders_and_overdue(self):
        """8. Расписание напоминаний, pre-due проверка и расчет просрочки."""
        now = datetime.now()

        next_daily = calculate_next_reminder("daily", now)
        self.assertIsNotNone(next_daily)
        dt_daily = datetime.strptime(next_daily, "%Y-%m-%d %H:%M:%S")
        self.assertAlmostEqual((dt_daily - now).total_seconds(), 86400, delta=10)

        next_custom = calculate_next_reminder("custom", now, custom_hours=6)
        self.assertIsNotNone(next_custom)
        dt_custom = datetime.strptime(next_custom, "%Y-%m-%d %H:%M:%S")
        self.assertAlmostEqual((dt_custom - now).total_seconds(), 21600, delta=10)

        # 1. Тест просроченного долга
        past_date = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        debt = create_debt(
            conn=self.conn,
            group_id=self.group1["id"],
            creditor_user_id=self.user_a["id"],
            creditor_name="Алиса",
            debtor_user_id=self.user_b["id"],
            debtor_name="Борис",
            amount=1500.0,
            description="Просроченный обед",
            due_datetime=past_date,
            notification_frequency="daily",
        )

        debts = get_group_debts(self.conn, self.group1["id"], filter_tab="all")
        found = [d for d in debts if d["id"] == debt["id"]][0]
        self.assertTrue(found["is_overdue"])
        self.assertGreaterEqual(found["overdue_days"], 2)

        # 2. Тест долга с наступившим временем напоминания (next_reminder_at <= now)
        past_rem = (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        update_debt_reminder_schedule(self.conn, debt["id"], last_reminder_at=past_rem, next_reminder_at=past_rem)

        pending = get_pending_debt_reminders(self.conn)
        pending_ids = [p["id"] for p in pending]
        self.assertIn(debt["id"], pending_ids)

        # 3. Тест pre-due напоминания (за 24ч до срока)
        pre_due_date = (now + timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        debt_predue = create_debt(
            conn=self.conn,
            group_id=self.group1["id"],
            creditor_user_id=self.user_a["id"],
            creditor_name="Алиса",
            debtor_user_id=self.user_c["id"],
            debtor_name="Виктор",
            amount=2000.0,
            description="Завтра срок",
            due_datetime=pre_due_date,
            notification_frequency="none",
        )
        pending_after = get_pending_debt_reminders(self.conn)
        pending_after_ids = [p["id"] for p in pending_after]
        self.assertIn(debt_predue["id"], pending_after_ids)


if __name__ == "__main__":
    unittest.main()
