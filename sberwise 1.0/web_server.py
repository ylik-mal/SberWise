"""
Асинхронный веб-сервер для Telegram Mini App (Web App) и REST API.
Реализует безопасную мультичатовую изоляцию (Multi-Chat Isolation) и валидацию Telegram initData.
"""

import asyncio
import os
import json
import logging
import hmac
import hashlib
import html
import urllib.parse
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
import aiohttp
from aiohttp import web

from config import BOT_TOKEN, APP_VERSION, OPENAI_API_KEY, GEMINI_API_KEY
from ai_module import parse_unstructured_expense_text, transcribe_and_parse_voice
from receipt_parser import parse_document_receipt, parse_image_receipt_items
from database import (
    create_room, get_user_rooms, archive_room, delete_room, user_can_delete_room, add_expense_itemized,
    RoomNeedsMoreMembersError, require_active_room_members,
    get_expense_items, calculate_room_settlement, deterministic_split,
    get_db,
    get_group_balances,
    get_category_totals,
    get_group_expenses,
    get_group_members_users,
    get_user_by_id,
    get_user_by_telegram_id,
    get_or_create_user,
    get_user_expense_count,
    add_expense,
    simplify_debts,
    get_group_budget_limit,
    set_group_budget_limit,
    get_category_budgets,
    set_category_budget,
    get_recurring_expenses,
    create_recurring_expense,
    delete_recurring_expense,
    reset_group_expenses,
    add_settlement,
    get_user_groups,
    is_user_group_member,
    get_group_by_id,
    get_group_by_chat_id,
    set_group_settlement_message_id,
    create_debt,
    get_debt_by_id,
    get_group_debts,
    add_debt_payment,
    mark_debt_paid,
    cancel_debt,
    update_debt_reminder_preferences,
    get_debts_summary,
    create_notification,
    get_notifications,
    mark_notification_read,
    mark_all_notifications_read,
)
from scoring_engine import calculate_comprehensive_score, calculate_budget_forecast
from analytics_engine import calculate_room_analytics
from invite_message import build_room_invite_caption

logger = logging.getLogger(__name__)

WEBAPP_DIR = os.path.join(os.path.dirname(__file__), "webapp")
INVITE_IMAGE_PATH = Path(__file__).resolve().parents[2] / "дизайн.png"


# ─── CORS Middleware ───────────────────────────────────────────

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Telegram-Init-Data"
    return response


@web.middleware
async def request_logger_middleware(request, handler):
    start = datetime.now()
    try:
        response = await handler(request)
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        # Не логируем частые проверки живости
        if not (request.path == "/health" or request.path == "/api/health"):
            logger.info(f"[{request.method}] {request.path} -> {response.status} ({duration_ms:.1f}ms)")
        return response
    except web.HTTPException as ex:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.info(f"[{request.method}] {request.path} -> HTTP {ex.status} ({duration_ms:.1f}ms)")
        raise
    except Exception as ex:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.error(f"[{request.method}] {request.path} -> EXCEPTION: {ex} ({duration_ms:.1f}ms)", exc_info=True)
        raise


# ─── Telegram Auth & InitData Validation ────────────────────────

def validate_telegram_init_data(init_data_str: str) -> Optional[dict]:
    """
    Валидация подписи Telegram Mini App initData по официальному алгоритму Telegram HMAC-SHA256.
    Возвращает распарсенный словарь (включая dict 'user') при успехе, иначе None.
    """
    if not init_data_str or not BOT_TOKEN:
        return None

    try:
        parsed = dict(urllib.parse.parse_qsl(init_data_str, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if hmac.compare_digest(calculated_hash, received_hash):
            if "user" in parsed:
                try:
                    parsed["user"] = json.loads(parsed["user"])
                except Exception:
                    pass
            return parsed
    except Exception as err:
        logger.warning(f"Telegram initData validation error: {err}")
    return None


def get_auth_user(request: web.Request, conn) -> Optional[dict]:
    """
    Определяет текущего пользователя Telegram:
    1. Через валидацию X-Telegram-Init-Data или query/body initData.
    2. Fallback для тестов и локального запуска: tg_user_id или user_id.
    3. Fallback на первого пользователя системы при прямом открытии в браузере.
    """
    init_data = request.headers.get("X-Telegram-Init-Data") or request.query.get("initData")
    if init_data:
        validated = validate_telegram_init_data(init_data)
        if validated and "user" in validated and isinstance(validated["user"], dict):
            raw_id = validated["user"].get("id")
            if raw_id is not None:
                try:
                    tg_uid = int(raw_id)
                except (ValueError, TypeError):
                    tg_uid = None
                if tg_uid:
                    u = get_user_by_telegram_id(conn, tg_uid)
                    if u:
                        return u
                    display_name = validated["user"].get("first_name", "") or validated["user"].get("username", "User")
                    return get_or_create_user(conn, tg_uid, validated["user"].get("username", ""), display_name)

    # Dev / Test fallback
    tg_uid_param = request.query.get("tg_user_id") or request.query.get("user_id")
    is_local_request = request.host.split(":")[0] in {"127.0.0.1", "localhost"}
    if tg_uid_param and is_local_request:
        try:
            val = int(tg_uid_param)
            row = conn.execute("SELECT * FROM users WHERE telegram_id = ? OR id = ?", (val, val)).fetchone()
            if row:
                return dict(row)
        except (ValueError, TypeError):
            pass

    # Fallback для прямого запуска в браузере: первый активный пользователь
    first_user = conn.execute("SELECT * FROM users ORDER BY id ASC LIMIT 1").fetchone()
    if first_user:
        return dict(first_user)

    return None


# ─── REST API Handlers ─────────────────────────────────────────

async def handle_health(request):
    """
    GET /health и GET /api/health (Section 7)
    Response при нормальной работе:
    HTTP 200: { "status": "ok", "database": "ok" }
    При недоступности БД:
    HTTP 503: { "status": "error", "database": "unavailable" }
    """
    db_status = "ok"
    status_code = 200
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"Health check database error: {e}")
        db_status = "unavailable"
        status_code = 503

    return web.json_response({
        "status": "ok" if db_status == "ok" else "error",
        "database": db_status
    }, status=status_code)


async def handle_ready(request):
    """
    GET /ready и GET /api/ready (Section 8)
    Проверяет:
    - backend initialized;
    - database available;
    - critical configuration loaded;
    - AI engine status.
    """
    checks = {
        "status": "ready",
        "database": "ok",
        "bot": "configured" if BOT_TOKEN else "unconfigured",
        "ai_engine": "ok",
        "version": APP_VERSION,
        "time": datetime.now().isoformat()
    }
    status_code = 200

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM groups")
        group_count = cursor.fetchone()[0]
        conn.close()
        checks["groups_count"] = group_count
    except Exception as e:
        checks["database"] = f"error: {e}"
        checks["status"] = "not_ready"
        status_code = 503

    try:
        from ai_module import get_ai_engine_status
        ai_stat = get_ai_engine_status()
        checks["ai_status"] = ai_stat.get("status", "ok")
    except Exception:
        checks["ai_status"] = "degraded"

    return web.json_response(checks, status=status_code)


async def handle_get_user_groups(request):
    """
    Возвращает список всех групп бюджета, в которых состоит текущий пользователь.
    Используется Telegram Mini App для отображения списка групп и переключения между ними.
    """
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user:
            # Fallback: все группы в системе
            all_groups = conn.execute("SELECT * FROM groups ORDER BY id ASC").fetchall()
            return web.json_response({"groups": [dict(g) for g in all_groups], "user": None})

        groups = get_user_groups(conn, user["id"])
        if not groups:
            first_g = conn.execute("SELECT * FROM groups ORDER BY id ASC LIMIT 1").fetchone()
            if first_g:
                try:
                    add_member_to_group(conn, first_g["id"], user["id"])
                    groups = get_user_groups(conn, user["id"])
                except Exception:
                    pass

        for group in groups:
            group["can_delete_room"] = user_can_delete_room(conn, group["id"], user["id"])
        return web.json_response({
            "groups": groups,
            "user": {"id": user["id"], "name": user["display_name"], "telegram_id": user["telegram_id"]}
        })
    finally:
        conn.close()


async def handle_group_summary(request):
    """
    Возвращает полную аналитическую сводку по группе.
    - Автоматически резолвит группу пользователя при gid == 0
    - Автоматически добавляет пользователя в группу при первом входе
    """
    group_id_param = request.match_info.get("group_id")
    conn = get_db()

    try:
        user = get_auth_user(request, conn)

        # 1. Поиск группы. An explicitly requested room is never an implicit
        # join request: only its current members may read its summary.
        group_row = None
        gid_int = 0
        try:
            gid_int = int(group_id_param)
            if gid_int != 0:
                group_row = conn.execute(
                    "SELECT * FROM groups WHERE id = ? OR telegram_chat_id = ?",
                    (gid_int, gid_int)
                ).fetchone()
        except (ValueError, TypeError):
            gid_int = 0

        requested_group = gid_int != 0
        if requested_group and not group_row:
            return web.json_response({"error": "Комната не найдена"}, status=404)
        if requested_group and user and not is_user_group_member(conn, group_row["id"], user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой комнате"}, status=403)

        # При group_id == 0 определяем комнату пользователя по умолчанию.
        if not group_row and user:
            user_groups = get_user_groups(conn, user["id"])
            if user_groups:
                group_row = conn.execute("SELECT * FROM groups WHERE id = ?", (user_groups[0]["id"],)).fetchone()
            else:
                first_g = conn.execute("SELECT * FROM groups ORDER BY id ASC LIMIT 1").fetchone()
                if first_g:
                    try:
                        add_member_to_group(conn, first_g["id"], user["id"])
                    except Exception:
                        pass
                    group_row = first_g

        # Fallback для тестов, если пользователь не указан
        if not group_row:
            group_row = conn.execute("SELECT * FROM groups ORDER BY id ASC LIMIT 1").fetchone()

        if not group_row:
            return web.json_response({
                "group_id": 0,
                "group_name": "СберСплит",
                "total_expenses": 0.0,
                "budget": {"target_budget": 100000.0, "daily_burn_rate": 0.0, "days_until_critical": 30, "is_overbudget": False},
                "category_totals": {},
                "balances": {},
                "simplified_debts": [],
                "scoring": [],
                "expenses": [],
                "members": [],
                "available_groups": [],
                "current_user": user,
            })

        group_id = group_row["id"]
        group_name = group_row["name"] or "Коллективный бюджет"

        # 2. Автодобавление допустимо только для неявно выбранной комнаты.
        if user and not requested_group:
            is_member = is_user_group_member(conn, group_id, user["id"])
            if not is_member:
                try:
                    add_member_to_group(conn, group_id, user["id"])
                except Exception:
                    pass

        # 3. Список доступных пользователю групп для переключателя
        available_groups = []
        if user:
            available_groups = get_user_groups(conn, user["id"])
        if not available_groups:
            available_groups = [dict(group_row)]

        # 4. Расходы и категории (СТРОГО WHERE group_id = ?)
        expenses = get_group_expenses(conn, group_id, limit=50)
        category_totals = get_category_totals(conn, group_id)
        total_spent = sum(category_totals.values())

        # 5. Участники и балансы (СТРОГО WHERE group_id = ?)
        members = get_group_members_users(conn, group_id)
        raw_balances = get_group_balances(conn, group_id)
        named_balances = {}
        for uid, val in raw_balances.items():
            u = get_user_by_id(conn, uid)
            name = u["display_name"] if u else f"User#{uid}"
            named_balances[name] = val

        # 6. Упрощенные взаиморасчеты (минимизация транзакций)
        raw_debts = simplify_debts(raw_balances)
        simplified_debts = []
        for f_id, t_id, amt in raw_debts:
            fu = get_user_by_id(conn, f_id)
            tu = get_user_by_id(conn, t_id)
            simplified_debts.append({
                "from_name": fu["display_name"] if fu else f"User#{f_id}",
                "to_name": tu["display_name"] if tu else f"User#{t_id}",
                "amount": amt,
            })

        # 7. Альтернативный Скоринг Сбера для каждого участника этой группы
        scoring_profiles = []
        for m in members:
            uid = m["id"]
            bal = raw_balances.get(uid, 0.0)
            exp_count = get_user_expense_count(conn, uid, group_id)

            paid_row = conn.execute(
                "SELECT SUM(amount) FROM expenses WHERE paid_by = ? AND group_id = ?",
                (uid, group_id),
            ).fetchone()
            paid_total = paid_row[0] or 0.0

            share_row = conn.execute("""
                SELECT SUM(es.share) FROM expense_splits es
                JOIN expenses e ON e.id = es.expense_id
                WHERE es.user_id = ? AND e.group_id = ?
            """, (uid, group_id)).fetchone()
            share_total = share_row[0] or 0.0

            receipts_count = conn.execute(
                "SELECT COUNT(*) FROM expenses WHERE paid_by = ? AND group_id = ? AND (description LIKE '%чек%' OR description LIKE '%оплата%')",
                (uid, group_id),
            ).fetchone()[0] or 0

            profile = calculate_comprehensive_score(
                user_id=uid,
                user_display_name=m["display_name"],
                expenses_paid_count=exp_count,
                expenses_paid_total=paid_total,
                user_share_total=share_total,
                current_balance=bal,
                settlements_sent_count=1 if bal >= 0 else 0,
                settlements_sent_total=paid_total,
                settlements_received_count=0,
                verified_receipts_count=receipts_count,
                avg_days_to_settle=1.5 if bal >= 0 else 3.5,
            )
            scoring_profiles.append(profile)

        # 8. Предиктивный прогноз бюджета группы (AI фича)
        now = datetime.now()
        group_budget_limit = get_group_budget_limit(conn, group_id)
        budget_forecast = calculate_budget_forecast(
            total_spent_month=total_spent,
            days_elapsed=max(1, now.day),
            days_in_month=30,
            target_budget=group_budget_limit,
        )

        # 9. Список расходов для UI
        formatted_expenses = []
        for e in expenses[:30]:
            p = get_user_by_id(conn, e["paid_by"])
            formatted_expenses.append({
                "id": e["id"],
                "amount": e["amount"],
                "description": e["description"],
                "category": e["category"],
                "created_at": e["created_at"],
                "payer_name": p["display_name"] if p else "Участник",
            })

        can_delete_room = bool(user and user_can_delete_room(conn, group_id, user["id"]))
        return web.json_response({
            "group_id": group_id,
            "room_id": group_id,
            "group_name": group_name,
            "room_name": group_name,
            "room_type": group_row["type"] or "long_term",
            "can_delete_room": can_delete_room,
            "total_expenses": total_spent,
            "spent": total_spent,
            "budget": budget_forecast,
            "category_totals": category_totals,
            "categories": [{"category": k, "amount": v} for k, v in category_totals.items()],
            "balances": named_balances,
            "simplified_debts": simplified_debts,
            "debts_summary": get_debts_summary(conn, group_id, user["id"] if user else None),
            "scoring": scoring_profiles,
            "expenses": formatted_expenses,
            "members": [{"id": m["id"], "name": m.get("member_display_name") or m.get("display_name"), "username": m.get("username"), "status": m.get("status", "active"), "is_external": bool(m.get("is_external"))} for m in members],
            "available_groups": [
                {
                    "id": g["id"],
                    "name": g["name"],
                    "room_type": g.get("type") or "long_term",
                    "currency": g.get("currency") or "RUB",
                    "total_expenses": g.get("total_expenses", 0.0),
                    "members_count": g.get("members_count", 0),
                }
                for g in available_groups
            ],
            "available_rooms": [
                {
                    "id": g["id"],
                    "name": g["name"],
                    "room_type": g.get("type") or "long_term",
                    "currency": g.get("currency") or "RUB",
                    "total_expenses": g.get("total_expenses", 0.0),
                    "members_count": g.get("members_count", 0),
                }
                for g in available_groups
            ],
            "current_user": {"id": user["id"], "name": user["display_name"]} if user else None,
        })

    except Exception as err:
        logger.error(f"Error in handle_group_summary: {err}", exc_info=True)
        return web.json_response({"error": str(err)}, status=500)
    finally:
        conn.close()


async def handle_get_group_analytics(request):
    """
    Возвращает реальную аналитику расходов строго по указанной комнате и периоду:
    - Проверка безопасности: пользователь обязан состоять в комнате (иначе 403 Forbidden).
    - Query-параметры:
      - period: current_month | prev_month | 7_days | 30_days | all_time | custom
      - from: YYYY-MM-DD (для custom)
      - to: YYYY-MM-DD (для custom)
    """
    group_id_param = request.match_info.get("group_id")
    conn = get_db()
    try:
        user = get_auth_user(request, conn)

        # 1. Поиск группы
        group_row = None
        try:
            gid_int = int(group_id_param)
            if gid_int != 0:
                group_row = conn.execute(
                    "SELECT * FROM groups WHERE id = ? OR telegram_chat_id = ?",
                    (gid_int, gid_int)
                ).fetchone()
        except (ValueError, TypeError):
            gid_int = 0

        if not group_row and user:
            user_groups = get_user_groups(conn, user["id"])
            if user_groups:
                group_row = conn.execute("SELECT * FROM groups WHERE id = ?", (user_groups[0]["id"],)).fetchone()

        if not group_row:
            group_row = conn.execute("SELECT * FROM groups ORDER BY id ASC LIMIT 1").fetchone()

        if not group_row:
            return web.json_response({"error": "Комната не найдена"}, status=404)

        group_id = group_row["id"]

        # 2. ПРОВЕРКА БЕЗОПАСНОСТИ (Membership Check)
        if user:
            is_member = is_user_group_member(conn, group_id, user["id"])
            if not is_member:
                logger.warning(f"Forbidden: User {user['id']} tried to access Analytics for Group {group_id}")
                return web.json_response({
                    "error": "Forbidden: Вы не состоите в этой комнате",
                    "code": 403
                }, status=403)

        # 3. Чтение параметров периода
        period_type = request.query.get("period", "current_month")
        date_from = request.query.get("from")
        date_to = request.query.get("to")

        # 4. Расчет реальной аналитики
        analytics = calculate_room_analytics(
            conn=conn,
            group_id=group_id,
            period_type=period_type,
            date_from_str=date_from,
            date_to_str=date_to
        )

        return web.json_response(analytics)

    except Exception as err:
        logger.error(f"Error in handle_get_group_analytics: {err}", exc_info=True)
        return web.json_response({"error": str(err)}, status=500)
    finally:
        conn.close()


async def handle_add_expense(request):
    """Добавление расхода из WebApp интерфейса с проверкой membership."""
    group_id_param = request.match_info.get("group_id")
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    amount = float(body.get("amount", 0))
    category = body.get("category", "🔧 Другое")
    # The WebApp submits the user-entered name as `title`; keep accepting
    # `description` for older clients and never replace a supplied title with
    # the generic WebApp fallback.
    raw_description = str(body.get("description") or "").strip()
    raw_title = str(body.get("title") or "").strip()
    # Legacy clients sent a generic description alongside the actual user title.
    # Keep the user-entered text whenever it is available.
    description = raw_title or ("" if raw_description.lower() == "расход из webapp" else raw_description) or category

    if amount <= 0:
        return web.json_response({"error": "Сумма должна быть больше нуля"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        # Также проверяем user_id из body если передан
        if not user and body.get("user_id"):
            try:
                u_id = int(body["user_id"])
                user = get_user_by_id(conn, u_id)
            except Exception:
                pass

        group_row = None
        try:
            gid_int = int(group_id_param)
            group_row = conn.execute("SELECT * FROM groups WHERE id = ? OR telegram_chat_id = ?", (gid_int, gid_int)).fetchone()
        except (ValueError, TypeError):
            pass

        if not group_row:
            return web.json_response({"error": "Группа не найдена"}, status=404)

        group_id = group_row["id"]

        # Membership check
        if user:
            if not is_user_group_member(conn, group_id, user["id"]):
                return web.json_response({"error": "Forbidden: Вы не состоите в этой группе", "code": 403}, status=403)

        members = get_group_members_users(conn, group_id)
        if not members:
            return web.json_response({"error": "В группе нет участников"}, status=400)
        try:
            require_active_room_members(conn, group_id)
        except RoomNeedsMoreMembersError as err:
            return web.json_response({"error": str(err), "code": "ROOM_NEEDS_MEMBERS"}, status=409)

        # Плательщик — авторизованный пользователь или первый участник
        payer = user if user and any(m["id"] == user["id"] for m in members) else members[0]

        member_ids = [m["id"] for m in members]
        is_personal = bool(body.get("is_personal", False))
        split_user_ids = [payer["id"]] if is_personal else member_ids

        request_id = str(body.get("client_request_id") or "").strip()[:80] or None
        if request_id:
            existing = conn.execute("SELECT id FROM expenses WHERE group_id=? AND paid_by=? AND client_request_id=?", (group_id, payer["id"], request_id)).fetchone()
            if existing:
                return web.json_response({"success": True, "duplicate": True, "expense_id": existing["id"]})
        try:
            expense_id = add_expense(
            conn,
            group_id=group_id,
            payer_id=payer["id"],
            amount=amount,
            description=description,
            category=category,
            split_user_ids=split_user_ids, client_request_id=request_id,
            )
        except sqlite3.IntegrityError:
            existing = conn.execute("SELECT id FROM expenses WHERE group_id=? AND paid_by=? AND client_request_id=?", (group_id, payer["id"], request_id)).fetchone()
            if existing:
                return web.json_response({"success": True, "duplicate": True, "expense_id": existing["id"]})
            raise

        return web.json_response({"success": True, "expense_id": expense_id, "message": "Расход успешно сохранён"})
    finally:
        conn.close()


async def handle_settle_debt(request):
    """Погашение долга между участниками из WebApp с проверкой membership."""
    group_id_param = request.match_info.get("group_id")
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    from_name = body.get("from_name")
    to_name = body.get("to_name")
    amount = float(body.get("amount", 0))
    client_request_id = str(body.get("client_request_id") or "").strip()[:100] or None

    if amount <= 0 or not from_name or not to_name:
        return web.json_response({"error": "Некорректные параметры"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        group_row = None
        try:
            gid_int = int(group_id_param)
            group_row = conn.execute("SELECT * FROM groups WHERE id = ? OR telegram_chat_id = ?", (gid_int, gid_int)).fetchone()
        except (ValueError, TypeError):
            pass

        if not group_row:
            return web.json_response({"error": "Группа не найдена"}, status=404)

        group_id = group_row["id"]

        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой группе", "code": 403}, status=403)

        members = get_group_members_users(conn, group_id)
        from_user = next((m for m in members if m["display_name"] == from_name or m["username"] == from_name), None)
        to_user = next((m for m in members if m["display_name"] == to_name or m["username"] == to_name), None)

        if not from_user or not to_user:
            return web.json_response({"error": "Пользователи не найдены в этой группе"}, status=404)

        duplicate = False
        if client_request_id:
            duplicate = bool(conn.execute("SELECT 1 FROM settlements WHERE group_id = ? AND from_user_id = ? AND to_user_id = ? AND client_request_id = ?", (group_id, from_user["id"], to_user["id"], client_request_id)).fetchone())
        add_settlement(conn, group_id, from_user["id"], to_user["id"], amount, client_request_id=client_request_id)
        return web.json_response({"success": True, "duplicate": duplicate, "message": "Погашение уже учтено" if duplicate else f"Погашение {amount:,.0f} ₽ записано!"})
    finally:
        conn.close()


async def handle_update_budget(request):
    """Обновление месячного лимита бюджета группы с проверкой membership."""
    group_id_param = request.match_info.get("group_id")
    try:
        body = await request.json()
        # `budget` is the current client contract. Keep `budget_limit` as a
        # backwards-compatible alias so an already-open Mini App is not left
        # unable to save its room settings after an update.
        budget = float(body.get("budget", body.get("budget_limit", 0)))
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    if budget <= 0:
        return web.json_response({"error": "Лимит должен быть больше 0"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        gid = int(group_id_param)

        if user and not is_user_group_member(conn, gid, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой группе", "code": 403}, status=403)

        set_group_budget_limit(conn, gid, budget)
        return web.json_response({"success": True, "budget": budget})
    finally:
        conn.close()


async def handle_reset_month(request):
    """Обнуление расходов текущего месяца с проверкой membership."""
    group_id_param = request.match_info.get("group_id")
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        gid = int(group_id_param)

        if user and not is_user_group_member(conn, gid, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой группе", "code": 403}, status=403)

        count = reset_group_expenses(conn, gid, only_current_month=True)
        return web.json_response({"success": True, "deleted": count})
    finally:
        conn.close()


async def handle_webapp_index(request):
    """Отдаёт главную страницу Telegram Mini App (Section 9, 32)."""
    index_path = os.path.join(WEBAPP_DIR, "index.html")
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    if os.path.exists(index_path):
        return web.FileResponse(index_path, headers=headers)
    return web.Response(
        text="<!DOCTYPE html><html><head><meta charset='utf-8'><title>SberSplit</title></head><body><h1>SberSplit Mini App</h1></body></html>",
        content_type="text/html",
        headers=headers,
        status=200
    )




async def handle_auth_telegram(request):
    """
    POST /api/auth/telegram или GET /api/auth/telegram
    Валидирует Telegram initData и возвращает профиль пользователя.
    """
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user:
            return web.json_response({"authenticated": False, "user": None}, status=401)
        return web.json_response({
            "authenticated": True,
            "user": {
                "id": user["id"],
                "telegram_id": user["telegram_id"],
                "username": user["username"],
                "name": user["display_name"],
            }
        })
    finally:
        conn.close()


async def handle_get_room_expenses(request):
    """GET /api/rooms/{group_id}/expenses — полная история для вкладки истории."""
    group_id_param = request.match_info.get("group_id")
    try:
        gid = int(group_id_param)
    except Exception:
        gid = 1
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, gid, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой комнате"}, status=403)
        expenses = get_group_expenses(conn, gid, limit=500)
        formatted = []
        for e in expenses:
            p = get_user_by_id(conn, e["paid_by"])
            formatted.append({
                "id": e["id"],
                "amount": e["amount"],
                "description": e["description"],
                "category": e["category"],
                "created_at": e["created_at"],
                "payer_name": p["display_name"] if p else "Участник",
            })
        return web.json_response({"expenses": formatted, "count": len(formatted)})
    finally:
        conn.close()


# ─── REST API: ЦЕНТР УВЕДОМЛЕНИЙ ─────────────────────────────
async def handle_get_notifications(request):
    """Возвращает сохранённые события только для текущего пользователя и комнаты."""
    try:
        group_id = int(request.match_info.get("group_id"))
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid group_id"}, status=400)
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user or not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden"}, status=403)
        rows = get_notifications(conn, user["id"], group_id)
        unread = sum(1 for row in rows if not row.get("read_at"))
        return web.json_response({"notifications": rows, "count": len(rows), "unread_count": unread})
    finally:
        conn.close()


async def _get_plan_group(request, conn):
    """Resolve a room for Plan API and enforce the same membership boundary as other room APIs."""
    try:
        group_id = int(request.match_info.get("group_id"))
    except (ValueError, TypeError):
        raise web.HTTPBadRequest(text="Некорректный идентификатор комнаты")
    group = conn.execute("SELECT id FROM groups WHERE id = ?", (group_id,)).fetchone()
    if not group:
        raise web.HTTPNotFound(text="Комната не найдена")
    user = get_auth_user(request, conn)
    if user and not is_user_group_member(conn, group_id, user["id"]):
        raise web.HTTPForbidden(text="Вы не состоите в этой комнате")
    return group_id


async def handle_get_group_plan(request):
    conn = get_db()
    try:
        group_id = await _get_plan_group(request, conn)
        analytics = calculate_room_analytics(conn, group_id, period_type="current_month")
        spent_by_category = {
            row.get("category", "Другое"): float(row.get("amount", 0) or 0)
            for row in analytics.get("categories", [])
        }
        limits = {row["category"]: float(row["monthly_limit"]) for row in get_category_budgets(conn, group_id)}
        categories = []
        for category in sorted(set(spent_by_category) | set(limits)):
            spent = spent_by_category.get(category, 0.0)
            limit = limits.get(category)
            categories.append({
                "category": category,
                "spent": spent,
                "limit": limit,
                "percent": round((spent / limit * 100) if limit else 0, 1),
            })
        recurring = get_recurring_expenses(conn, group_id)
        recurring_total = sum(float(item["amount"]) for item in recurring if item.get("active"))
        budget = get_group_budget_limit(conn, group_id)
        total_spent = sum(spent_by_category.values())
        recommendations = []
        if budget:
            remaining = budget - total_spent - recurring_total
            recommendations.append({
                "kind": "budget",
                "title": "Остаток на месяц",
                "text": f"После регулярных расходов останется {max(remaining, 0):,.0f} ₽".replace(",", " "),
                "status": "warning" if remaining < 0 else "ok",
            })
        for row in categories:
            if row["limit"] and row["percent"] >= 80:
                recommendations.append({"kind": "limit", "title": row["category"], "text": f"Использовано {row['percent']:.0f}% лимита", "status": "warning"})
        return web.json_response({
            "budget": budget,
            "total_spent": total_spent,
            "category_budgets": categories,
            "recurring_expenses": recurring,
            "recurring_total": recurring_total,
            "recommendations": recommendations[:3],
        })
    finally:
        conn.close()


async def handle_set_category_budget(request):
    try:
        body = await request.json()
        category = str(body.get("category", "")).strip()[:80]
        monthly_limit = float(body.get("monthly_limit", 0))
    except Exception:
        return web.json_response({"error": "Некорректные данные лимита"}, status=400)
    if not category or monthly_limit <= 0:
        return web.json_response({"error": "Укажите категорию и лимит больше нуля"}, status=400)
    conn = get_db()
    try:
        group_id = await _get_plan_group(request, conn)
        set_category_budget(conn, group_id, category, monthly_limit)
        return web.json_response({"success": True, "category": category, "monthly_limit": monthly_limit})
    finally:
        conn.close()


async def handle_create_recurring_expense(request):
    try:
        body = await request.json()
        title = str(body.get("title", "")).strip()[:120]
        amount = float(body.get("amount", 0))
        category = str(body.get("category") or "Другое").strip()[:80]
        next_due_date = body.get("next_due_date") or None
    except Exception:
        return web.json_response({"error": "Некорректные данные платежа"}, status=400)
    if not title or amount <= 0:
        return web.json_response({"error": "Укажите название и сумму больше нуля"}, status=400)
    conn = get_db()
    try:
        group_id = await _get_plan_group(request, conn)
        recurring_id = create_recurring_expense(conn, group_id, title, amount, category, next_due_date)
        return web.json_response({"success": True, "id": recurring_id}, status=201)
    finally:
        conn.close()


async def handle_delete_recurring_expense(request):
    conn = get_db()
    try:
        group_id = await _get_plan_group(request, conn)
        recurring_id = int(request.match_info.get("recurring_id"))
        if not delete_recurring_expense(conn, group_id, recurring_id):
            return web.json_response({"error": "Платёж не найден"}, status=404)
        return web.json_response({"success": True})
    finally:
        conn.close()


async def handle_request_telegram_members(request):
    """Ask the bot to show Telegram's native user picker in the user's private chat."""
    try:
        group_id = int(request.match_info["group_id"])
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid group_id"}, status=400)
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user or not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden"}, status=403)
        conn.execute("CREATE TABLE IF NOT EXISTS member_import_requests (request_id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL, requested_by_user_id INTEGER NOT NULL, status TEXT DEFAULT 'pending', created_at TEXT DEFAULT (datetime('now')), completed_at TEXT)")
        try:
            conn.execute("ALTER TABLE member_import_requests ADD COLUMN completed_at TEXT")
        except sqlite3.OperationalError:
            pass
        pending = conn.execute("""
            SELECT request_id FROM member_import_requests
            WHERE group_id = ? AND requested_by_user_id = ? AND status = 'pending'
              AND created_at >= datetime('now', '-10 minutes')
            ORDER BY created_at DESC LIMIT 1
        """, (group_id, user["id"])).fetchone()
        if pending:
            conn.commit()
            return web.json_response({"ok": True, "request_id": pending["request_id"], "already_pending": True})
        request_id = secrets.randbelow(2_000_000_000) + 1
        conn.execute("INSERT INTO member_import_requests (request_id, group_id, requested_by_user_id) VALUES (?, ?, ?)", (request_id, group_id, user["id"]))
        conn.commit()
        if not BOT_TOKEN:
            return web.json_response({"error": "BOT_TOKEN не настроен"}, status=503)
        payload = {"chat_id": user["telegram_id"], "text": "Выберите участников комнаты в списке Telegram и отправьте выбор обратно в бота.", "reply_markup": {"keyboard": [[{"text": "👥 Выбрать участников", "request_users": {"request_id": request_id, "user_is_bot": False, "max_quantity": 10, "request_name": True, "request_username": True}}]], "resize_keyboard": True, "one_time_keyboard": True}}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=10) as response:
                result = await response.json(content_type=None)
                if response.status >= 400 or not result.get("ok"):
                    return web.json_response({"error": "Telegram не принял запрос выбора пользователей"}, status=502)
        return web.json_response({"ok": True, "request_id": request_id})
    finally:
        conn.close()


async def handle_get_telegram_member_request(request):
    """Return the picker result without sending another Telegram instruction."""
    try:
        group_id = int(request.match_info["group_id"])
        request_id = int(request.match_info["request_id"])
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid request"}, status=400)
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        row = conn.execute("SELECT status FROM member_import_requests WHERE request_id = ? AND group_id = ? AND requested_by_user_id = ?", (request_id, group_id, user["id"] if user else -1)).fetchone()
        if not row:
            return web.json_response({"error": "Запрос выбора не найден"}, status=404)
        return web.json_response({"status": row["status"]})
    finally:
        conn.close()


async def handle_request_room_invite_delivery(request):
    """Ask the bot to deliver a styled room invitation to selected Telegram users."""
    try:
        group_id = int(request.match_info["group_id"])
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        room = get_group_by_id(conn, group_id)
        if not room:
            return web.json_response({"error": "Комната не найдена"}, status=404)
        if not user or not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden"}, status=403)
        if not BOT_TOKEN:
            return web.json_response({"error": "BOT_TOKEN не настроен"}, status=503)

        request_id = secrets.randbelow(2_000_000_000) + 1
        conn.execute(
            "INSERT INTO room_invite_delivery_requests (request_id, room_id, requested_by_user_id) VALUES (?, ?, ?)",
            (request_id, group_id, user["id"]),
        )
        conn.commit()

        payload = {
            "chat_id": user["telegram_id"],
            "text": "Выберите пользователей — SberWise отправит каждому красивое приглашение в комнату.",
            "reply_markup": {
                "keyboard": [[{
                    "text": "👥 Выбрать получателей",
                    "request_users": {
                        "request_id": request_id,
                        "user_is_bot": False,
                        "max_quantity": 10,
                        "request_name": True,
                        "request_username": True,
                    },
                }]],
                "resize_keyboard": True,
                "one_time_keyboard": True,
            },
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=10) as response:
                result = await response.json(content_type=None)
                if response.status >= 400 or not result.get("ok"):
                    conn.execute("UPDATE room_invite_delivery_requests SET status = 'failed', completed_at = datetime('now') WHERE request_id = ?", (request_id,))
                    conn.commit()
                    return web.json_response({"error": "Telegram не принял запрос выбора получателей"}, status=502)
        return web.json_response({"ok": True, "request_id": request_id})
    finally:
        conn.close()


async def handle_create_room_setup(request):
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user:
            return web.json_response({"error": "Authentication required"}, status=401)
        token = secrets.token_urlsafe(24)
        connect_code = "SW-" + secrets.token_hex(3).upper()
        conn.execute("INSERT INTO room_setups (token, connect_code, created_by_user_id, expires_at) VALUES (?, ?, ?, datetime('now', '+15 minutes'))", (token, connect_code, user["id"]))
        conn.commit()
        bot_username = os.getenv("BOT_USERNAME", "Xakatonsberbot")
        return web.json_response({"setupId": token, "connectCode": connect_code, "telegramAddBotUrl": f"https://t.me/{bot_username}?startgroup=setup_{token}&admin=invite_users", "expiresAt": conn.execute("SELECT expires_at FROM room_setups WHERE token = ?", (token,)).fetchone()[0]})
    finally:
        conn.close()


async def resolve_room_invite_link(chat_id: int, bot_id: int, can_invite: bool):
    """Resolve a real invite link using only Telegram Bot API responses."""
    if not BOT_TOKEN:
        return None, "BOT_TOKEN не настроен"
    async with aiohttp.ClientSession() as session:
        async with session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat", json={"chat_id": chat_id}, timeout=10) as response:
            chat_result = await response.json(content_type=None)
        chat = chat_result.get("result") or {}
        logger.info("ROOM_INVITE_CHAT chat_id=%s type=%s title=%s invite_link_present=%s keys=%s", chat_id, chat.get("type"), chat.get("title"), bool(chat.get("invite_link")), sorted(chat.keys()))
        if chat.get("invite_link"):
            return chat["invite_link"], None
        logger.info("INVITE_CREATE_START chat_id=%s bot_status=administrator can_invite_users=%s", chat_id, can_invite)
        async with session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink", json={"chat_id": chat_id, "name": "SberWise", "creates_join_request": False}, timeout=10) as response:
            result = await response.json(content_type=None)
        link = (result.get("result") or {}).get("invite_link")
        if link:
            logger.info("INVITE_CREATE_SUCCESS chat_id=%s", chat_id)
            return link, None
        logger.warning("INVITE_CREATE_ERROR chat_id=%s error_code=%s description=%s", chat_id, result.get("error_code"), result.get("description"))
        async with session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/exportChatInviteLink", json={"chat_id": chat_id}, timeout=10) as response:
            export_result = await response.json(content_type=None)
        exported = export_result.get("result")
        if exported:
            logger.info("INVITE_EXPORT_SUCCESS chat_id=%s", chat_id)
            return exported, None
        error = export_result.get("description") or result.get("description") or "Telegram не вернул invite link"
        logger.warning("INVITE_EXPORT_ERROR chat_id=%s error_code=%s description=%s", chat_id, export_result.get("error_code"), error)
        return None, error


async def handle_room_setup_status(request):
    token = request.match_info.get("setup_id", "")
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        row = conn.execute("SELECT rs.*, g.name AS room_name FROM room_setups rs LEFT JOIN groups g ON g.id = rs.room_id WHERE rs.token = ? AND rs.created_by_user_id = ?", (token, user["id"] if user else -1)).fetchone()
        if not row:
            return web.json_response({"error": "Setup not found"}, status=404)
        data = dict(row)
        # SQLite datetime('now') is UTC; compare in UTC as well (local time is UTC+5).
        if data["status"] == "pending" and data["expires_at"] < datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"):
            logger.info("ROOM_SETUP_EXPIRED setup_id=%s user_id=%s", data["id"], user["id"] if user else None)
            conn.execute("UPDATE room_setups SET status = 'expired' WHERE id = ?", (data["id"],)); conn.commit(); data["status"] = "expired"
        data["steps"] = {
            "botAdded": data.get("telegram_chat_id") is not None,
            "adminGranted": data.get("status") in ("bot_added", "awaiting_permissions", "completed"),
            "canInviteUsers": data.get("status") == "completed" and bool(data.get("invite_link")),
            "roomCreated": data.get("room_id") is not None,
            "inviteCreated": bool(data.get("invite_link")),
        }
        data["chat"] = {"id": data["telegram_chat_id"], "title": data.get("room_name")} if data.get("telegram_chat_id") else None
        data["room"] = {"id": data["room_id"], "name": data.get("room_name")} if data.get("room_id") else None
        data["error"] = ("Требуется выдать боту права администратора и разрешение приглашать пользователей." if data["status"] == "awaiting_permissions" else None)
        return web.json_response({"setup": data})
    finally:
        conn.close()


async def handle_room_setup_check(request):
    """Повторно подтверждает права бота через Telegram Bot API."""
    token = request.match_info.get("setup_id", "")
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        row = conn.execute("SELECT rs.*, g.name AS room_name FROM room_setups rs LEFT JOIN groups g ON g.id = rs.room_id WHERE rs.token = ? AND rs.created_by_user_id = ?", (token, user["id"] if user else -1)).fetchone()
        if not row:
            return web.json_response({"error": "Setup not found"}, status=404)
        data = dict(row)
        if not data.get("telegram_chat_id"):
            return web.json_response({"setup": data})
        if not BOT_TOKEN:
            return web.json_response({"error": "BOT_TOKEN не настроен"}, status=503)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10) as resp:
                me = await resp.json(content_type=None)
            bot_id = (me.get("result") or {}).get("id")
            async with session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember", json={"chat_id": data["telegram_chat_id"], "user_id": bot_id}, timeout=10) as resp:
                member_result = await resp.json(content_type=None)
        member = member_result.get("result") or {}
        can_invite = member.get("status") == "administrator" and bool(member.get("can_invite_users"))
        if member.get("status") != "administrator" or not can_invite:
            conn.execute("UPDATE room_setups SET status = 'awaiting_permissions' WHERE id = ?", (data["id"],)); conn.commit()
            return web.json_response({"ok": True, "status": "awaiting_permissions", "setup": {**data, "status": "awaiting_permissions"}})
        existing = get_group_by_chat_id(conn, data["telegram_chat_id"])
        room = existing or create_room(conn, data.get("room_name") or "Telegram группа", creator_user_id=data["created_by_user_id"], telegram_chat_id=data["telegram_chat_id"])
        conn.execute("INSERT OR IGNORE INTO group_members (group_id, user_id, role) VALUES (?, ?, 'creator')", (room["id"], data["created_by_user_id"]))
        invite_link, invite_error = await resolve_room_invite_link(data["telegram_chat_id"], bot_id, can_invite)
        conn.execute("UPDATE room_setups SET status = ?, room_id = ?, invite_link = ? WHERE id = ?", ("completed" if invite_link else "bot_added", room["id"], invite_link, data["id"]))
        conn.commit()
        return web.json_response({"ok": True, "status": "completed" if invite_link else "bot_added", "error": invite_error})
    finally:
        conn.close()


async def handle_notification_action(request):
    group_id = int(request.match_info["group_id"])
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user or not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden"}, status=403)
        notification_id = request.match_info.get("notification_id")
        if notification_id:
            ok = mark_notification_read(conn, int(notification_id), user["id"], group_id)
        else:
            mark_all_notifications_read(conn, user["id"], group_id)
            ok = True
        return web.json_response({"ok": ok})
    finally:
        conn.close()


# ─── REST API: СИСТЕМА ДОЛГОВ (DEBTS API) ────────────────────

async def handle_get_group_debts(request):
    """
    GET /api/group/{group_id}/debts
    Получение списка долгов группы с фильтрацией:
    - ?tab=i_owe | owed_to_me | all
    - ?status=active | partially_paid | paid | cancelled
    Строгая проверка прав доступа: пользователь обязан состоять в группе (403).
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой группе"}, status=403)

        tab = request.query.get("tab", "all")
        status = request.query.get("status")

        debts = get_group_debts(
            conn,
            group_id=group_id,
            user_id=user["id"] if user else None,
            filter_tab=tab,
            status=status
        )
        summary = get_debts_summary(conn, group_id, user["id"] if user else None)

        return web.json_response({
            "group_id": group_id,
            "tab": tab,
            "debts": debts,
            "summary": summary
        })
    finally:
        conn.close()


async def handle_get_debts_summary(request):
    """
    GET /api/group/{group_id}/debts/summary
    Финансовая сводка по долгам: totalIOwe, totalOwedToMe, activeDebtsCount, overdueDebtsCount.
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой группе"}, status=403)

        summary = get_debts_summary(conn, group_id, user["id"] if user else None)
        return web.json_response(summary)
    finally:
        conn.close()


async def handle_create_debt(request):
    """
    POST /api/group/{group_id}/debts
    Ручное создание долга в группе.
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой группе"}, status=403)

        data = await request.json()
        amount = float(data.get("amount", 0))
        if amount <= 0:
            return web.json_response({"error": "Сумма долга должна быть больше 0"}, status=400)
        if amount > 10_000_000:
            return web.json_response({"error": "Сумма долга слишком велика"}, status=400)

        # Mini App sends a direction + counterparty; normalize it to the DB contract.
        direction = data.get("direction", "owed_to_me")
        member_user_id = data.get("member_user_id")
        external_name = (data.get("external_name") or "").strip()
        current_user_id = user["id"] if user else None
        if not current_user_id:
            return web.json_response({"error": "Не удалось определить пользователя"}, status=401)
        creditor_user_id = data.get("creditor_user_id")
        creditor_name = (data.get("creditor_name") or "").strip()
        debtor_user_id = data.get("debtor_user_id")
        debtor_name = (data.get("debtor_name") or "").strip()

        if member_user_id is not None:
            member_user_id = int(member_user_id)
            member = conn.execute(
                "SELECT u.id, u.display_name FROM users u JOIN group_members gm ON gm.user_id = u.id WHERE gm.group_id = ? AND u.id = ?",
                (group_id, member_user_id),
            ).fetchone()
            if not member:
                return web.json_response({"error": "Участник не состоит в этой комнате"}, status=400)
            if direction == "i_owe":
                creditor_user_id, creditor_name = member_user_id, (member["display_name"] if member else external_name)
                debtor_user_id, debtor_name = current_user_id, user["display_name"] if user else "Я"
            else:
                creditor_user_id, creditor_name = current_user_id, user["display_name"] if user else "Я"
                debtor_user_id, debtor_name = member_user_id, (member["display_name"] if member else external_name)
        elif external_name:
            if direction == "i_owe":
                creditor_user_id, creditor_name = None, external_name
                debtor_user_id, debtor_name = current_user_id, user["display_name"] if user else "Я"
            else:
                creditor_user_id, creditor_name = current_user_id, user["display_name"] if user else "Я"
                debtor_user_id, debtor_name = None, external_name

        for selected_id, role in ((creditor_user_id, "кредитор"), (debtor_user_id, "должник")):
            if selected_id is not None:
                selected = conn.execute(
                    "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
                    (group_id, int(selected_id)),
                ).fetchone()
                if not selected:
                    return web.json_response({"error": f"Выбранный {role} не состоит в этой комнате"}, status=400)

        # Если указан creditor_user_id, проверяем его имя в группе
        if creditor_user_id:
            cu = get_user_by_id(conn, int(creditor_user_id))
            if cu:
                creditor_name = cu["display_name"]

        # Если указан debtor_user_id, проверяем его имя в группе
        if debtor_user_id:
            du = get_user_by_id(conn, int(debtor_user_id))
            if du:
                debtor_name = du["display_name"]

        if not creditor_name or not debtor_name:
            return web.json_response({"error": "Укажите имя должника и кредитора"}, status=400)

        # Нельзя быть должным самому себе
        if creditor_user_id and debtor_user_id and int(creditor_user_id) == int(debtor_user_id):
            return web.json_response({"error": "Кредитор и должник не могут быть одним лицом"}, status=400)

        due_datetime = data.get("due_datetime") or data.get("due_date")
        notification_frequency = str(data.get("notification_frequency", "none"))
        allowed_frequencies = {"none", "10_min", "30_min", "3_times_a_day", "daily", "every_3_days", "weekly", "custom"}
        if notification_frequency not in allowed_frequencies:
            return web.json_response({"error": "Некорректная частота напоминаний"}, status=400)
        custom_hours = data.get("custom_reminder_interval_hours")
        if custom_hours:
            custom_hours = int(custom_hours)
        custom_minutes = data.get("custom_reminder_interval_minutes")
        if custom_minutes:
            custom_minutes = int(custom_minutes)
        elif custom_hours and not custom_minutes:
            custom_minutes = custom_hours * 60
        if notification_frequency == "custom" and not custom_minutes:
            return web.json_response({"error": "Укажите интервал напоминаний"}, status=400)
        if custom_minutes and not 1 <= custom_minutes <= 43200:
            return web.json_response({"error": "Интервал напоминаний должен быть от 1 минуты до 30 дней"}, status=400)

        client_request_id = str(data.get("client_request_id") or "").strip()[:100] or None
        if client_request_id:
            existing = conn.execute(
                "SELECT id FROM debts WHERE group_id = ? AND created_by_user_id = ? AND client_request_id = ?",
                (group_id, current_user_id, client_request_id),
            ).fetchone()
            if existing:
                return web.json_response({"debt": get_debt_by_id(conn, existing["id"], group_id), "message": "Долг уже зафиксирован", "duplicate": True})

        debt = create_debt(
            conn=conn,
            group_id=group_id,
            creditor_user_id=int(creditor_user_id) if creditor_user_id else None,
            creditor_name=creditor_name,
            debtor_user_id=int(debtor_user_id) if debtor_user_id else None,
            debtor_name=debtor_name,
            amount=amount,
            description=data.get("description", ""),
            due_datetime=due_datetime,
            notification_frequency=notification_frequency,
            custom_reminder_interval_hours=custom_hours,
            custom_reminder_interval_minutes=custom_minutes,
            created_by_user_id=user["id"] if user else None,
            client_request_id=client_request_id,
        )

        if debtor_user_id and int(debtor_user_id) != int(user["id"] if user else -1):
            create_notification(
                conn, int(debtor_user_id), group_id, "debt_created",
                f"Новый долг: {amount:,.2f} ₽", (data.get("description") or "Вам выставлен долг"),
                "debt", debt["id"], event_key=f"debt_created:{debt['id']}:{debtor_user_id}"
            )

        return web.json_response({"debt": debt, "message": "Долг успешно создан"}, status=201)
    except sqlite3.IntegrityError:
        if 'client_request_id' in locals() and client_request_id:
            existing = conn.execute("SELECT id FROM debts WHERE group_id = ? AND created_by_user_id = ? AND client_request_id = ?", (group_id, current_user_id, client_request_id)).fetchone()
            if existing:
                return web.json_response({"debt": get_debt_by_id(conn, existing["id"], group_id), "message": "Долг уже зафиксирован", "duplicate": True})
        logger.exception("Debt creation integrity error")
        return web.json_response({"error": "Не удалось сохранить долг: проверьте данные участников"}, status=409)
    except Exception as e:
        logger.error(f"Error creating debt: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_get_debt_detail(request):
    """
    GET /api/group/{group_id}/debts/{debt_id}
    Детальная информация о долге и история выплат.
    """
    group_id_param = request.match_info.get("group_id")
    debt_id_param = request.match_info.get("debt_id")
    try:
        group_id = int(group_id_param)
        debt_id = int(debt_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid IDs"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой группе"}, status=403)

        debt = get_debt_by_id(conn, debt_id, group_id)
        if not debt:
            return web.json_response({"error": "Долг не найден"}, status=404)

        debt["can_manage_reminders"] = bool(user and int(user["id"]) in {
            int(debt.get("creditor_user_id") or 0), int(debt.get("created_by_user_id") or 0)
        })
        debt["can_pay"] = bool(user and int(debt.get("debtor_user_id") or 0) == int(user["id"]))
        return web.json_response({"debt": debt})
    finally:
        conn.close()


async def handle_update_debt_reminders(request):
    """Update an existing debt's reminders; only its creditor or creator may do so."""
    try:
        group_id = int(request.match_info.get("group_id"))
        debt_id = int(request.match_info.get("debt_id"))
        data = await request.json()
    except (TypeError, ValueError, json.JSONDecodeError):
        return web.json_response({"error": "Некорректные данные"}, status=400)

    frequency = str(data.get("notification_frequency", "none"))
    allowed = {"none", "10_min", "30_min", "3_times_a_day", "daily", "every_3_days", "weekly", "custom"}
    if frequency not in allowed:
        return web.json_response({"error": "Некорректная частота напоминаний"}, status=400)
    custom_minutes = data.get("custom_reminder_interval_minutes")
    try:
        custom_minutes = int(custom_minutes) if custom_minutes else None
    except (TypeError, ValueError):
        return web.json_response({"error": "Некорректный интервал"}, status=400)
    if frequency == "custom" and not custom_minutes:
        return web.json_response({"error": "Укажите интервал напоминаний"}, status=400)
    if custom_minutes and not 1 <= custom_minutes <= 43200:
        return web.json_response({"error": "Интервал должен быть от 1 минуты до 30 дней"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user or not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Нет доступа к комнате"}, status=403)
        debt = get_debt_by_id(conn, debt_id, group_id)
        if not debt:
            return web.json_response({"error": "Долг не найден"}, status=404)
        managers = {int(debt.get("creditor_user_id") or 0), int(debt.get("created_by_user_id") or 0)}
        if int(user["id"]) not in managers:
            return web.json_response({"error": "Настройки напоминаний меняет кредитор или создатель долга"}, status=403)
        updated = update_debt_reminder_preferences(conn, debt_id, frequency, custom_minutes)
        updated["can_manage_reminders"] = True
        return web.json_response({"debt": updated, "message": "Настройки напоминаний сохранены"})
    finally:
        conn.close()


async def handle_add_debt_payment(request):
    """
    POST /api/group/{group_id}/debts/{debt_id}/payments
    Внесение частичного платежа по долгу.
    """
    group_id_param = request.match_info.get("group_id")
    debt_id_param = request.match_info.get("debt_id")
    try:
        group_id = int(group_id_param)
        debt_id = int(debt_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid IDs"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user or not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Нет доступа к комнате"}, status=403)

        debt = get_debt_by_id(conn, debt_id, group_id)
        if not debt:
            return web.json_response({"error": "Долг не найден"}, status=404)
        if int(debt.get("debtor_user_id") or 0) != int(user["id"]):
            return web.json_response({"error": "Оплатить можно только долг, который вы должны"}, status=403)

        data = await request.json()
        amount = float(data.get("amount", 0))
        note = data.get("note", "")
        client_request_id = str(data.get("client_request_id") or "").strip()[:100] or None

        updated_debt = add_debt_payment(
            conn=conn,
            debt_id=debt_id,
            amount=amount,
            created_by_user_id=user["id"] if user else None,
            note=note,
            client_request_id=client_request_id,
        )
        event_type = "debt_paid" if updated_debt["status"] == "paid" else "debt_partially_paid"
        for recipient in (updated_debt.get("creditor_user_id"), updated_debt.get("debtor_user_id")):
            if recipient and int(recipient) != int(user["id"] if user else -1):
                create_notification(conn, int(recipient), group_id, event_type,
                    "Долг погашен" if event_type == "debt_paid" else "Частичное погашение долга",
                    f"Платёж {amount:,.2f} ₽ · осталось {updated_debt['remaining_amount']:,.2f} ₽",
                    "debt", debt_id, event_key=f"{event_type}:{debt_id}:{updated_debt['updated_at']}:{recipient}")

        return web.json_response({
            "debt": updated_debt,
            "message": f"Платёж на сумму {amount:,.0f} ₽ успешно внесён"
        })
    except ValueError as ve:
        return web.json_response({"error": str(ve)}, status=400)
    except Exception as e:
        logger.error(f"Error adding debt payment: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_mark_debt_paid(request):
    """
    POST /api/group/{group_id}/debts/{debt_id}/mark-paid
    Полное погашение долга в один клик.
    """
    group_id_param = request.match_info.get("group_id")
    debt_id_param = request.match_info.get("debt_id")
    try:
        group_id = int(group_id_param)
        debt_id = int(debt_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid IDs"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user or not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Нет доступа к комнате"}, status=403)

        debt = get_debt_by_id(conn, debt_id, group_id)
        if not debt:
            return web.json_response({"error": "Долг не найден"}, status=404)
        if int(debt.get("debtor_user_id") or 0) != int(user["id"]):
            return web.json_response({"error": "Оплатить можно только долг, который вы должны"}, status=403)

        updated_debt = mark_debt_paid(conn, debt_id, user["id"] if user else None)
        return web.json_response({
            "debt": updated_debt,
            "message": "Долг полностью закрыт!"
        })
    except ValueError as ve:
        return web.json_response({"error": str(ve)}, status=400)
    except Exception as e:
        logger.error(f"Error marking debt paid: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_cancel_debt(request):
    """
    POST /api/group/{group_id}/debts/{debt_id}/cancel
    Отмена долга.
    """
    group_id_param = request.match_info.get("group_id")
    debt_id_param = request.match_info.get("debt_id")
    try:
        group_id = int(group_id_param)
        debt_id = int(debt_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid IDs"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой группе"}, status=403)

        if not get_debt_by_id(conn, debt_id, group_id):
            return web.json_response({"error": "Долг не найден"}, status=404)

        cancelled_debt = cancel_debt(conn, debt_id, user["id"] if user else None)
        return web.json_response({
            "debt": cancelled_debt,
            "message": "Долг отменён"
        })
    except ValueError as ve:
        return web.json_response({"error": str(ve)}, status=400)
    except Exception as e:
        logger.error(f"Error cancelling debt: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()




# ─── ROOMS / КОМНАТЫ API ─────────────────────────────────────

async def handle_get_rooms(request):
    """
    GET /api/rooms
    Получить все доступные комнаты (Room) пользователя.
    """
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user:
            # Демо/анонимный фоллбэк на первого пользователя
            first_user = conn.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
            uid = first_user["id"] if first_user else 1
        else:
            uid = user["id"]

        rooms = get_user_rooms(conn, uid)
        return web.json_response({"rooms": rooms, "count": len(rooms)})
    finally:
        conn.close()


async def handle_create_room(request):
    """
    POST /api/rooms
    Создать новую комнату:
    - name: Название комнаты
    - type: one_time (разовый чек) | long_term (длительная)
    - currency: RUB | USD | EUR
    - members: список участников (ID или имена)
    """
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user:
            return web.json_response({"error": "Требуется авторизация Telegram"}, status=401)
        creator_id = user["id"]

        data = await request.json()
        name = data.get("name", "").strip()
        if not name:
            return web.json_response({"error": "Укажите название комнаты"}, status=400)

        room_type = data.get("room_type", data.get("type", "long_term"))
        currency = data.get("currency", "RUB")
        settlement_strategy = data.get("settlement_strategy", "min_transfers")
        if room_type not in ("one_time", "long_term") or currency not in ("RUB", "USD", "EUR", "KZT"):
            return web.json_response({"error": "Некорректные настройки комнаты"}, status=400)

        room = create_room(
            conn=conn,
            name=name,
            room_type=room_type,
            currency=currency,
            creator_user_id=creator_id,
            settlement_strategy=settlement_strategy,
        )
        return web.json_response({"room": room, "message": "Комната успешно создана"}, status=201)
    except Exception as e:
        logger.error(f"Error creating room: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


def _invite_link(token: str) -> str:
    bot_username = os.getenv("BOT_USERNAME", "Xakatonsberbot")
    return f"https://t.me/{bot_username}?start=invite_{token}"


async def handle_create_room_invite(request):
    group_id = int(request.match_info["group_id"])
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        room = get_group_by_id(conn, group_id)
        if not room:
            return web.json_response({"error": "Комната не найдена"}, status=404)
        if not user or not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Нет доступа к комнате"}, status=403)
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO room_invites (room_id, token, created_by_user_id, expires_at) VALUES (?, ?, ?, datetime('now', '+30 days'))", (group_id, token, user["id"]))
        conn.commit()
        return web.json_response({"token": token, "invite_link": _invite_link(token), "expires_at": conn.execute("SELECT expires_at FROM room_invites WHERE token = ?", (token,)).fetchone()[0]})
    finally:
        conn.close()


def _public_request_origin(request: web.Request) -> Optional[str]:
    """Return the HTTPS origin that Telegram can use to fetch a prepared invite image."""
    origin = request.headers.get("Origin", "").rstrip("/")
    if origin.startswith("https://"):
        return origin
    forwarded_host = request.headers.get("X-Forwarded-Host")
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
    if forwarded_host and forwarded_proto == "https":
        return f"https://{forwarded_host.split(',')[0].strip()}"
    return None


async def handle_invite_image(request):
    """Serve the approved visual used by Telegram's prepared room invite."""
    if not INVITE_IMAGE_PATH.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(INVITE_IMAGE_PATH, headers={"Cache-Control": "public, max-age=3600"})


async def handle_prepare_room_invite_share(request):
    """Create a native Telegram prepared message for the current Mini App user."""
    try:
        group_id = int(request.match_info["group_id"])
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid group_id"}, status=400)
    origin = _public_request_origin(request)
    if not origin:
        return web.json_response({"error": "Нативная отправка доступна только из HTTPS Mini App"}, status=400)
    if not BOT_TOKEN:
        return web.json_response({"error": "BOT_TOKEN не настроен"}, status=503)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user or not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Нет доступа к комнате"}, status=403)
        room = conn.execute("""
            SELECT g.id, g.name, creator.display_name AS creator_name
            FROM groups g LEFT JOIN users creator ON creator.id = g.created_by_user_id
            WHERE g.id = ?
        """, (group_id,)).fetchone()
        if not room:
            return web.json_response({"error": "Комната не найдена"}, status=404)

        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO room_invites (room_id, token, created_by_user_id, expires_at) VALUES (?, ?, ?, datetime('now', '+30 days'))",
            (group_id, token, user["id"]),
        )
        conn.commit()

        invite_url = _invite_link(token)
        result = {
            "type": "photo",
            "id": secrets.token_hex(12),
            "photo_url": f"{origin}/assets/sberwise-invite.png",
            "thumbnail_url": f"{origin}/assets/sberwise-invite.png",
            "caption": build_room_invite_caption(room["name"], room["creator_name"]),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [[{
                    "text": "🟢 Присоединиться к комнате",
                    "url": invite_url,
                }]],
            },
        }
        payload = {
            "user_id": user["telegram_id"],
            "result": result,
            "allow_user_chats": True,
            "allow_group_chats": True,
            "allow_channel_chats": False,
            "allow_bot_chats": False,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/savePreparedInlineMessage", json=payload, timeout=15) as response:
                telegram_result = await response.json(content_type=None)
        prepared_id = (telegram_result.get("result") or {}).get("id") if telegram_result.get("ok") else None
        if not prepared_id:
            conn.execute("DELETE FROM room_invites WHERE token = ? AND use_count = 0", (token,))
            conn.commit()
            logger.warning("PREPARED_INVITE_FAILED room_id=%s status=%s error=%s", group_id, telegram_result.get("error_code"), telegram_result.get("description"))
            return web.json_response({"error": "Telegram не смог подготовить приглашение"}, status=502)
        return web.json_response({"prepared_message_id": prepared_id})
    finally:
        conn.close()


async def handle_get_room_invite(request):
    token = request.match_info["token"]
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT ri.token, ri.expires_at, ri.max_uses, ri.use_count, g.id AS room_id, g.name AS room_name,
                   u.display_name AS creator_name,
                   (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) AS members_count
            FROM room_invites ri JOIN groups g ON g.id = ri.room_id JOIN users u ON u.id = ri.created_by_user_id
            WHERE ri.token = ?
        """, (token,)).fetchone()
        if not row:
            return web.json_response({"error": "Приглашение не найдено"}, status=404)
        invite = dict(row)
        expired = invite["expires_at"] and invite["expires_at"] < datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        exhausted = invite["max_uses"] is not None and invite["use_count"] >= invite["max_uses"]
        user = get_auth_user(request, conn)
        already_member = bool(user and is_user_group_member(conn, invite["room_id"], user["id"]))
        return web.json_response({"invite": invite, "valid": not expired and not exhausted, "already_member": already_member})
    finally:
        conn.close()


async def handle_join_room_invite(request):
    token = request.match_info["token"]
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user:
            return web.json_response({"error": "Требуется авторизация Telegram"}, status=401)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM room_invites WHERE token = ?", (token,)).fetchone()
            if not row:
                raise ValueError("Приглашение не найдено")
            invite = dict(row)
            if invite["expires_at"] and invite["expires_at"] < datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"):
                raise ValueError("Приглашение больше недействительно")
            if invite["max_uses"] is not None and invite["use_count"] >= invite["max_uses"]:
                raise ValueError("Лимит приглашения исчерпан")
            exists = conn.execute("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (invite["room_id"], user["id"])).fetchone()
            if not exists:
                conn.execute("INSERT INTO group_members (group_id, user_id, role) VALUES (?, ?, 'member')", (invite["room_id"], user["id"]))
                conn.execute("UPDATE room_invites SET use_count = use_count + 1 WHERE id = ?", (invite["id"],))
                members = get_group_members_users(conn, invite["room_id"])
                for member in members:
                    if member["id"] != user["id"]:
                        create_notification(conn, member["id"], invite["room_id"], "member_joined", "Новый участник", f"{user['display_name']} присоединился к комнате", "member", user["id"], event_key=f"member_joined:{invite['room_id']}:{user['id']}:{member['id']}")
            conn.commit()
            return web.json_response({"ok": True, "already_member": bool(exists), "room_id": invite["room_id"]})
        except ValueError as err:
            conn.rollback()
            return web.json_response({"error": str(err)}, status=400)
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()


async def handle_archive_room(request):
    """
    POST /api/group/{group_id}/archive
    Завершить / архивировать комнату.
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой комнате"}, status=403)

        archive_room(conn, group_id)
        settlement = calculate_room_settlement(conn, group_id, user["id"] if user else None)
        return web.json_response({
            "message": "Комната завершена",
            "status": "settled",
            "settlement": settlement
        })
    finally:
        conn.close()


async def handle_delete_room(request):
    """DELETE /api/rooms/{room_id}: creator-only, transactional room removal."""
    try:
        room_id = int(request.match_info.get("room_id"))
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid room_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user:
            return web.json_response({"error": "Требуется авторизация"}, status=401)
        room = conn.execute("SELECT id FROM groups WHERE id = ?", (room_id,)).fetchone()
        if not room:
            return web.json_response({"error": "Комната не найдена"}, status=404)
        if not user_can_delete_room(conn, room_id, user["id"]):
            return web.json_response({"error": "Удалить комнату может только её создатель"}, status=403)
        deleted = delete_room(conn, room_id)
        logger.info("ROOM_DELETED room_id=%s actor_id=%s", room_id, user["id"])
        return web.json_response({"ok": True, "deleted_room_id": room_id, "deleted": deleted})
    except LookupError:
        return web.json_response({"error": "Комната не найдена"}, status=404)
    except Exception:
        logger.exception("Failed to delete room room_id=%s", request.match_info.get("room_id"))
        return web.json_response({"error": "Не удалось удалить комнату"}, status=500)
    finally:
        conn.close()


async def handle_leave_room(request):
    """Remove only the authenticated participant from a room and their room-scoped inbox."""
    try:
        room_id = int(request.match_info.get("room_id"))
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid room_id"}, status=400)
    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if not user:
            return web.json_response({"error": "Требуется авторизация"}, status=401)
        member = conn.execute("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (room_id, user["id"])).fetchone()
        if not member:
            return web.json_response({"error": "Комната не найдена"}, status=404)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM notifications WHERE group_id = ? AND user_id = ?", (room_id, user["id"]))
        conn.execute("DELETE FROM notification_preferences WHERE group_id = ? AND user_id = ?", (room_id, user["id"]))
        conn.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (room_id, user["id"]))
        conn.commit()
        return web.json_response({"ok": True, "left_room_id": room_id})
    except Exception:
        conn.rollback()
        logger.exception("Failed to leave room room_id=%s", room_id)
        return web.json_response({"error": "Не удалось убрать комнату из списка"}, status=500)
    finally:
        conn.close()


# ─── DRAFT & MULTI-INPUT PIPELINES ───────────────────────────

async def handle_parse_text(request):
    """
    POST /api/group/{group_id}/parse/text
    AI парсинг произвольного текста (список покупок, сообщение из чата).
    Возвращает ParsedExpenseDraft с позициями и участниками.
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden"}, status=403)

        data = await request.json()
        text = data.get("text", "").strip()
        if not text:
            return web.json_response({"error": "Текст не может быть пустым"}, status=400)

        members = get_group_members_users(conn, group_id)
        draft = await parse_unstructured_expense_text(
            text=text,
            room_members=members,
            default_payer_id=user["id"] if user else None
        )
        return web.json_response({
            "draft": draft,
            "room_members": [
                {"id": member["id"], "name": member.get("member_display_name") or member.get("display_name") or "Участник"}
                for member in members
            ],
        })
    except Exception as e:
        logger.error(f"Error in handle_parse_text: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_parse_voice(request):
    """
    POST /api/group/{group_id}/parse/voice
    Принимает аудиозапись голоса, делает Speech-To-Text и формирует ParsedExpenseDraft.
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой комнате"}, status=403)

        reader = await request.multipart()
        audio_bytes = b""
        filename = "voice.webm"
        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name in ("voice", "audio", "file"):
                filename = part.filename or filename
                audio_bytes = await part.read()
                break

        # Валидация аудиофайла
        if not audio_bytes or len(audio_bytes) < 100:
            return web.json_response({"error": "Аудиозапись пуста или повреждена. Попробуйте записать снова."}, status=400)

        if len(audio_bytes) > 20 * 1024 * 1024:
            return web.json_response({"error": "Размер аудиофайла превышает лимит 20 МБ"}, status=413)

        members = get_group_members_users(conn, group_id)
        draft = await transcribe_and_parse_voice(
            audio_bytes=audio_bytes,
            room_members=members,
            default_payer_id=user["id"] if user else None,
            filename=filename
        )

        if draft.get("error"):
            return web.json_response(draft, status=400)

        if user and not draft.get("payer_id"):
            draft["payer_id"] = user["id"]

        return web.json_response({"draft": draft, "transcript": draft.get("transcription", "")})
    except Exception as e:
        logger.error(f"Error in handle_parse_voice: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_parse_receipt(request):
    """
    POST /api/group/{group_id}/parse/receipt
    Реальное распознавание позиций чека из изображения (OpenAI GPT-4o-mini Vision / QR ФНС).
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не являетесь участником этой комнаты"}, status=403)

        reader = await request.multipart()
        img_bytes = b""
        filename = ""
        mime_type = ""
        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name in ("photo", "receipt", "image", "file"):
                filename = part.filename or ""
                mime_type = part.headers.get("Content-Type", "").lower()
                img_bytes = await part.read()
                break

        if not img_bytes:
            return web.json_response({"error": "Файл изображения чека не передан"}, status=400)

        # Ограничение размера файла 15 МБ
        if len(img_bytes) > 15 * 1024 * 1024:
            return web.json_response({"error": "Размер файла превышает допустимый лимит 15 МБ"}, status=413)

        members = get_group_members_users(conn, group_id)
        logger.info("RECEIPT_UPLOAD_START group_id=%s bytes=%s mime=%s extension=%s", group_id, len(img_bytes), mime_type or "unknown", Path(filename).suffix.lower() or "unknown")
        try:
            draft = await asyncio.wait_for(parse_image_receipt_items(img_bytes, members), timeout=45)
        except asyncio.TimeoutError:
            logger.warning("RECEIPT_OCR_TIMEOUT group_id=%s", group_id)
            return web.json_response({"error": "Распознавание чека заняло слишком много времени", "code": "ocr_timeout"}, status=504)

        if draft.get("error"):
            return web.json_response({
                "error": draft.get("message", "Не удалось распознать чек"),
                "code": draft.get("error")
            }, status=422)

        if user:
            draft["payer_id"] = user["id"]
        return web.json_response({"draft": draft})
    except Exception as e:
        logger.error(f"Error in handle_parse_receipt: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_parse_document(request):
    """
    POST /api/group/{group_id}/parse/document
    Парсинг электронного чека / бронирования (PDF / CSV).
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden"}, status=403)

        reader = await request.multipart()
        doc_bytes = b""
        filename = "document.pdf"
        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name in ("document", "file", "pdf", "csv"):
                filename = part.filename or filename
                doc_bytes = await part.read()
                break

        if not doc_bytes:
            return web.json_response({"error": "Файл документа не передан"}, status=400)
        if len(doc_bytes) > 20 * 1024 * 1024:
            return web.json_response({"error": "Размер документа превышает 20 МБ"}, status=413)
        if not filename.lower().endswith((".pdf", ".csv")):
            return web.json_response({"error": "Поддерживаются только PDF и CSV"}, status=415)

        members = get_group_members_users(conn, group_id)
        draft = parse_document_receipt(doc_bytes, filename, members)
        if draft.get("error"):
            return web.json_response({"error": draft.get("message", "Не удалось распознать документ"), "code": draft["error"]}, status=422)
        # When an AI provider is configured, use the same text normalizer as Text Input.
        # The deterministic PDF extraction remains the fallback for offline operation.
        extracted_text = draft.get("extracted_text")
        if extracted_text and (OPENAI_API_KEY or GEMINI_API_KEY):
            try:
                normalized = await parse_unstructured_expense_text(extracted_text, members, user["id"] if user else None)
                if normalized.get("items") and normalized.get("total_amount", 0) > 0:
                    normalized["source_type"] = draft.get("source_type", "pdf")
                    normalized["extracted_text"] = extracted_text
                    draft = normalized
            except Exception as ai_err:
                logger.warning("Document AI normalization failed; using extracted PDF data: %s", ai_err)
        if user:
            draft["payer_id"] = user["id"]
        logger.info("RECEIPT_UPLOAD_DONE group_id=%s items=%s confidence=%s", group_id, len(draft.get("items", [])), draft.get("confidence", 0))
        return web.json_response({"draft": draft})
    except Exception as e:
        logger.error(f"Error in handle_parse_document: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


async def handle_add_expense_itemized(request):
    """
    POST /api/group/{group_id}/expense/itemized
    Подтверждение и сохранение расхода с детальными позициями (ExpenseItems)
    и индивидуальным распределением участников.
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой комнате"}, status=403)

        try:
            require_active_room_members(conn, group_id)
        except RoomNeedsMoreMembersError as err:
            return web.json_response({"error": str(err), "code": "ROOM_NEEDS_MEMBERS"}, status=409)

        data = await request.json()
        title = (data.get("title") or "Расход").strip()
        items = data.get("items", [])
        payer_id = data.get("payer_id") or (user["id"] if user else None)
        if not payer_id:
            first_m = conn.execute("SELECT user_id FROM group_members WHERE group_id = ? LIMIT 1", (group_id,)).fetchone()
            payer_id = first_m["user_id"] if first_m else 1

        source_type = data.get("source_type", "manual")
        category = data.get("category")
        currency = data.get("currency", "RUB")

        res = add_expense_itemized(
            conn=conn,
            group_id=group_id,
            payer_id=int(payer_id),
            title=title,
            items=items,
            source_type=source_type,
            category=category,
            currency=currency,
        )
        attachment = data.get("attachment") or {}
        if attachment.get("filename"):
            conn.execute(
                "INSERT INTO expense_attachments (group_id, expense_id, file_name, file_path, mime_type, file_size) VALUES (?, ?, ?, ?, ?, ?)",
                (group_id, res["id"], str(attachment["filename"])[:255], attachment.get("file_path"), attachment.get("file_type"), int(attachment.get("file_size") or 0)),
            )
            conn.commit()
        return web.json_response({"expense": res, "message": "Расход успешно сохранён в комнату"}, status=201)
    except Exception as e:
        logger.error(f"Error in handle_add_expense_itemized: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


# ─── ИТОГИ КОМНАТЫ И СВОДКА В TELEGRAM ────────────────────────

async def handle_get_room_settlement(request):
    """
    GET /api/group/{group_id}/settlement/detail
    Детальные «Итоги комнаты» — личный результат (+X / -X), оптимизированный список переводов.
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden: Вы не состоите в этой комнате"}, status=403)

        settlement = calculate_room_settlement(
            conn=conn,
            group_id=group_id,
            current_user_id=user["id"] if user else None
        )
        return web.json_response(settlement)
    finally:
        conn.close()


async def handle_send_settlement_to_telegram(request):
    """
    POST /api/group/{group_id}/settlement/send-telegram
    Публикация красивой финансовой сводки в Telegram-чат группы.
    """
    group_id_param = request.match_info.get("group_id")
    try:
        group_id = int(group_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid group_id"}, status=400)

    conn = get_db()
    try:
        user = get_auth_user(request, conn)
        if user and not is_user_group_member(conn, group_id, user["id"]):
            return web.json_response({"error": "Forbidden"}, status=403)

        group = get_group_by_id(conn, group_id)
        if not group or not group.get("telegram_chat_id"):
            return web.json_response({"error": "Комната не привязана к чату Telegram"}, status=400)

        settlement = calculate_room_settlement(conn, group_id, user["id"] if user else None)
        room_name = group.get("name", "Комната")
        total_spent = settlement.get("total_expenses", 0.0)
        transfers = settlement.get("transfers", [])

        # This payload is intentionally generated from the same settlement object
        # as the Mini App, so figures and transfers cannot diverge between views.
        room_label = html.escape(str(room_name))
        lines = [f"<b>💸 Итоги комнаты</b>", f"«{room_label}»", "", f"Потрачено: <b>{total_spent:,.0f} ₽</b>"]
        if transfers:
            transfers_total = sum(float(item.get("amount") or 0) for item in transfers)
            lines.extend(["", f"К закрытию: <b>{len(transfers)} перевода · {transfers_total:,.0f} ₽</b>", "", "<b>Кому перевести</b>"])
            for index, transfer in enumerate(transfers, 1):
                from_name = html.escape(str(transfer.get("from_name") or "Участник"))
                to_name = html.escape(str(transfer.get("to_name") or "Участник"))
                lines.append(f"{index}. <b>{from_name}</b> → <b>{to_name}</b> — {float(transfer.get('amount') or 0):,.0f} ₽")
        else:
            lines.extend(["", "🎉 <b>Все взаиморасчёты закрыты</b>", "Переводов для этой комнаты сейчас нет."])
        lines.extend(["", f"<i>Обновлено {datetime.now().strftime('%d.%m · %H:%M')}</i>"])
        text = "\n".join(lines)

        # Отправляем через Telegram Bot API
        if BOT_TOKEN:
            async with aiohttp.ClientSession() as session:
                base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
                payload = {"chat_id": group["telegram_chat_id"], "text": text, "parse_mode": "HTML"}
                previous_message_id = group.get("settlement_message_id")
                if previous_message_id:
                    edit_payload = {**payload, "message_id": previous_message_id}
                    async with session.post(f"{base_url}/editMessageText", json=edit_payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        result = await resp.json(content_type=None)
                        if resp.status == 200 or "message is not modified" in str(result).lower():
                            return web.json_response({"success": True, "updated": True, "message": "Сводка в Telegram обновлена"})
                        logger.info("Settlement message update unavailable; sending a new one: %s", result)
                async with session.post(f"{base_url}/sendMessage", json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    result = await resp.json(content_type=None)
                    if resp.status != 200 or not result.get("ok"):
                        logger.warning("Telegram settlement send error: %s", result)
                        return web.json_response({"error": "Не удалось доставить сообщение в Telegram чат"}, status=502)
                    message_id = result.get("result", {}).get("message_id")
                    if message_id:
                        set_group_settlement_message_id(conn, group_id, message_id)

        return web.json_response({"success": True, "updated": False, "message": "Сводка отправлена в чат Telegram"})
    except Exception as e:
        logger.error(f"Error sending settlement to telegram: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
    finally:
        conn.close()


def create_web_app():
    """Создать и сконфигурировать aiohttp Application."""
    app = web.Application(
        middlewares=[request_logger_middleware, cors_middleware],
        client_max_size=35 * 1024 * 1024  # 35 MB upload limit for voice / OCR (Section 37)
    )

    # Health & Readiness Endpoints (Section 7, 8)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/ready", handle_ready)
    app.router.add_get("/api/ready", handle_ready)

    # CORS & JSON API
    app.router.add_get("/api/groups", handle_get_user_groups)
    app.router.add_get("/api/group/{group_id}/summary", handle_group_summary)
    app.router.add_get("/api/group/{group_id}/analytics", handle_get_group_analytics)
    app.router.add_get("/api/rooms/{group_id}/analytics", handle_get_group_analytics)
    app.router.add_get("/api/group/{group_id}/plan", handle_get_group_plan)
    app.router.add_post("/api/group/{group_id}/plan/category-budget", handle_set_category_budget)
    app.router.add_post("/api/group/{group_id}/plan/recurring", handle_create_recurring_expense)
    app.router.add_delete("/api/group/{group_id}/plan/recurring/{recurring_id}", handle_delete_recurring_expense)
    app.router.add_post("/api/group/{group_id}/expense", handle_add_expense)
    app.router.add_post("/api/group/{group_id}/settle", handle_settle_debt)
    app.router.add_post("/api/group/{group_id}/budget", handle_update_budget)
    app.router.add_post("/api/group/{group_id}/reset", handle_reset_month)

    # Debts System API
    app.router.add_get("/api/group/{group_id}/notifications", handle_get_notifications)
    app.router.add_post("/api/group/{group_id}/member-import-requests", handle_request_telegram_members)
    app.router.add_get("/api/group/{group_id}/member-import-requests/{request_id}", handle_get_telegram_member_request)
    app.router.add_post("/api/room-setups", handle_create_room_setup)
    app.router.add_get("/api/room-setups/{setup_id}", handle_room_setup_status)
    app.router.add_post("/api/room-setups/{setup_id}/check", handle_room_setup_check)
    app.router.add_post("/api/room-setups/{setup_id}/invite", handle_room_setup_check)
    app.router.add_post("/api/group/{group_id}/notifications/{notification_id}/read", handle_notification_action)
    app.router.add_post("/api/group/{group_id}/notifications/read-all", handle_notification_action)
    app.router.add_get("/api/group/{group_id}/debts", handle_get_group_debts)
    app.router.add_get("/api/group/{group_id}/debts/summary", handle_get_debts_summary)
    app.router.add_get("/api/group/{group_id}/debts/{debt_id}", handle_get_debt_detail)
    app.router.add_post("/api/group/{group_id}/debts", handle_create_debt)
    app.router.add_post("/api/group/{group_id}/debts/{debt_id}/reminders", handle_update_debt_reminders)
    app.router.add_post("/api/group/{group_id}/debts/{debt_id}/payment", handle_add_debt_payment)
    app.router.add_post("/api/group/{group_id}/debts/{debt_id}/pay", handle_mark_debt_paid)
    app.router.add_post("/api/group/{group_id}/debts/{debt_id}/cancel", handle_cancel_debt)

    # Auth & User API
    app.router.add_get("/api/auth/telegram", handle_auth_telegram)
    app.router.add_post("/api/auth/telegram", handle_auth_telegram)

    # Room & Multi-Room API
    app.router.add_get("/api/rooms", handle_get_rooms)
    app.router.add_post("/api/rooms", handle_create_room)
    app.router.add_post("/api/rooms/{group_id}/invites", handle_create_room_invite)
    app.router.add_post("/api/rooms/{group_id}/invite-delivery-requests", handle_request_room_invite_delivery)
    app.router.add_post("/api/rooms/{group_id}/prepared-invites", handle_prepare_room_invite_share)
    app.router.add_get("/api/invites/{token}", handle_get_room_invite)
    app.router.add_post("/api/invites/{token}/join", handle_join_room_invite)
    app.router.add_get("/api/rooms/{group_id}", handle_group_summary)
    app.router.add_get("/api/rooms/{group_id}/dashboard", handle_group_summary)
    app.router.add_get("/api/rooms/{group_id}/summary", handle_group_summary)
    app.router.add_get("/api/rooms/{group_id}/budget", handle_group_summary)
    app.router.add_get("/api/rooms/{group_id}/settlement", handle_get_room_settlement)
    app.router.add_get("/api/rooms/{group_id}/debts", handle_get_group_debts)
    app.router.add_get("/api/rooms/{group_id}/expenses", handle_get_room_expenses)
    app.router.add_delete("/api/rooms/{room_id}", handle_delete_room)
    app.router.add_delete("/api/rooms/{room_id}/membership", handle_leave_room)
    app.router.add_post("/api/group/{group_id}/archive", handle_archive_room)

    # Multi-Input & ParsedExpenseDraft API
    app.router.add_post("/api/group/{group_id}/parse/text", handle_parse_text)
    app.router.add_post("/api/group/{group_id}/parse/voice", handle_parse_voice)
    app.router.add_post("/api/group/{group_id}/parse/receipt", handle_parse_receipt)
    app.router.add_post("/api/group/{group_id}/parse/document", handle_parse_document)
    app.router.add_post("/api/group/{group_id}/expense/itemized", handle_add_expense_itemized)

    # Room Settlement & Telegram Summary API
    app.router.add_get("/api/group/{group_id}/settlement/detail", handle_get_room_settlement)
    app.router.add_post("/api/group/{group_id}/settlement/send-telegram", handle_send_settlement_to_telegram)

    # Mini App Frontend
    app.router.add_get("/assets/sberwise-invite.png", handle_invite_image)
    app.router.add_get("/webapp", handle_webapp_index)
    app.router.add_get("/", handle_webapp_index)
    app.router.add_static("/", path=WEBAPP_DIR, name="static")

    return app


async def start_web_server(port: int = 8080):
    """Запуск сервера в фоновом режиме."""
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 WebApp сервер запущен на http://localhost:{port}/webapp")
    return runner
