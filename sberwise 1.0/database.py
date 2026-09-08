"""
Модуль базы данных — чистый sqlite3, без SQLAlchemy.
Работает стабильно на Python 3.13 без greenlet.
"""

import sqlite3
import os
import json
from decimal import Decimal
from datetime import datetime
from typing import Optional
from config import DATABASE_PATH


def get_db() -> sqlite3.Connection:
    """Получить подключение к БД."""
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    # Switching journal mode needs an exclusive lock.  It is configured once
    # during init_db(), not on every bot/WebApp request.
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Создать все таблицы."""
    conn = get_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            display_name TEXT NOT NULL,
            reliability_score REAL DEFAULT 0.5,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_chat_id INTEGER UNIQUE NOT NULL,
            name TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL REFERENCES groups(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            joined_at TEXT DEFAULT (datetime('now')),
            UNIQUE(group_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL REFERENCES groups(id),
            paid_by INTEGER NOT NULL REFERENCES users(id),
            amount REAL NOT NULL,
            description TEXT,
            category TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expense_splits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER NOT NULL REFERENCES expenses(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            share REAL NOT NULL,
            is_settled INTEGER DEFAULT 0,
            settled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL REFERENCES groups(id),
            from_user_id INTEGER NOT NULL REFERENCES users(id),
            to_user_id INTEGER NOT NULL REFERENCES users(id),
            amount REAL NOT NULL,
            client_request_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL REFERENCES groups(id),
            creditor_user_id INTEGER REFERENCES users(id),
            creditor_name TEXT NOT NULL,
            debtor_user_id INTEGER REFERENCES users(id),
            debtor_name TEXT NOT NULL,
            original_amount REAL NOT NULL,
            remaining_amount REAL NOT NULL,
            currency TEXT DEFAULT 'RUB',
            description TEXT,
            expense_id INTEGER REFERENCES expenses(id),
            due_datetime TEXT,
            status TEXT DEFAULT 'active',
            notification_frequency TEXT DEFAULT 'none',
            custom_reminder_interval_hours INTEGER,
            custom_reminder_interval_minutes INTEGER,
            last_reminder_at TEXT,
            next_reminder_at TEXT,
            pre_due_reminder_sent_at TEXT,
            reminder_claimed_at TEXT,
            client_request_id TEXT,
            created_by_user_id INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            paid_at TEXT
        );

        CREATE TABLE IF NOT EXISTS debt_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debt_id INTEGER NOT NULL REFERENCES debts(id),
            amount REAL NOT NULL,
            paid_at TEXT DEFAULT (datetime('now')),
            created_by_user_id INTEGER REFERENCES users(id),
            note TEXT,
            client_request_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expense_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            quantity REAL DEFAULT 1.0,
            unit_price REAL NOT NULL,
            total_amount REAL NOT NULL,
            category TEXT,
            participants_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expense_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            expense_id INTEGER REFERENCES expenses(id) ON DELETE SET NULL,
            file_name TEXT NOT NULL,
            file_path TEXT,
            mime_type TEXT,
            file_size INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS member_import_requests (
            request_id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL REFERENCES groups(id),
            requested_by_user_id INTEGER NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            entity_type TEXT,
            entity_id INTEGER,
            severity TEXT DEFAULT 'info',
            event_key TEXT NOT NULL,
            read_at TEXT,
            telegram_status TEXT DEFAULT 'pending',
            telegram_sent_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, event_key)
        );
        CREATE INDEX IF NOT EXISTS idx_notifications_user_group ON notifications(user_id, group_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS notification_preferences (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            telegram_enabled INTEGER DEFAULT 0,
            in_app_enabled INTEGER DEFAULT 1,
            UNIQUE(user_id, group_id)
        );
        CREATE TABLE IF NOT EXISTS room_setups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            created_by_user_id INTEGER NOT NULL REFERENCES users(id),
            status TEXT DEFAULT 'pending',
            telegram_chat_id INTEGER,
            room_id INTEGER REFERENCES groups(id),
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS room_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            token TEXT NOT NULL UNIQUE,
            created_by_user_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            max_uses INTEGER,
            use_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_room_invites_room ON room_invites(room_id);
        CREATE TABLE IF NOT EXISTS room_invite_delivery_requests (
            request_id INTEGER PRIMARY KEY,
            room_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            requested_by_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'pending',
            invite_token TEXT REFERENCES room_invites(token),
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_room_invite_delivery_requests_user ON room_invite_delivery_requests(requested_by_user_id, status);

        CREATE TABLE IF NOT EXISTS category_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            category TEXT NOT NULL,
            monthly_limit REAL NOT NULL CHECK(monthly_limit > 0),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(group_id, category)
        );

        CREATE TABLE IF NOT EXISTS recurring_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            category TEXT NOT NULL DEFAULT 'Другое',
            frequency TEXT NOT NULL DEFAULT 'monthly',
            next_due_date TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_category_budgets_group ON category_budgets(group_id);
        CREATE INDEX IF NOT EXISTS idx_recurring_expenses_group_active ON recurring_expenses(group_id, active);

        CREATE INDEX IF NOT EXISTS idx_debts_group_status ON debts(group_id, status);
        CREATE INDEX IF NOT EXISTS idx_debts_group_debtor ON debts(group_id, debtor_user_id);
        CREATE INDEX IF NOT EXISTS idx_debts_group_creditor ON debts(group_id, creditor_user_id);
        CREATE INDEX IF NOT EXISTS idx_debts_status_next_rem ON debts(status, next_reminder_at);
        CREATE INDEX IF NOT EXISTS idx_debts_expense_id ON debts(expense_id);
        CREATE INDEX IF NOT EXISTS idx_debts_due_datetime ON debts(due_datetime);
        CREATE INDEX IF NOT EXISTS idx_debt_payments_debt_id ON debt_payments(debt_id);
    """)
    conn.commit()

    # Миграция: столбец budget_limit в groups
    try:
        conn.execute("ALTER TABLE groups ADD COLUMN budget_limit REAL DEFAULT 60000.0")
        conn.commit()
    except Exception:
        pass

    # Миграция: столбец reminder_interval_hours в groups (6-24 часов, 0 = выключено)
    try:
        conn.execute("ALTER TABLE groups ADD COLUMN reminder_interval_hours INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    # Миграция: столбец last_reminder_at в groups (timestamp последнего AI-напоминания)
    try:
        conn.execute("ALTER TABLE groups ADD COLUMN last_reminder_at TEXT")
        conn.commit()
    except Exception:
        pass

    # Миграция: столбец reminder_interval_minutes в groups (любой интервал в минутах)
    try:
        conn.execute("ALTER TABLE groups ADD COLUMN reminder_interval_minutes INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    # Миграция: столбец custom_reminder_interval_minutes в debts
    try:
        conn.execute("ALTER TABLE debts ADD COLUMN custom_reminder_interval_minutes INTEGER")
        conn.commit()
    except Exception:
        pass

    # Миграции: Room поля в groups
    for col, defn in [
        ("type", "TEXT DEFAULT 'long_term'"),
        ("currency", "TEXT DEFAULT 'RUB'"),
        ("settlement_strategy", "TEXT DEFAULT 'min_transfers'"),
        ("status", "TEXT DEFAULT 'active'"),
        ("created_by_user_id", "INTEGER REFERENCES users(id)"),
        ("updated_at", "TEXT"),
        ("settlement_message_id", "INTEGER"),
    ]:
        try:
            conn.execute(f"ALTER TABLE groups ADD COLUMN {col} {defn}")
            conn.commit()
        except Exception:
            pass

    # Миграции: поля в expenses
    for col, defn in [
        ("source_type", "TEXT DEFAULT 'manual'"),
        ("title", "TEXT"),
        ("expense_date", "TEXT"),
        ("currency", "TEXT DEFAULT 'RUB'"),
        ("raw_data", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE expenses ADD COLUMN {col} {defn}")
            conn.commit()
        except Exception:
            pass

    # Миграции: поля в expense_splits
    for col, defn in [
        ("share_type", "TEXT DEFAULT 'equal'"),
        ("share_value", "REAL"),
        ("calculated_amount", "REAL DEFAULT 0.0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE expense_splits ADD COLUMN {col} {defn}")
            conn.commit()
        except Exception:
            pass

    # Миграции: внешние участники в group_members
    for col, defn in [
        ("is_external", "INTEGER DEFAULT 0"),
        ("display_name", "TEXT"),
        ("role", "TEXT DEFAULT 'member'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE group_members ADD COLUMN {col} {defn}")
            conn.commit()
        except Exception:
            pass

    for col, defn in [("access_status", "TEXT DEFAULT 'active'"), ("has_started_bot", "INTEGER DEFAULT 0")]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            conn.commit()
        except Exception:
            pass
    for col, defn in [("status", "TEXT DEFAULT 'active'"), ("telegram_username", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE group_members ADD COLUMN {col} {defn}")
            conn.commit()
        except Exception:
            pass
    try:
        conn.execute("ALTER TABLE expenses ADD COLUMN client_request_id TEXT")
        conn.commit()
    except Exception:
        pass

    # Debt requests and reminder claims must survive concurrent WebApp/bot workers.
    for col, definition in [
        ("client_request_id", "TEXT"),
        ("reminder_claimed_at", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE debts ADD COLUMN {col} {definition}")
            conn.commit()
        except Exception:
            pass
    try:
        conn.execute("ALTER TABLE debt_payments ADD COLUMN client_request_id TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE settlements ADD COLUMN client_request_id TEXT")
        conn.commit()
    except Exception:
        pass
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_debts_client_request ON debts(group_id, created_by_user_id, client_request_id) WHERE client_request_id IS NOT NULL")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_debt_payments_client_request ON debt_payments(debt_id, client_request_id) WHERE client_request_id IS NOT NULL")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_settlements_client_request ON settlements(group_id, from_user_id, to_user_id, client_request_id) WHERE client_request_id IS NOT NULL")
    conn.commit()
    try:
        conn.execute("ALTER TABLE member_import_requests ADD COLUMN completed_at TEXT")
        conn.commit()
    except Exception:
        pass
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_expenses_request_id ON expenses(group_id, paid_by, client_request_id) WHERE client_request_id IS NOT NULL")
    conn.commit()
    try:
        conn.execute("ALTER TABLE room_setups ADD COLUMN invite_link TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE room_setups ADD COLUMN connect_code TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_room_setups_connect_code ON room_setups(connect_code)")
        conn.commit()
    except Exception:
        pass

    conn.close()


def set_group_budget_limit(conn: sqlite3.Connection, group_id: int, limit: float):
    """Установить фиксированный лимит бюджета для группы."""
    try:
        conn.execute("UPDATE groups SET budget_limit = ? WHERE id = ?", (limit, group_id))
        conn.commit()
    except Exception:
        try:
            conn.execute("ALTER TABLE groups ADD COLUMN budget_limit REAL DEFAULT 60000.0")
            conn.commit()
            conn.execute("UPDATE groups SET budget_limit = ? WHERE id = ?", (limit, group_id))
            conn.commit()
        except Exception:
            pass


def get_group_budget_limit(conn: sqlite3.Connection, group_id: int) -> float:
    """Получить установленный лимит бюджета группы (дефолт 60000.0)."""
    try:
        row = conn.execute("SELECT budget_limit FROM groups WHERE id = ?", (group_id,)).fetchone()
        if row and row["budget_limit"] and row["budget_limit"] > 0:
            return float(row["budget_limit"])
    except Exception:
        try:
            conn.execute("ALTER TABLE groups ADD COLUMN budget_limit REAL DEFAULT 60000.0")
            conn.commit()
            row = conn.execute("SELECT budget_limit FROM groups WHERE id = ?", (group_id,)).fetchone()
            if row and row["budget_limit"] and row["budget_limit"] > 0:
                return float(row["budget_limit"])
        except Exception:
            pass
    return 60000.0


def get_category_budgets(conn: sqlite3.Connection, group_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT category, monthly_limit, updated_at FROM category_budgets WHERE group_id = ? ORDER BY category",
        (group_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def set_category_budget(conn: sqlite3.Connection, group_id: int, category: str, monthly_limit: float):
    conn.execute(
        """INSERT INTO category_budgets (group_id, category, monthly_limit, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(group_id, category) DO UPDATE SET monthly_limit = excluded.monthly_limit, updated_at = datetime('now')""",
        (group_id, category, monthly_limit),
    )
    conn.commit()


def get_recurring_expenses(conn: sqlite3.Connection, group_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM recurring_expenses WHERE group_id = ? ORDER BY active DESC, next_due_date IS NULL, next_due_date, id DESC",
        (group_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def create_recurring_expense(conn: sqlite3.Connection, group_id: int, title: str, amount: float, category: str, next_due_date: Optional[str] = None) -> int:
    cur = conn.execute(
        "INSERT INTO recurring_expenses (group_id, title, amount, category, next_due_date) VALUES (?, ?, ?, ?, ?)",
        (group_id, title, amount, category, next_due_date),
    )
    conn.commit()
    return cur.lastrowid


def delete_recurring_expense(conn: sqlite3.Connection, group_id: int, recurring_id: int) -> bool:
    cur = conn.execute("DELETE FROM recurring_expenses WHERE id = ? AND group_id = ?", (recurring_id, group_id))
    conn.commit()
    return cur.rowcount > 0


# ─── CRUD операции ─────────────────────────────────────────────

def get_or_create_user(conn: sqlite3.Connection, telegram_id: int, username: str, display_name: str) -> dict:
    """Получить пользователя или создать нового."""
    row = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    if row:
        return dict(row)
    conn.execute(
        "INSERT INTO users (telegram_id, username, display_name) VALUES (?, ?, ?)",
        (telegram_id, username, display_name),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    return dict(row)


def get_or_create_group(conn: sqlite3.Connection, chat_id: int, name: str) -> dict:
    """Получить группу или создать новую."""
    row = conn.execute("SELECT * FROM groups WHERE telegram_chat_id = ?", (chat_id,)).fetchone()
    if row:
        return dict(row)
    conn.execute(
        "INSERT INTO groups (telegram_chat_id, name) VALUES (?, ?)",
        (chat_id, name),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM groups WHERE telegram_chat_id = ?", (chat_id,)).fetchone()
    return dict(row)


def add_member_to_group(conn: sqlite3.Connection, group_id: int, user_id: int):
    """Добавить участника в группу."""
    try:
        existing_members = get_group_members_users(conn, group_id)
        cursor = conn.execute(
            "INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group_id, user_id),
        )
        conn.commit()
        if cursor.rowcount:
            joined_user = get_user_by_id(conn, user_id)
            joined_name = (joined_user or {}).get("display_name", "Новый участник")
            for member in existing_members:
                create_notification(conn, member["id"], group_id, "member_joined", "Новый участник",
                    f"{joined_name} присоединился к комнате", "member", user_id,
                    event_key=f"member_joined:{group_id}:{user_id}:{member['id']}")
    except sqlite3.IntegrityError:
        pass


class RoomNeedsMoreMembersError(ValueError):
    """Raised when someone tries to create a shared expense in a solo room."""


def require_active_room_members(conn: sqlite3.Connection, group_id: int, minimum: int = 2) -> int:
    """Allow shared expenses only after enough real room members have joined.

    Pending invitations and legacy external contacts do not count: they cannot
    receive a share or a debt notification yet.
    """
    row = conn.execute("""
        SELECT COUNT(*) AS count
        FROM group_members
        WHERE group_id = ?
          AND COALESCE(status, 'active') = 'active'
          AND COALESCE(is_external, 0) = 0
    """, (group_id,)).fetchone()
    count = int(row["count"] or 0)
    if count < minimum:
        raise RoomNeedsMoreMembersError(
            "Для общего расхода в комнате должны быть минимум два активных участника"
        )
    return count


def add_expense(
    conn: sqlite3.Connection,
    group_id: int,
    payer_id: int,
    amount: float,
    description: str,
    category: str,
    split_user_ids: list[int], client_request_id: Optional[str] = None,
) -> int:
    """Добавить расход и разделить между участниками. Возвращает ID расхода и создаёт связанные Debt."""
    require_active_room_members(conn, group_id)
    cursor = conn.execute(
        "INSERT INTO expenses (group_id, paid_by, amount, description, category, client_request_id) VALUES (?, ?, ?, ?, ?, ?)",
        (group_id, payer_id, amount, description, category, client_request_id),
    )
    expense_id = cursor.lastrowid

    share = round(amount / len(split_user_ids), 2) if split_user_ids else amount
    payer = get_user_by_id(conn, payer_id)
    payer_name = payer["display_name"] if payer else f"User#{payer_id}"

    for uid in split_user_ids:
        is_settled = 1 if uid == payer_id else 0
        conn.execute(
            "INSERT INTO expense_splits (expense_id, user_id, share, is_settled) VALUES (?, ?, ?, ?)",
            (expense_id, uid, share, is_settled),
        )

        # Автоматическое создание долга (плательщик не должен сам себе!)
        if uid != payer_id and share > 0:
            debtor = get_user_by_id(conn, uid)
            debtor_name = debtor["display_name"] if debtor else f"User#{uid}"
            # Проверяем идемпотентность
            existing = conn.execute(
                "SELECT id FROM debts WHERE expense_id = ? AND debtor_user_id = ?",
                (expense_id, uid)
            ).fetchone()
            if not existing:
                conn.execute("""
                    INSERT INTO debts (
                        group_id, creditor_user_id, creditor_name,
                        debtor_user_id, debtor_name,
                        original_amount, remaining_amount, currency,
                        description, expense_id, status, created_by_user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'RUB', ?, ?, 'active', ?)
                """, (
                    group_id, payer_id, payer_name,
                    uid, debtor_name,
                    share, share,
                    description or f"Доля за расход: {category}",
                    expense_id, payer_id
                ))

    conn.commit()
    _notify_expense_created(conn, group_id, payer_id, expense_id, description, amount)
    return expense_id


def get_group_balances(conn: sqlite3.Connection, group_id: int) -> dict[int, float]:
    """
    Рассчитать баланс каждого участника в группе.
    Положительный = ему должны, отрицательный = он должен.
    """
    # Сколько каждый заплатил
    paid_rows = conn.execute(
        "SELECT paid_by, SUM(amount) as total FROM expenses WHERE group_id = ? GROUP BY paid_by",
        (group_id,),
    ).fetchall()
    paid_map = {row["paid_by"]: row["total"] for row in paid_rows}

    # Сколько каждый должен (его доля)
    owed_rows = conn.execute("""
        SELECT es.user_id, SUM(es.share) as total
        FROM expense_splits es
        JOIN expenses e ON e.id = es.expense_id
        WHERE e.group_id = ?
        GROUP BY es.user_id
    """, (group_id,)).fetchall()
    owed_map = {row["user_id"]: row["total"] for row in owed_rows}

    # Погашения отправленные
    sent_rows = conn.execute(
        "SELECT from_user_id, SUM(amount) as total FROM settlements WHERE group_id = ? GROUP BY from_user_id",
        (group_id,),
    ).fetchall()
    sent_map = {row["from_user_id"]: row["total"] for row in sent_rows}

    # Погашения полученные
    recv_rows = conn.execute(
        "SELECT to_user_id, SUM(amount) as total FROM settlements WHERE group_id = ? GROUP BY to_user_id",
        (group_id,),
    ).fetchall()
    recv_map = {row["to_user_id"]: row["total"] for row in recv_rows}

    all_user_ids = set(paid_map) | set(owed_map) | set(sent_map) | set(recv_map)

    balances = {}
    for uid in all_user_ids:
        paid = paid_map.get(uid, 0.0)
        owed = owed_map.get(uid, 0.0)
        sent = sent_map.get(uid, 0.0)
        recv = recv_map.get(uid, 0.0)
        balances[uid] = round((paid - owed) + sent - recv, 2)

    return balances


def add_settlement(conn: sqlite3.Connection, group_id: int, from_user_id: int, to_user_id: int, amount: float, client_request_id: Optional[str] = None):
    """Записать погашение долга."""
    if client_request_id:
        existing = conn.execute("SELECT id FROM settlements WHERE group_id = ? AND from_user_id = ? AND to_user_id = ? AND client_request_id = ?", (group_id, from_user_id, to_user_id, client_request_id)).fetchone()
        if existing:
            return existing["id"]
    cursor = conn.execute(
        "INSERT INTO settlements (group_id, from_user_id, to_user_id, amount, client_request_id) VALUES (?, ?, ?, ?, ?)",
        (group_id, from_user_id, to_user_id, amount, client_request_id),
    )
    conn.commit()
    sender = get_user_by_id(conn, from_user_id) or {}
    create_notification(conn, to_user_id, group_id, "settlement_created", "Перевод отмечен",
        f"{sender.get('display_name', 'Участник')} отметил перевод вам на {amount:,.0f} ₽",
        "settlement", cursor.lastrowid, event_key=f"settlement_created:{cursor.lastrowid}:{to_user_id}")
    return cursor.lastrowid


def get_group_expenses(conn: sqlite3.Connection, group_id: int, limit: int = 10) -> list[dict]:
    """Получить последние расходы группы."""
    rows = conn.execute(
        "SELECT * FROM expenses WHERE group_id = ? ORDER BY created_at DESC LIMIT ?",
        (group_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_category_totals(conn: sqlite3.Connection, group_id: int) -> dict[str, float]:
    """Получить суммы по категориям."""
    rows = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE group_id = ? GROUP BY category",
        (group_id,),
    ).fetchall()
    return {row["category"]: row["total"] for row in rows}


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[dict]:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_telegram_id(conn: sqlite3.Connection, telegram_id: int) -> Optional[dict]:
    row = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    return dict(row) if row else None


def get_group_members_users(conn: sqlite3.Connection, group_id: int) -> list[dict]:
    """Получить всех пользователей в группе."""
    rows = conn.execute("""
        SELECT u.*, gm.is_external, gm.role, gm.status, gm.telegram_username, COALESCE(gm.display_name, u.display_name) AS member_display_name
        FROM users u
        JOIN group_members gm ON gm.user_id = u.id
        WHERE gm.group_id = ?
    """, (group_id,)).fetchall()
    return [dict(r) for r in rows]


def create_notification(conn, user_id, group_id, notification_type, title, body="", entity_type=None, entity_id=None, severity="info", event_key=None):
    """Persist one room-scoped in-app event. The event key makes retries idempotent."""
    if not user_id or not group_id:
        return None
    key = event_key or f"{notification_type}:{entity_type or ''}:{entity_id or ''}:{title}"
    conn.execute("""INSERT OR IGNORE INTO notifications
        (user_id, group_id, type, title, body, entity_type, entity_id, severity, event_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (int(user_id), int(group_id), notification_type, title, body, entity_type, entity_id, severity, key))
    conn.commit()
    row = conn.execute("SELECT * FROM notifications WHERE user_id = ? AND event_key = ?", (int(user_id), key)).fetchone()
    return dict(row) if row else None


def _notify_expense_created(conn, group_id, payer_id, expense_id, description, amount):
    """Expenses belong in History; the notification centre is reserved for personal settlements.

    A room expense is visible to everyone in the shared history, but it is not a
    personal action by itself. Sending it to every participant made the centre
    look like a global room feed and hid the important debt reminders.
    """
    return None


def get_notifications(conn, user_id, group_id, unread_only=False, limit=50):
    # Hide previously created room-feed events as well. The table remains intact
    # for auditability, while the user-facing centre shows only personal events.
    room_feed_types = ("expense_created", "member_joined", "budget_80", "budget_100")
    placeholders = ", ".join("?" for _ in room_feed_types)
    query = f"SELECT * FROM notifications WHERE user_id = ? AND group_id = ? AND type NOT IN ({placeholders})"
    params = [int(user_id), int(group_id), *room_feed_types]
    if unread_only:
        query += " AND read_at IS NULL"
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(int(limit))
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def mark_notification_read(conn, notification_id, user_id, group_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("UPDATE notifications SET read_at = COALESCE(read_at, ?) WHERE id = ? AND user_id = ? AND group_id = ?", (now, int(notification_id), int(user_id), int(group_id)))
    conn.commit()
    return cur.rowcount > 0


def mark_all_notifications_read(conn, user_id, group_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE notifications SET read_at = COALESCE(read_at, ?) WHERE user_id = ? AND group_id = ?", (now, int(user_id), int(group_id)))
    conn.commit()


def get_user_expense_count(conn: sqlite3.Connection, user_id: int, group_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM expenses WHERE paid_by = ? AND group_id = ?",
        (user_id, group_id),
    ).fetchone()
    return row["cnt"] if row else 0


def simplify_debts(balances: dict[int, float]) -> list[tuple[int, int, float]]:
    """
    Упростить долги — минимизировать количество транзакций.
    Возвращает список (from_id, to_id, amount).
    """
    debtors = []
    creditors = []

    for uid, balance in balances.items():
        if balance < -0.01:
            debtors.append([uid, -balance])
        elif balance > 0.01:
            creditors.append([uid, balance])

    debtors.sort(key=lambda x: -x[1])
    creditors.sort(key=lambda x: -x[1])

    transactions = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor_id, debt = debtors[i]
        creditor_id, credit = creditors[j]

        transfer = min(debt, credit)
        if transfer > 0.01:
            transactions.append((debtor_id, creditor_id, round(transfer, 2)))

        debtors[i][1] -= transfer
        creditors[j][1] -= transfer

        if debtors[i][1] < 0.01:
            i += 1
        if creditors[j][1] < 0.01:
            j += 1

    return transactions


# ─── AI Reminder настройки ─────────────────────────────────────

def set_reminder_interval(conn: sqlite3.Connection, group_id: int, minutes: int):
    """Установить интервал AI-напоминаний в минутах (0 = выключено, любое число минут: 10, 30, 60, 1440...)."""
    hours = max(1, minutes // 60) if minutes >= 60 else (1 if minutes > 0 else 0)
    try:
        conn.execute(
            "UPDATE groups SET reminder_interval_minutes = ?, reminder_interval_hours = ? WHERE id = ?",
            (minutes, hours, group_id),
        )
        conn.commit()
    except Exception:
        for col, default in [
            ("reminder_interval_minutes", "INTEGER DEFAULT 0"),
            ("reminder_interval_hours", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE groups ADD COLUMN {col} {default}")
                conn.commit()
            except Exception:
                pass
        try:
            conn.execute(
                "UPDATE groups SET reminder_interval_minutes = ?, reminder_interval_hours = ? WHERE id = ?",
                (minutes, hours, group_id),
            )
            conn.commit()
        except Exception:
            pass


def get_reminder_interval(conn: sqlite3.Connection, group_id: int) -> int:
    """Получить текущий интервал AI-напоминаний в минутах (0 = выключено)."""
    try:
        row = conn.execute(
            "SELECT reminder_interval_minutes, reminder_interval_hours FROM groups WHERE id = ?",
            (group_id,),
        ).fetchone()
        if row:
            if "reminder_interval_minutes" in row.keys() and row["reminder_interval_minutes"] is not None and row["reminder_interval_minutes"] > 0:
                return int(row["reminder_interval_minutes"])
            if row["reminder_interval_hours"] and row["reminder_interval_hours"] > 0:
                return int(row["reminder_interval_hours"]) * 60
    except Exception:
        try:
            row = conn.execute("SELECT reminder_interval_hours FROM groups WHERE id = ?", (group_id,)).fetchone()
            if row and row["reminder_interval_hours"]:
                return int(row["reminder_interval_hours"]) * 60
        except Exception:
            pass
    return 0


def update_last_reminder_at(conn: sqlite3.Connection, group_id: int):
    """Обновить метку времени последнего AI-напоминания."""
    now = datetime.now().isoformat()
    try:
        conn.execute("UPDATE groups SET last_reminder_at = ? WHERE id = ?", (now, group_id))
        conn.commit()
    except Exception:
        try:
            conn.execute("ALTER TABLE groups ADD COLUMN last_reminder_at TEXT")
            conn.commit()
            conn.execute("UPDATE groups SET last_reminder_at = ? WHERE id = ?", (now, group_id))
            conn.commit()
        except Exception:
            pass


def get_all_groups_with_reminders(conn: sqlite3.Connection) -> list[dict]:
    """Получить все группы с активными AI-напоминаниями (с интервалом в минутах)."""
    try:
        rows = conn.execute(
            "SELECT id, telegram_chat_id, name, "
            "COALESCE(NULLIF(reminder_interval_minutes, 0), reminder_interval_hours * 60, 0) as reminder_interval_minutes, "
            "reminder_interval_hours, last_reminder_at "
            "FROM groups WHERE reminder_interval_minutes > 0 OR reminder_interval_hours > 0"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        # Мигрируем недостающие столбцы
        for col, default in [
            ("reminder_interval_minutes", "INTEGER DEFAULT 0"),
            ("reminder_interval_hours", "INTEGER DEFAULT 0"),
            ("last_reminder_at", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE groups ADD COLUMN {col} {default}")
                conn.commit()
            except Exception:
                pass
        try:
            rows = conn.execute(
                "SELECT id, telegram_chat_id, name, "
                "COALESCE(NULLIF(reminder_interval_minutes, 0), reminder_interval_hours * 60, 0) as reminder_interval_minutes, "
                "reminder_interval_hours, last_reminder_at "
                "FROM groups WHERE reminder_interval_minutes > 0 OR reminder_interval_hours > 0"
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []


def reset_group_expenses(conn: sqlite3.Connection, group_id: int, only_current_month: bool = True) -> int:
    """
    Обнулить траты и взаиморасчёты группы.
    only_current_month=True удаляет траты за текущий месяц (default).
    only_current_month=False удаляет все траты группы за всё время.
    Возвращает количество удалённых записей о расходах.
    """
    if only_current_month:
        month_str = datetime.now().strftime("%Y-%m")
        rows = conn.execute(
            "SELECT id FROM expenses WHERE group_id = ? AND strftime('%Y-%m', created_at) = ?",
            (group_id, month_str),
        ).fetchall()
        expense_ids = [r["id"] for r in rows]
        if not expense_ids:
            # Даже если нет расходов, удаляем возможные settlement за этот месяц
            conn.execute(
                "DELETE FROM settlements WHERE group_id = ? AND strftime('%Y-%m', created_at) = ?",
                (group_id, month_str),
            )
            conn.commit()
            return 0

        placeholders = ",".join("?" * len(expense_ids))
        conn.execute(f"DELETE FROM expense_splits WHERE expense_id IN ({placeholders})", expense_ids)
        conn.execute(f"DELETE FROM expenses WHERE id IN ({placeholders})", expense_ids)
        conn.execute(
            "DELETE FROM settlements WHERE group_id = ? AND strftime('%Y-%m', created_at) = ?",
            (group_id, month_str),
        )
        conn.commit()
        return len(expense_ids)
    else:
        rows = conn.execute("SELECT id FROM expenses WHERE group_id = ?", (group_id,)).fetchall()
        expense_ids = [r["id"] for r in rows]
        if expense_ids:
            placeholders = ",".join("?" * len(expense_ids))
            conn.execute(f"DELETE FROM expense_splits WHERE expense_id IN ({placeholders})", expense_ids)
            conn.execute("DELETE FROM expenses WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM settlements WHERE group_id = ?", (group_id,))
        conn.commit()
        return len(expense_ids)


# ─── Multi-Chat Group Management ───────────────────────────────

def get_user_groups(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    """
    Получить список всех групп (бюджетов чатов), в которых состоит пользователь.
    Включает общую сумму расходов группы и количество участников.
    """
    rows = conn.execute("""
        SELECT g.id, g.telegram_chat_id, g.name, g.budget_limit, g.created_at, g.created_by_user_id,
               COALESCE(gm.role, 'member') as member_role,
               COALESCE(g.type, 'long_term') as type,
               COALESCE(g.currency, 'RUB') as currency,
               COALESCE((SELECT SUM(amount) FROM expenses WHERE group_id = g.id), 0.0) as total_expenses,
               (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as members_count
        FROM groups g
        JOIN group_members gm ON gm.group_id = g.id
        WHERE gm.user_id = ?
        ORDER BY g.id ASC
    """, (user_id,)).fetchall()
    return [dict(r) for r in rows]


def is_user_group_member(conn: sqlite3.Connection, group_id: int, user_id: int) -> bool:
    """Проверить, состоит ли пользователь в указанной группе."""
    row = conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ).fetchone()
    return bool(row)


def get_group_by_id(conn: sqlite3.Connection, group_id: int) -> Optional[dict]:
    """Получить группу по внутреннему ID."""
    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    return dict(row) if row else None


def get_group_by_chat_id(conn: sqlite3.Connection, chat_id: int) -> Optional[dict]:
    """Получить группу по telegram_chat_id."""
    row = conn.execute("SELECT * FROM groups WHERE telegram_chat_id = ?", (chat_id,)).fetchone()
    return dict(row) if row else None


def set_group_settlement_message_id(conn: sqlite3.Connection, group_id: int, message_id: int) -> None:
    """Remember the single Telegram summary message that should be updated."""
    conn.execute("UPDATE groups SET settlement_message_id = ? WHERE id = ?", (int(message_id), int(group_id)))
    conn.commit()


def migrate_group_chat_id(conn: sqlite3.Connection, old_chat_id: int, new_chat_id: int) -> bool:
    """
    Обновить telegram_chat_id группы при миграции группы Telegram в супергруппу.
    Предотвращает создание пустых дубликатов групп.
    """
    # Проверяем, существует ли группа со старым chat_id
    old_group = get_group_by_chat_id(conn, old_chat_id)
    if not old_group:
        return False

    # Проверяем, нет ли уже группы с новым chat_id (если бот уже видел супергруппу)
    new_group = get_group_by_chat_id(conn, new_chat_id)
    if new_group:
        # Объединяем: переносим участников и расходы в old_group, удаляем new_group
        conn.execute("UPDATE expenses SET group_id = ? WHERE group_id = ?", (old_group["id"], new_group["id"]))
        conn.execute("UPDATE settlements SET group_id = ? WHERE group_id = ?", (old_group["id"], new_group["id"]))
        conn.execute("INSERT OR IGNORE INTO group_members (group_id, user_id) SELECT ?, user_id FROM group_members WHERE group_id = ?", (old_group["id"], new_group["id"]))
        conn.execute("DELETE FROM group_members WHERE group_id = ?", (new_group["id"],))
        conn.execute("DELETE FROM groups WHERE id = ?", (new_group["id"],))

    conn.execute(
        "UPDATE groups SET telegram_chat_id = ? WHERE id = ?",
        (new_chat_id, old_group["id"]),
    )
    conn.commit()
    return True




# ─── СИСТЕМА ДОЛГОВ (DEBT MANAGEMENT SYSTEM) ─────────────────

from datetime import timedelta

def calculate_next_reminder(
    frequency: str,
    from_dt: datetime,
    custom_minutes: Optional[int] = None,
    custom_hours: Optional[int] = None,
) -> Optional[str]:
    """
    Расчёт следующего времени напоминания:
    - 10_min: +10 минут
    - 30_min: +30 минут
    - 3_times_a_day: 09:00, 14:00, 20:00 (следующий доступный слот)
    - daily: +24 часа
    - every_3_days: +72 часа
    - weekly: +7 дней
    - custom: +custom_minutes минут (или custom_hours часов)
    """
    if frequency == "none":
        return None

    if frequency == "10_min":
        nxt = from_dt + timedelta(minutes=10)
        return nxt.strftime("%Y-%m-%d %H:%M:%S")

    elif frequency == "30_min":
        nxt = from_dt + timedelta(minutes=30)
        return nxt.strftime("%Y-%m-%d %H:%M:%S")

    elif frequency == "3_times_a_day":
        slots = [9, 14, 20]
        cur_hour = from_dt.hour
        next_slot = None
        for s in slots:
            if s > cur_hour:
                next_slot = s
                break
        if next_slot is not None:
            nxt = from_dt.replace(hour=next_slot, minute=0, second=0, microsecond=0)
        else:
            tomorrow = from_dt + timedelta(days=1)
            nxt = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        return nxt.strftime("%Y-%m-%d %H:%M:%S")

    elif frequency == "daily":
        nxt = from_dt + timedelta(days=1)
        return nxt.strftime("%Y-%m-%d %H:%M:%S")

    elif frequency == "every_3_days":
        nxt = from_dt + timedelta(days=3)
        return nxt.strftime("%Y-%m-%d %H:%M:%S")

    elif frequency == "weekly":
        nxt = from_dt + timedelta(days=7)
        return nxt.strftime("%Y-%m-%d %H:%M:%S")

    elif frequency == "custom":
        if custom_minutes and custom_minutes > 0:
            nxt = from_dt + timedelta(minutes=custom_minutes)
            return nxt.strftime("%Y-%m-%d %H:%M:%S")
        elif custom_hours and custom_hours > 0:
            nxt = from_dt + timedelta(hours=custom_hours)
            return nxt.strftime("%Y-%m-%d %H:%M:%S")

    return None


def create_debt(
    conn: sqlite3.Connection,
    group_id: int,
    creditor_user_id: Optional[int],
    creditor_name: str,
    debtor_user_id: Optional[int],
    debtor_name: str,
    amount: float,
    description: str = "",
    due_datetime: Optional[str] = None,
    notification_frequency: str = "none",
    custom_reminder_interval_hours: Optional[int] = None,
    custom_reminder_interval_minutes: Optional[int] = None,
    expense_id: Optional[int] = None,
    created_by_user_id: Optional[int] = None,
    client_request_id: Optional[str] = None,
) -> dict:
    """Создать новый долг вручную или автоматически с поддержкой интервалов в минутах."""
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Синхронизируем минуты и часы
    if custom_reminder_interval_minutes and not custom_reminder_interval_hours:
        custom_reminder_interval_hours = max(1, custom_reminder_interval_minutes // 60)
    elif custom_reminder_interval_hours and not custom_reminder_interval_minutes:
        custom_reminder_interval_minutes = custom_reminder_interval_hours * 60

    next_rem = None
    if notification_frequency != "none":
        if due_datetime:
            try:
                due_dt = datetime.strptime(due_datetime.replace("T", " "), "%Y-%m-%d %H:%M:%S")
                if due_dt > now:
                    next_rem = due_datetime.replace("T", " ")
                else:
                    next_rem = calculate_next_reminder(
                        notification_frequency,
                        now,
                        custom_minutes=custom_reminder_interval_minutes,
                        custom_hours=custom_reminder_interval_hours,
                    )
            except Exception:
                next_rem = calculate_next_reminder(
                    notification_frequency,
                    now,
                    custom_minutes=custom_reminder_interval_minutes,
                    custom_hours=custom_reminder_interval_hours,
                )
        else:
            next_rem = calculate_next_reminder(
                notification_frequency,
                now,
                custom_minutes=custom_reminder_interval_minutes,
                custom_hours=custom_reminder_interval_hours,
            )

    # Убеждаемся, что колонка custom_reminder_interval_minutes существует
    try:
        conn.execute("ALTER TABLE debts ADD COLUMN custom_reminder_interval_minutes INTEGER")
        conn.commit()
    except Exception:
        pass

    cursor = conn.execute("""
        INSERT INTO debts (
            group_id, creditor_user_id, creditor_name,
            debtor_user_id, debtor_name,
            original_amount, remaining_amount, currency,
            description, expense_id, due_datetime,
            status, notification_frequency, custom_reminder_interval_hours,
            custom_reminder_interval_minutes,
            next_reminder_at, created_by_user_id, client_request_id,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'RUB', ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        group_id, creditor_user_id, creditor_name.strip(),
        debtor_user_id, debtor_name.strip(),
        round(amount, 2), round(amount, 2),
        description.strip(), expense_id,
        due_datetime.replace("T", " ") if due_datetime else None,
        notification_frequency, custom_reminder_interval_hours,
        custom_reminder_interval_minutes,
        next_rem, created_by_user_id, client_request_id,
        now_str, now_str
    ))
    conn.commit()
    debt_id = cursor.lastrowid
    return get_debt_by_id(conn, debt_id, group_id)


def get_debt_by_id(conn: sqlite3.Connection, debt_id: int, group_id: Optional[int] = None) -> Optional[dict]:
    """Получить долг по ID с деталями и историей платежей."""
    query = "SELECT * FROM debts WHERE id = ?"
    params = [debt_id]
    if group_id is not None:
        query += " AND group_id = ?"
        params.append(group_id)

    row = conn.execute(query, params).fetchone()
    if not row:
        return None

    debt = dict(row)
    payments_rows = conn.execute(
        "SELECT * FROM debt_payments WHERE debt_id = ? ORDER BY paid_at DESC, id DESC",
        (debt_id,)
    ).fetchall()
    debt["payments"] = [dict(p) for p in payments_rows]

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    debt["is_overdue"] = bool(
        debt["due_datetime"] and
        debt["due_datetime"] < now_str and
        debt["status"] in ("active", "partially_paid") and
        debt["remaining_amount"] > 0
    )
    if debt["is_overdue"]:
        try:
            due_dt = datetime.strptime(debt["due_datetime"], "%Y-%m-%d %H:%M:%S")
            diff_days = (datetime.now() - due_dt).days
            debt["overdue_days"] = max(1, diff_days)
        except Exception:
            debt["overdue_days"] = 1
    else:
        debt["overdue_days"] = 0

    return debt


def get_group_debts(
    conn: sqlite3.Connection,
    group_id: int,
    user_id: Optional[int] = None,
    filter_tab: str = "all",  # "i_owe", "owed_to_me", "all"
    status: Optional[str] = None,
) -> list[dict]:
    """
    Получить список долгов группы с фильтрацией:
    - filter_tab = 'i_owe': должник = user_id
    - filter_tab = 'owed_to_me': кредитор = user_id
    - filter_tab = 'all': все долги группы
    """
    query = "SELECT * FROM debts WHERE group_id = ?"
    params = [group_id]

    if status:
        query += " AND status = ?"
        params.append(status)

    if user_id:
        if filter_tab == "i_owe":
            query += " AND debtor_user_id = ?"
            params.append(user_id)
        elif filter_tab == "owed_to_me":
            query += " AND creditor_user_id = ?"
            params.append(user_id)

    query += " ORDER BY status ASC, due_datetime ASC, id DESC"
    rows = conn.execute(query, params).fetchall()

    debts = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in rows:
        d = dict(r)
        d["is_overdue"] = bool(
            d["due_datetime"] and
            d["due_datetime"] < now_str and
            d["status"] in ("active", "partially_paid") and
            d["remaining_amount"] > 0
        )
        if d["is_overdue"]:
            try:
                due_dt = datetime.strptime(d["due_datetime"], "%Y-%m-%d %H:%M:%S")
                diff_days = (datetime.now() - due_dt).days
                d["overdue_days"] = max(1, diff_days)
            except Exception:
                d["overdue_days"] = 1
        else:
            d["overdue_days"] = 0
        debts.append(d)

    return debts


def add_debt_payment(
    conn: sqlite3.Connection,
    debt_id: int,
    amount: float,
    created_by_user_id: Optional[int] = None,
    note: str = "",
    client_request_id: Optional[str] = None,
) -> dict:
    """Внести частичный или полный платеж по долгу."""
    debt = get_debt_by_id(conn, debt_id)
    if not debt:
        raise ValueError("Долг не найден")

    if debt["status"] in ("paid", "cancelled"):
        raise ValueError("Долг уже закрыт или отменён")

    amount = round(amount, 2)
    if amount <= 0:
        raise ValueError("Сумма платежа должна быть больше нуля")
    if amount > round(float(debt["remaining_amount"]), 2):
        raise ValueError("Сумма платежа не может превышать остаток долга")

    if client_request_id:
        existing = conn.execute(
            "SELECT 1 FROM debt_payments WHERE debt_id = ? AND client_request_id = ?",
            (debt_id, client_request_id),
        ).fetchone()
        if existing:
            return debt

    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        INSERT INTO debt_payments (debt_id, amount, paid_at, created_by_user_id, note, client_request_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (debt_id, amount, now_str, created_by_user_id, note.strip(), client_request_id, now_str))

    new_remaining = round(max(0.0, debt["remaining_amount"] - amount), 2)
    if new_remaining <= 0:
        new_status = "paid"
        paid_at = now_str
        next_reminder = None  # Останавливаем напоминания
    else:
        new_status = "partially_paid"
        paid_at = None
        next_reminder = debt["next_reminder_at"]

    conn.execute("""
        UPDATE debts SET
            remaining_amount = ?,
            status = ?,
            paid_at = ?,
            next_reminder_at = ?,
            updated_at = ?
        WHERE id = ?
    """, (new_remaining, new_status, paid_at, next_reminder, now_str, debt_id))
    conn.commit()

    return get_debt_by_id(conn, debt_id, debt["group_id"])


def mark_debt_paid(conn: sqlite3.Connection, debt_id: int, user_id: Optional[int] = None) -> dict:
    """Полное погашение долга в один клик."""
    debt = get_debt_by_id(conn, debt_id)
    if not debt:
        raise ValueError("Долг не найден")

    if debt["remaining_amount"] > 0:
        return add_debt_payment(
            conn,
            debt_id=debt_id,
            amount=debt["remaining_amount"],
            created_by_user_id=user_id,
            note="Полное погашение в один клик"
        )
    return debt


def cancel_debt(conn: sqlite3.Connection, debt_id: int, user_id: Optional[int] = None) -> dict:
    """Отменить долг (status = cancelled)."""
    debt = get_debt_by_id(conn, debt_id)
    if not debt:
        raise ValueError("Долг не найден")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        UPDATE debts SET
            status = 'cancelled',
            next_reminder_at = NULL,
            updated_at = ?
        WHERE id = ?
    """, (now_str, debt_id))
    conn.commit()

    return get_debt_by_id(conn, debt_id, debt["group_id"])


def get_debts_summary(conn: sqlite3.Connection, group_id: int, user_id: Optional[int] = None) -> dict:
    """
    Финансовая сводка по долгам внутри группы:
    - totalIOwe: сколько я должен
    - totalOwedToMe: сколько должны мне
    - activeDebtsCount: количество активных долгов
    - overdueDebtsCount: количество просроченных долгов
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    active_rows = conn.execute("""
        SELECT * FROM debts
        WHERE group_id = ? AND status IN ('active', 'partially_paid') AND remaining_amount > 0
    """, (group_id,)).fetchall()

    # A personal dashboard must never show another participant's private debts.
    personal_rows = active_rows if user_id is None else [
        row for row in active_rows
        if row["debtor_user_id"] == user_id or row["creditor_user_id"] == user_id
    ]

    total_i_owe = 0.0
    total_owed_to_me = 0.0
    active_count = len(personal_rows)
    active_i_owe_count = 0
    overdue_count = 0

    for r in personal_rows:
        amt = r["remaining_amount"]
        is_overdue = bool(r["due_datetime"] and r["due_datetime"] < now_str)
        if is_overdue:
            overdue_count += 1

        if user_id:
            if r["debtor_user_id"] == user_id:
                total_i_owe += amt
                active_i_owe_count += 1
            if r["creditor_user_id"] == user_id:
                total_owed_to_me += amt

    return {
        "totalIOwe": round(total_i_owe, 2),
        "totalOwedToMe": round(total_owed_to_me, 2),
        "activeDebtsCount": active_count,
        "activeDebtsIOweCount": active_i_owe_count,
        "overdueDebtsCount": overdue_count,
    }


def get_pending_debt_reminders(conn: sqlite3.Connection, now_str: Optional[str] = None) -> list[dict]:
    """
    Получить все долги, для которых подошло время отправки напоминания:
    1. Просроченные/активные, где next_reminder_at <= now
    2. Предупреждение за 24 часа до срока (pre-due reminder)
    """
    if not now_str:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = conn.execute("""
        SELECT d.*, g.name as group_name
        FROM debts d
        JOIN groups g ON g.id = d.group_id
        WHERE d.status IN ('active', 'partially_paid')
          AND d.remaining_amount > 0
          AND (d.reminder_claimed_at IS NULL OR d.reminder_claimed_at < datetime(?, '-2 minutes'))
          AND (
            (d.next_reminder_at IS NOT NULL AND d.next_reminder_at <= ?)
            OR
            (d.due_datetime IS NOT NULL
             AND d.pre_due_reminder_sent_at IS NULL
             AND datetime(d.due_datetime, '-24 hours') <= ?
             AND ? < d.due_datetime)
          )
    """, (now_str, now_str, now_str, now_str)).fetchall()

    return [dict(r) for r in rows]


def claim_due_debt_reminder(conn: sqlite3.Connection, debt_id: int, now_str: str) -> bool:
    """Atomically reserve a due reminder so parallel bot workers cannot send it twice."""
    cur = conn.execute("""
        UPDATE debts
        SET reminder_claimed_at = ?
        WHERE id = ?
          AND status IN ('active', 'partially_paid')
          AND remaining_amount > 0
          AND (reminder_claimed_at IS NULL OR reminder_claimed_at < datetime(?, '-2 minutes'))
    """, (now_str, debt_id, now_str))
    conn.commit()
    return cur.rowcount == 1


def update_debt_reminder_schedule(
    conn: sqlite3.Connection,
    debt_id: int,
    last_reminder_at: str,
    next_reminder_at: Optional[str] = None,
    pre_due_reminder_sent_at: Optional[str] = None,
):
    """Обновить временные метки напоминаний в БД."""
    updates = ["last_reminder_at = ?", "reminder_claimed_at = NULL"]
    params = [last_reminder_at]

    if next_reminder_at is not None:
        updates.append("next_reminder_at = ?")
        params.append(next_reminder_at)

    if pre_due_reminder_sent_at is not None:
        updates.append("pre_due_reminder_sent_at = ?")
        params.append(pre_due_reminder_sent_at)

    updates.append("updated_at = ?")
    params.append(last_reminder_at)

    params.append(debt_id)
    conn.execute(f"UPDATE debts SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()


def update_debt_reminder_preferences(
    conn: sqlite3.Connection,
    debt_id: int,
    frequency: str,
    custom_minutes: Optional[int] = None,
) -> Optional[dict]:
    """Change one debt's reminder schedule and restart it from the new interval."""
    now = datetime.now()
    next_reminder = calculate_next_reminder(frequency, now, custom_minutes=custom_minutes)
    custom_hours = max(1, (int(custom_minutes) + 59) // 60) if custom_minutes else None
    conn.execute(
        """UPDATE debts SET notification_frequency = ?, custom_reminder_interval_minutes = ?,
           custom_reminder_interval_hours = ?, last_reminder_at = NULL, next_reminder_at = ?,
           reminder_claimed_at = NULL, updated_at = ? WHERE id = ?""",
        (frequency, custom_minutes, custom_hours, next_reminder, now.strftime("%Y-%m-%d %H:%M:%S"), debt_id),
    )
    conn.commit()
    return get_debt_by_id(conn, debt_id)


# ─── Финансовые функции и алгоритмы расчёта ───────────────────

def deterministic_split(total_amount: float, count: int) -> list[float]:
    """
    Детерминированное разделение суммы на N участников без потери копеек.
    100.00 на 3 -> [33.34, 33.33, 33.33], сумма строго 100.00!
    """
    if count <= 0:
        return []
    total_cents = int(round(total_amount * 100))
    base = total_cents // count
    remainder = total_cents % count
    splits = []
    for i in range(count):
        cents = base + (1 if i < remainder else 0)
        splits.append(round(cents / 100.0, 2))
    return splits


def calculate_room_settlement(conn: sqlite3.Connection, group_id: int, current_user_id: Optional[int] = None) -> dict:
    """
    Продуктовый расчет «Итоги комнаты» (Minimum Transfers Settlement):
    1. Рассчитывает net balance каждого участника в копейках.
    2. Разделяет участников на должников (debtors) и кредиторов (creditors).
    3. Жадным алгоритмом находит минимальный набор переводов.
    4. Формирует личный результат для current_user_id (+X ₽ / -X ₽).
    """
    members = get_group_members_users(conn, group_id)
    if not members:
        return {
            "room_id": group_id,
            "total_expenses": 0.0,
            "my_result": 0.0,
            "my_status": "zero",
            "transfers": [],
            "my_transfers": [],
            "members": [],
        }

    # Сколько каждый заплатил
    paid_rows = conn.execute(
        "SELECT paid_by, SUM(amount) as total FROM expenses WHERE group_id = ? GROUP BY paid_by",
        (group_id,),
    ).fetchall()
    paid_map = {row["paid_by"]: int(round(row["total"] * 100)) for row in paid_rows}

    # Сколько каждый должен (доли расходов)
    owed_rows = conn.execute("""
        SELECT es.user_id, SUM(es.share) as total
        FROM expense_splits es
        JOIN expenses e ON e.id = es.expense_id
        WHERE e.group_id = ?
        GROUP BY es.user_id
    """, (group_id,)).fetchall()
    owed_map = {row["user_id"]: int(round(row["total"] * 100)) for row in owed_rows}

    # Взаиморасчёты (settlements)
    sent_rows = conn.execute(
        "SELECT from_user_id, SUM(amount) as total FROM settlements WHERE group_id = ? GROUP BY from_user_id",
        (group_id,),
    ).fetchall()
    sent_map = {row["from_user_id"]: int(round(row["total"] * 100)) for row in sent_rows}

    recv_rows = conn.execute(
        "SELECT to_user_id, SUM(amount) as total FROM settlements WHERE group_id = ? GROUP BY to_user_id",
        (group_id,),
    ).fetchall()
    recv_map = {row["to_user_id"]: int(round(row["total"] * 100)) for row in recv_rows}

    member_dict = {m["id"]: m for m in members}
    all_uids = set(member_dict.keys()) | set(paid_map.keys()) | set(owed_map.keys())

    debtors = []
    creditors = []
    member_balances = []

    for uid in all_uids:
        paid_c = paid_map.get(uid, 0)
        owed_c = owed_map.get(uid, 0)
        sent_c = sent_map.get(uid, 0)
        recv_c = recv_map.get(uid, 0)

        # Net balance = (paid - owed) + sent - recv
        bal_cents = (paid_c - owed_c) + sent_c - recv_c
        bal_rub = round(bal_cents / 100.0, 2)

        user_info = member_dict.get(uid) or get_user_by_id(conn, uid)
        disp_name = user_info["display_name"] if user_info else f"Участник #{uid}"

        member_balances.append({
            "user_id": uid,
            "display_name": disp_name,
            "paid": round(paid_c / 100.0, 2),
            "share": round(owed_c / 100.0, 2),
            "balance": bal_rub,
            "balance_cents": bal_cents,
        })

        if bal_cents < -50:  # меньше -0.50 руб
            debtors.append({
                "user_id": uid,
                "display_name": disp_name,
                "debt_cents": -bal_cents,
            })
        elif bal_cents > 50:  # больше +0.50 руб
            creditors.append({
                "user_id": uid,
                "display_name": disp_name,
                "credit_cents": bal_cents,
            })

    # Сортируем для жадной минимизации
    debtors.sort(key=lambda x: -x["debt_cents"])
    creditors.sort(key=lambda x: -x["credit_cents"])

    transfers = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        d = debtors[i]
        c = creditors[j]
        amount_c = min(d["debt_cents"], c["credit_cents"])
        if amount_c >= 50:
            transfers.append({
                "from_user_id": d["user_id"],
                "from_name": d["display_name"],
                "to_user_id": c["user_id"],
                "to_name": c["display_name"],
                "amount": round(amount_c / 100.0, 2),
                "status": "pending",
            })
        d["debt_cents"] -= amount_c
        c["credit_cents"] -= amount_c
        if d["debt_cents"] < 50:
            i += 1
        if c["credit_cents"] < 50:
            j += 1

    # Общая сумма трат комнаты
    tot_row = conn.execute("SELECT SUM(amount) as s FROM expenses WHERE group_id = ?", (group_id,)).fetchone()
    total_spent = round(tot_row["s"] or 0.0, 2)

    # Личный результат текущего пользователя
    my_res = 0.0
    my_status = "zero"
    my_transfers = []
    if current_user_id:
        for mb in member_balances:
            if mb["user_id"] == current_user_id:
                my_res = mb["balance"]
                break
        if my_res > 0.50:
            my_status = "owed_to_me"
        elif my_res < -0.50:
            my_status = "i_owe"

        for t in transfers:
            if t["from_user_id"] == current_user_id:
                my_transfers.append({**t, "type": "i_pay"})
            elif t["to_user_id"] == current_user_id:
                my_transfers.append({**t, "type": "i_receive"})

    return {
        "room_id": group_id,
        "total_expenses": total_spent,
        "my_result": my_res,
        # Explicit public name for Mini App clients. `my_result` is retained
        # for existing bot/API consumers.
        "personal_result": my_res,
        "my_status": my_status,
        "transfers": transfers,
        "my_transfers": my_transfers,
        "member_balances": member_balances,
    }


# ─── Управление комнатами (Rooms) ──────────────────────────────

def create_room(
    conn: sqlite3.Connection,
    name: str,
    room_type: str = "long_term",
    currency: str = "RUB",
    creator_user_id: Optional[int] = None,
    telegram_chat_id: Optional[int] = None,
    members: Optional[list] = None,
    settlement_strategy: str = "min_transfers",
) -> dict:
    """Создать новую Комнату (Room) с форматом (разовый/длительная), валютой и участниками."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Если telegram_chat_id не передан, генерируем уникальный отрицательный ID
    if not telegram_chat_id:
        min_row = conn.execute("SELECT MIN(telegram_chat_id) as min_id FROM groups").fetchone()
        cur_min = min_row["min_id"] if min_row and min_row["min_id"] and min_row["min_id"] < 0 else -1000000
        telegram_chat_id = cur_min - 1

    try:
        conn.execute("BEGIN")
        cursor = conn.execute("""
            INSERT INTO groups (
                telegram_chat_id, name, type, currency, settlement_strategy, status,
                created_by_user_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
        """, (telegram_chat_id, name.strip(), room_type, currency, settlement_strategy, creator_user_id, now_str, now_str))
        room_id = cursor.lastrowid
        if not creator_user_id:
            raise ValueError("Для создания комнаты требуется авторизованный пользователь")
        conn.execute(
            "INSERT INTO group_members (group_id, user_id, role) VALUES (?, ?, 'creator')",
            (room_id, creator_user_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_group_by_id(conn, room_id)


def get_user_rooms(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    """
    Получить все комнаты пользователя с типом, валютой, суммой расходов и участниками.
    """
    rows = conn.execute("""
        SELECT g.id, g.telegram_chat_id, g.name, g.budget_limit, g.created_at,
               COALESCE(g.type, 'long_term') as type,
               COALESCE(g.currency, 'RUB') as currency,
               COALESCE(g.settlement_strategy, 'min_transfers') as settlement_strategy,
               COALESCE(g.status, 'active') as status,
               COALESCE((SELECT SUM(amount) FROM expenses WHERE group_id = g.id), 0.0) as total_expenses,
               (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as members_count
        FROM groups g
        JOIN group_members gm ON gm.group_id = g.id
        WHERE gm.user_id = ?
        ORDER BY g.id ASC
    """, (user_id,)).fetchall()
    return [dict(r) for r in rows]


def archive_room(conn: sqlite3.Connection, room_id: int) -> bool:
    """Завершить / архивировать комнату."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE groups SET status = 'settled', updated_at = ? WHERE id = ?", (now_str, room_id))
    conn.commit()
    return True


def user_can_delete_room(conn: sqlite3.Connection, room_id: int, user_id: int) -> bool:
    """Only the persisted creator (or a legacy creator role) may delete a room."""
    room = conn.execute("SELECT created_by_user_id FROM groups WHERE id = ?", (room_id,)).fetchone()
    if not room:
        return False
    if room["created_by_user_id"] is not None:
        return int(room["created_by_user_id"]) == int(user_id)
    membership = conn.execute("SELECT role FROM group_members WHERE group_id = ? AND user_id = ?", (room_id, user_id)).fetchone()
    return bool(membership and membership["role"] == "creator")


def delete_room(conn: sqlite3.Connection, room_id: int) -> dict:
    """Permanently remove one room and every room-scoped record atomically."""
    deleted = {}

    def remove(table: str, where: str, params: tuple = ()) -> None:
        cursor = conn.execute(f"DELETE FROM {table} WHERE {where}", params)
        deleted[table] = cursor.rowcount

    try:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT id FROM groups WHERE id = ?", (room_id,)).fetchone():
            raise LookupError("ROOM_NOT_FOUND")
        remove("room_invite_delivery_requests", "room_id = ?", (room_id,))
        remove("room_invites", "room_id = ?", (room_id,))
        remove("room_setups", "room_id = ?", (room_id,))
        remove("notifications", "group_id = ?", (room_id,))
        remove("notification_preferences", "group_id = ?", (room_id,))
        remove("member_import_requests", "group_id = ?", (room_id,))
        remove("settlements", "group_id = ?", (room_id,))
        remove("debt_payments", "debt_id IN (SELECT id FROM debts WHERE group_id = ?)", (room_id,))
        remove("debts", "group_id = ?", (room_id,))
        remove("expense_attachments", "group_id = ?", (room_id,))
        remove("expense_splits", "expense_id IN (SELECT id FROM expenses WHERE group_id = ?)", (room_id,))
        remove("expense_items", "expense_id IN (SELECT id FROM expenses WHERE group_id = ?)", (room_id,))
        remove("expenses", "group_id = ?", (room_id,))
        remove("category_budgets", "group_id = ?", (room_id,))
        remove("recurring_expenses", "group_id = ?", (room_id,))
        remove("group_members", "group_id = ?", (room_id,))
        remove("groups", "id = ?", (room_id,))
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise


# ─── Детальные расходы с позициями (ExpenseItems) ──────────────

def add_expense_itemized(
    conn: sqlite3.Connection,
    group_id: int,
    payer_id: int,
    title: str,
    items: list[dict],
    source_type: str = "manual",
    category: Optional[str] = None,
    currency: str = "RUB",
    raw_data: Optional[str] = None,
) -> dict:
    """
    Добавить расход со списком позиций (ExpenseItems) и индивидуальным распределением участников.
    Рассчитывает долю каждого участника с детерминированным округлением до копейки.
    """
    require_active_room_members(conn, group_id)
    members = get_group_members_users(conn, group_id)
    all_uids = [m["id"] for m in members] or [payer_id]

    if not items:
        # Если позиции не переданы, создаём одну общую позицию
        items = [{
            "name": title or "Расход",
            "quantity": 1,
            "unit_price": 0.0,
            "total_amount": 0.0,
            "category": category or "🔧 Другое",
            "participants": all_uids,
        }]

    # Считаем общую сумму расхода в копейках
    total_cents = 0
    for it in items:
        amt = it.get("total_amount") or (it.get("quantity", 1) * it.get("unit_price", 0))
        total_cents += int(round(amt * 100))

    total_amount = round(total_cents / 100.0, 2)
    cat = category or items[0].get("category") or "🔧 Другое"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor = conn.execute("""
        INSERT INTO expenses (
            group_id, paid_by, amount, description, category,
            source_type, title, currency, raw_data, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        group_id, payer_id, total_amount, title.strip() or cat, cat,
        source_type, title.strip(), currency, raw_data, now_str
    ))
    expense_id = cursor.lastrowid

    # Доля каждого участника в копейках
    participant_cents = {uid: 0 for uid in all_uids}

    for it in items:
        it_name = (it.get("name") or "Товар").strip()
        it_qty = float(it.get("quantity") or 1.0)
        it_price = float(it.get("unit_price") or 0.0)
        it_total = float(it.get("total_amount") or (it_qty * it_price))
        it_cat = it.get("category") or cat

        parts = it.get("participants")
        if parts == "all" or not parts:
            it_uids = all_uids
        else:
            it_uids = [int(p) for p in parts if int(p) in all_uids] or all_uids

        # Сохраняем позицию в expense_items
        conn.execute("""
            INSERT INTO expense_items (
                expense_id, name, quantity, unit_price, total_amount, category, participants_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            expense_id, it_name, it_qty, it_price, it_total, it_cat,
            json.dumps(it_uids, ensure_ascii=False), now_str
        ))

        # Детерминированное разделение суммы позиции
        it_splits = deterministic_split(it_total, len(it_uids))
        for uid, s_amt in zip(it_uids, it_splits):
            participant_cents[uid] += int(round(s_amt * 100))

    # Записываем сплиты в expense_splits
    payer = get_user_by_id(conn, payer_id)
    payer_name = payer["display_name"] if payer else f"User#{payer_id}"

    for uid, c_cents in participant_cents.items():
        if c_cents <= 0 and uid != payer_id:
            continue
        share_rub = round(c_cents / 100.0, 2)
        is_settled = 1 if uid == payer_id else 0
        conn.execute("""
            INSERT INTO expense_splits (
                expense_id, user_id, share, is_settled, share_type, calculated_amount
            ) VALUES (?, ?, ?, ?, 'itemized', ?)
        """, (expense_id, uid, share_rub, is_settled, share_rub))

        # Создаём Debt для прозрачности
        if uid != payer_id and share_rub > 0:
            debtor = get_user_by_id(conn, uid)
            debtor_name = debtor["display_name"] if debtor else f"User#{uid}"
            conn.execute("""
                INSERT INTO debts (
                    group_id, creditor_user_id, creditor_name,
                    debtor_user_id, debtor_name,
                    original_amount, remaining_amount, currency,
                    description, expense_id, status, created_by_user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
            """, (
                group_id, payer_id, payer_name,
                uid, debtor_name,
                share_rub, share_rub, currency,
                title or f"Доля за расход: {cat}",
                expense_id, payer_id
            ))

    conn.commit()
    _notify_expense_created(conn, group_id, payer_id, expense_id, title or cat, total_amount)
    return {
        "id": expense_id,
        "group_id": group_id,
        "amount": total_amount,
        "title": title,
        "category": cat,
        "items_count": len(items),
        "source_type": source_type,
    }


def get_expense_items(conn: sqlite3.Connection, expense_id: int) -> list[dict]:
    """Получить все позиции расхода."""
    rows = conn.execute(
        "SELECT * FROM expense_items WHERE expense_id = ? ORDER BY id ASC",
        (expense_id,),
    ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        if d.get("participants_json"):
            try:
                d["participants"] = json.loads(d["participants_json"])
            except Exception:
                d["participants"] = []
        else:
            d["participants"] = []
        items.append(d)
    return items
