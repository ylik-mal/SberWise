"""
Telegram-бот для трекинга общих расходов с AI-аналитикой.
Кейс 3: Альтернативный Скоринг (Telegram-аналитика) — Сбер
"""

import asyncio
import io
import logging
import re
import secrets
import html
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, Router, F
from receipt_parser import parse_pdf_receipt, parse_image_receipt
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    BufferedInputFile,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    WebAppInfo,
    MenuButtonWebApp,
    UsersShared,
    ChatMemberUpdated,
)
from aiogram.enums import ParseMode
from aiogram.utils.backoff import BackoffConfig

from config import BOT_TOKEN, WEBAPP_PORT, WEBAPP_URL, CATEGORIES, IS_PRODUCTION_DEPLOYMENT, APP_VERSION
from ai_module import transcribe_and_parse_voice
from database import (
    calculate_room_settlement, add_expense_itemized, get_expense_items,
    RoomNeedsMoreMembersError,
    init_db,
    get_db,
    get_or_create_user,
    get_or_create_group,
    add_member_to_group,
    add_expense,
    get_group_balances,
    get_group_expenses,
    get_category_totals,
    get_user_by_id,
    get_user_by_telegram_id,
    get_group_members_users,
    simplify_debts,
    add_settlement,
    get_user_expense_count,
    get_group_budget_limit,
    set_group_budget_limit,
    set_reminder_interval,
    get_reminder_interval,
    update_last_reminder_at,
    get_all_groups_with_reminders,
    reset_group_expenses,
    get_user_groups,
    is_user_group_member,
    get_group_by_id,
    get_group_by_chat_id,
    migrate_group_chat_id,
    create_debt,
    get_debt_by_id,
    get_group_debts,
    add_debt_payment,
    mark_debt_paid,
    cancel_debt,
    get_debts_summary,
    get_pending_debt_reminders,
    claim_due_debt_reminder,
    update_debt_reminder_schedule,
    update_debt_reminder_preferences,
    calculate_next_reminder,
    create_room,
)
from scoring_engine import calculate_budget_forecast
from ai_module import (
    categorize_expense,
    generate_spending_tips,
    generate_debt_reminder,
    calculate_reliability_description,
    get_ai_engine_status,
    generate_ai_digest,
)
from charts import create_pie_chart, create_balance_chart
from web_server import start_web_server
from scoring_engine import calculate_comprehensive_score, calculate_budget_forecast
from tunnel import start_tunnel, stop_tunnel, get_public_url, set_on_url_change
from invite_message import build_room_invite_caption

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()
INVITE_IMAGE_PATH = Path(__file__).resolve().parents[2] / "дизайн.png"


@router.my_chat_member()
async def handle_bot_membership_update(event: ChatMemberUpdated):
    new_status = getattr(event.new_chat_member, "status", "unknown")
    logger.info("MY_CHAT_MEMBER_RECEIVED chat_id=%s chat_type=%s status=%s from_user=%s", event.chat.id, event.chat.type, new_status, event.from_user.id if event.from_user else None)
    if event.chat.type not in ("group", "supergroup") or new_status not in ("member", "administrator"):
        return
    conn = get_db()
    try:
        creator = get_user_by_telegram_id(conn, event.from_user.id) if event.from_user else None
        if not creator:
            return
        setup = conn.execute("SELECT * FROM room_setups WHERE created_by_user_id = ? AND status = 'pending' AND expires_at >= datetime('now') ORDER BY id DESC LIMIT 1", (creator["id"],)).fetchone()
        if setup:
            conn.execute("UPDATE room_setups SET status = 'bot_added', telegram_chat_id = ? WHERE id = ?", (event.chat.id, setup["id"]))
            conn.commit()
            logger.info("ROOM_SETUP_CORRELATED update_type=my_chat_member chat_id=%s setup_id=%s", event.chat.id, setup["id"])
    finally:
        conn.close()


# ─── Утилиты ──────────────────────────────────────────────────

def ensure_user_and_group(message: Message):
    """Зарегистрировать пользователя и группу."""
    conn = get_db()
    display_name = message.from_user.full_name or message.from_user.username or "Аноним"
    user = get_or_create_user(
        conn,
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
        display_name=display_name,
    )

    group = None
    if message.chat.type in ("group", "supergroup"):
        group = get_or_create_group(
            conn,
            chat_id=message.chat.id,
            name=message.chat.title or "Группа",
        )
        add_member_to_group(conn, group["id"], user["id"])

    return user, group, conn


def get_current_webapp_url(group_id: int | None = None) -> str:
    """Возвращает актуальный URL Mini App (единый источник правды, Section 11)."""
    # 1. Если задан WEBAPP_URL в конфиге и он начинается с https://
    if WEBAPP_URL and WEBAPP_URL.lower().startswith("https://"):
        base = WEBAPP_URL
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}group_id={group_id}" if group_id else base

    # 2. Локальная разработка: опрос активного SSH-туннеля
    pub_url = get_public_url()
    if pub_url and pub_url.lower().startswith("https://"):
        return f"{pub_url}/webapp?group_id={group_id}" if group_id else f"{pub_url}/webapp"

    # 3. Базовый локальный URL
    base = WEBAPP_URL or f"http://localhost:{WEBAPP_PORT}/webapp"
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}group_id={group_id}" if group_id else base


def get_webapp_keyboard(group_id: int = 1, button_text: str = "SberWise — ваш умный помощник", is_private: bool = False):
    """
    Генерация кнопки Mini App:
    - В ЛС: нативный web_app=WebAppInfo (открывается во всплывающем окне Telegram Mini App)
    - В группах: кнопка прямого запуска окна Telegram Mini App + ссылка на веб
    """
    current_url = get_current_webapp_url(None if is_private else group_id)
    if not current_url.lower().startswith("https://"):
        # Если туннель ещё стартует, даём deeplink-кнопку в бота вместо пустоты
        btn_bot = InlineKeyboardButton(text=button_text, url="https://t.me/Xakatonsberbot?start=app")
        return InlineKeyboardMarkup(inline_keyboard=[[btn_bot]])

    if is_private:
        btn = InlineKeyboardButton(text=button_text, web_app=WebAppInfo(url=current_url))
        return InlineKeyboardMarkup(inline_keyboard=[[btn]])
    else:
        # В группах Telegram не разрешает inline web_app кнопки, поэтому даём кнопку в бота и прямую ссылку
        btn_bot = InlineKeyboardButton(text=button_text, url=f"https://t.me/Xakatonsberbot?start=app_{group_id}")
        btn_web = InlineKeyboardButton(text="🌐 Открыть в браузере", url=current_url)
        return InlineKeyboardMarkup(inline_keyboard=[[btn_bot], [btn_web]])


async def send_room_invite_message(bot: Bot, chat_id: int, room_id: int, invite_token: str, room_name: str, creator_name: str | None = None) -> str | None:
    """Deliver a styled invite; photo failures fall back to an equivalent text message."""
    bot_username = "Xakatonsberbot"
    invite_url = f"https://t.me/{bot_username}?start=invite_{invite_token}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🟢 Присоединиться к комнате", url=invite_url)
    ]])
    caption = build_room_invite_caption(room_name, creator_name)

    try:
        if not INVITE_IMAGE_PATH.is_file():
            raise FileNotFoundError(str(INVITE_IMAGE_PATH))
        await bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(INVITE_IMAGE_PATH, filename="sberwise-invite.png"),
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return "photo"
    except Exception as photo_error:
        logger.warning("INVITE_MESSAGE_PHOTO_FALLBACK chat_id=%s reason=%s", chat_id, photo_error)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
            return "text"
        except Exception as message_error:
            logger.warning("INVITE_MESSAGE_DELIVERY_FAILED chat_id=%s reason=%s", chat_id, message_error)
            return None


# ─── /start ───────────────────────────────────────────────────

def mark_user_started(user_id: int):
    """Persist /start state without delaying Telegram's welcome message."""
    conn = get_db()
    try:
        conn.execute("UPDATE users SET access_status = 'active', has_started_bot = 1 WHERE id = ?", (user_id,))
        conn.execute("UPDATE group_members SET status = 'active' WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception as exc:
        logger.warning("Не удалось обновить статус /start для user_id=%s: %s", user_id, exc)
    finally:
        conn.close()

def register_private_start(telegram_id: int, username: str, display_name: str):
    """Do the non-urgent /start bookkeeping away from Telegram's response path."""
    conn = get_db()
    try:
        user = get_or_create_user(conn, telegram_id=telegram_id, username=username, display_name=display_name)
        conn.execute("UPDATE users SET access_status = 'active', has_started_bot = 1 WHERE id = ?", (user["id"],))
        conn.execute("UPDATE group_members SET status = 'active' WHERE user_id = ?", (user["id"],))
        conn.commit()
    except Exception as exc:
        logger.warning("Не удалось зарегистрировать личный /start для telegram_id=%s: %s", telegram_id, exc)
    finally:
        conn.close()

def build_start_welcome(first_name: str) -> str:
    return (
        f"Привет, {html.escape(first_name or 'друг')}!\n\n"
        "<b>Я SberWise — бот, который берёт на себя все разговоры о деньгах.</b>\n\n"
        "Скинулись на ужин? Разделю. Кто-то должен? Мягко напомню. "
        "Забыли, кто платил? Восстановлю.\n\n"
        "Вы просто проводите время. Деньги — моя забота."
    )

@router.message(CommandStart())
async def cmd_start(message: Message):
    args = (message.text or "").split()

    # A usual personal /start must never wait for SQLite. The Mini App resolves
    # the room after opening, while user registration continues in the background.
    if message.chat.type == "private" and not (len(args) > 1 and args[1].startswith("invite_")):
        first_name = (message.from_user.first_name if message.from_user else "") or "друг"
        display_name = (message.from_user.full_name if message.from_user else "") or (message.from_user.username if message.from_user else "") or "Аноним"
        if message.from_user:
            asyncio.create_task(asyncio.to_thread(
                register_private_start,
                message.from_user.id,
                message.from_user.username or "",
                display_name,
            ))
        await message.answer(
            build_start_welcome(first_name),
            parse_mode=ParseMode.HTML,
            reply_markup=get_webapp_keyboard(1, "🟢 SberWise — ваш умный помощник", is_private=True),
        )
        return

    user, group, conn = ensure_user_and_group(message)
    asyncio.create_task(asyncio.to_thread(mark_user_started, int(user["id"])))

    # Поддержка deep link /start app_1
    if len(args) > 1 and args[1].startswith("setup_") and group and message.chat.type in ("group", "supergroup"):
        setup_token = args[1][6:]
        logger.info("GROUP_START_RECEIVED chat_id=%s chat_type=%s title=%s setup_token=%s...", message.chat.id, message.chat.type, message.chat.title, setup_token[:6])
        setup = conn.execute("SELECT * FROM room_setups WHERE token = ? AND status = 'pending' AND expires_at >= datetime('now')", (setup_token,)).fetchone()
        if setup:
            conn.execute("UPDATE room_setups SET status = 'bot_added', telegram_chat_id = ? WHERE id = ?", (message.chat.id, setup["id"]))
            conn.commit()
            try:
                bot_member = await message.bot.get_chat_member(message.chat.id, message.bot.id)
                can_invite = bot_member.status == "administrator" and bool(getattr(bot_member, "can_invite_users", False))
            except Exception as perm_err:
                logger.warning("BOT_PERMISSIONS_CHECK failed chat_id=%s: %s", message.chat.id, perm_err)
                can_invite = False
            if not can_invite:
                conn.execute("UPDATE room_setups SET status = 'awaiting_permissions' WHERE id = ?", (setup["id"]))
                conn.commit()
                await message.answer("SberWise уже добавлен, но ему нужно право администратора на приглашение пользователей. Выдайте право и вернитесь в Mini App.")
                conn.close()
                return
            existing = get_group_by_chat_id(conn, message.chat.id)
            room = existing or create_room(conn, message.chat.title or "Telegram группа", creator_user_id=setup["created_by_user_id"], telegram_chat_id=message.chat.id)
            conn.execute("INSERT OR IGNORE INTO group_members (group_id, user_id, role) VALUES (?, ?, 'creator')", (room["id"], setup["created_by_user_id"]))
            invite_link = None
            try:
                invite = await message.bot.create_chat_invite_link(message.chat.id, name="SberWise invite")
                invite_link = invite.invite_link
            except Exception as invite_err:
                logger.warning("Не удалось создать invite link для setup: %s", invite_err)
            conn.execute("UPDATE room_setups SET status = 'completed', telegram_chat_id = ?, room_id = ?, invite_link = ? WHERE id = ?", (message.chat.id, room["id"], invite_link, setup["id"]))
            conn.commit()
            await message.answer("✅ SberWise подключён к этой группе и комната создана." + (f"\nПриглашение: {invite_link}" if invite_link else "\nНужны права администратора для создания ссылки-приглашения."))
            conn.close()
            return
    if len(args) > 1 and args[1].startswith("invite_") and message.chat.type == "private":
        invite_token = args[1][7:]
        invite = conn.execute("""
            SELECT ri.token, ri.expires_at, g.name FROM room_invites ri
            JOIN groups g ON g.id = ri.room_id WHERE ri.token = ?
        """, (invite_token,)).fetchone()
        if not invite or (invite["expires_at"] and invite["expires_at"] < datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")):
            conn.close()
            await message.answer("Это приглашение недействительно или уже истекло.")
            return
        webapp_url = get_current_webapp_url(None)
        separator = "&" if "?" in webapp_url else "?"
        invite_url = f"{webapp_url}{separator}invite={invite_token}"
        conn.close()
        await message.answer(
            f"Вас пригласили в комнату «{invite['name']}».\nОткройте Mini App, чтобы проверить приглашение и подтвердить вступление.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть приглашение", web_app=WebAppInfo(url=invite_url))]])
        )
        return
    target_group_id = group["id"] if group else None
    if len(args) > 1 and args[1].startswith("app_"):
        try:
            target_group_id = int(args[1].split("_")[1])
        except (ValueError, IndexError):
            pass

    if not target_group_id:
        user_groups = get_user_groups(conn, user["id"])
        target_group_id = user_groups[0]["id"] if user_groups else 1

    conn.close()

    first_name = (message.from_user.first_name if message.from_user else "") or user["display_name"] or "друг"
    await message.answer(
        build_start_welcome(first_name),
        parse_mode=ParseMode.HTML,
        reply_markup=get_webapp_keyboard(
            target_group_id if message.chat.type == "private" else group["id"],
            "🟢 SberWise — ваш умный помощник",
            is_private=message.chat.type == "private",
        ),
    )


@router.message(Command("connect"))
async def cmd_connect(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Команду /connect нужно отправить в Telegram-группе.")
        return
    parts = (message.text or "").split(maxsplit=1)
    code = parts[1].strip().upper() if len(parts) > 1 else ""
    conn = get_db()
    try:
        sender = get_user_by_telegram_id(conn, message.from_user.id) if message.from_user else None
        setup = conn.execute("SELECT * FROM room_setups WHERE connect_code = ? AND status != 'completed' AND expires_at >= datetime('now')", (code,)).fetchone()
        if not setup or not sender or sender["id"] != setup["created_by_user_id"]:
            await message.answer("Код подключения недействителен, истёк или принадлежит другому пользователю.")
            return
        conn.execute("UPDATE room_setups SET status = 'bot_added', telegram_chat_id = ? WHERE id = ?", (message.chat.id, setup["id"]))
        conn.commit()
        logger.info("MANUAL_CONNECT setup_id=%s chat_id=%s from_user=%s", setup["id"], message.chat.id, message.from_user.id if message.from_user else None)
        await message.answer("✅ Группа подключена к SberWise.\nПроверяю права и создаю комнату…")
    finally:
        conn.close()


@router.message(F.users_shared)
async def handle_users_shared(message: Message):
    """Handle Telegram's native picker for either member import or invite delivery."""
    shared = message.users_shared
    conn = get_db()
    try:
        actor = get_or_create_user(conn, message.from_user.id, message.from_user.username, message.from_user.full_name)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS room_invite_delivery_requests (
                request_id INTEGER PRIMARY KEY,
                room_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                requested_by_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'pending',
                invite_token TEXT REFERENCES room_invites(token),
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            )
        """)
        delivery = conn.execute("""
            SELECT * FROM room_invite_delivery_requests
            WHERE request_id = ? AND requested_by_user_id = ? AND status = 'pending'
        """, (shared.request_id, actor["id"])).fetchone()
        if delivery:
            room = conn.execute("""
                SELECT g.id, g.name, u.display_name AS creator_name
                FROM groups g LEFT JOIN users u ON u.id = g.created_by_user_id
                WHERE g.id = ?
            """, (delivery["room_id"],)).fetchone()
            if not room:
                conn.execute("UPDATE room_invite_delivery_requests SET status = 'failed', completed_at = datetime('now') WHERE request_id = ?", (shared.request_id,))
                conn.commit()
                await message.answer("Комната больше недоступна. Откройте приглашение заново.")
                return

            invite_token = delivery["invite_token"]
            if not invite_token:
                invite_token = secrets.token_urlsafe(32)
                conn.execute(
                    "INSERT INTO room_invites (room_id, token, created_by_user_id, expires_at) VALUES (?, ?, ?, datetime('now', '+30 days'))",
                    (room["id"], invite_token, actor["id"]),
                )
                conn.execute("UPDATE room_invite_delivery_requests SET invite_token = ? WHERE request_id = ?", (invite_token, shared.request_id))
            conn.commit()

            delivered = 0
            unavailable = 0
            for picked in shared.users:
                result = await send_room_invite_message(
                    message.bot,
                    int(picked.user_id),
                    room["id"],
                    invite_token,
                    room["name"],
                    room["creator_name"],
                )
                if result:
                    delivered += 1
                else:
                    unavailable += 1
            conn.execute("UPDATE room_invite_delivery_requests SET status = 'completed', completed_at = datetime('now') WHERE request_id = ?", (shared.request_id,))
            conn.commit()
            summary = f"Приглашения отправлены: {delivered}."
            if unavailable:
                summary += f" Не удалось доставить: {unavailable} — эти пользователи ещё не начали диалог с ботом."
            await message.answer(summary)
            return

        request = conn.execute("SELECT * FROM member_import_requests WHERE request_id = ? AND requested_by_user_id = ? AND status = 'pending'", (shared.request_id, actor["id"])).fetchone()
        if not request:
            await message.answer("Выбор участников устарел. Откройте его снова из комнаты.")
            return
        group_id = request["group_id"]
        added = 0
        for picked in shared.users:
            telegram_id = int(picked.user_id)
            existing = conn.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
            if existing:
                user_id = existing["id"]
                conn.execute("UPDATE users SET username = COALESCE(?, username), display_name = COALESCE(?, display_name) WHERE id = ?", (getattr(picked, "username", None), " ".join(filter(None, [picked.first_name, picked.last_name])) or "Участник Telegram", user_id))
            else:
                display_name = " ".join(filter(None, [picked.first_name, picked.last_name])) or "Участник Telegram"
                cur = conn.execute("INSERT INTO users (telegram_id, username, display_name, access_status, has_started_bot) VALUES (?, ?, ?, 'shared', 0)", (telegram_id, getattr(picked, "username", None), display_name))
                user_id = cur.lastrowid
            cur = conn.execute("INSERT OR IGNORE INTO group_members (group_id, user_id, display_name, is_external, role, status, telegram_username) VALUES (?, ?, ?, 0, 'member', 'invited', ?)", (group_id, user_id, " ".join(filter(None, [picked.first_name, picked.last_name])) or "Участник Telegram", getattr(picked, "username", None)))
            added += int(cur.rowcount > 0)
        conn.execute("UPDATE member_import_requests SET status = 'completed', completed_at = datetime('now') WHERE request_id = ?", (shared.request_id,))
        conn.commit()
        await message.answer(f"Добавлено приглашённых участников: {added}. Когда они откроют бота, доступ активируется.")
    finally:
        conn.close()


# ─── /add <сумма> <описание> ──────────────────────────────────

@router.message(Command("add"))
async def cmd_add(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)

    try:
        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            await message.answer(
                "❓ Формат: `/add 500 продукты`\n"
                "Или просто напишите: _\"купил хлеб 80р\"_",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        try:
            amount = float(args[1].replace(",", "."))
        except ValueError:
            await message.answer("⚠️ Некорректная сумма. Пример: `/add 500 обед`", parse_mode=ParseMode.MARKDOWN)
            return

        description = args[2] if len(args) > 2 else "Расход"

        # AI-категоризация (с fallback если API недоступен)
        try:
            ai_result = await categorize_expense(description)
            category = ai_result.get("category", "🔧 Другое")
            ai_desc = ai_result.get("description", description)
            is_personal = ai_result.get("is_personal", False) or any(kw in description.lower() for kw in ["себе", "для себя", "личн", "лично"])
        except Exception as ai_err:
            logger.warning(f"AI недоступен, используем fallback: {ai_err}")
            category = "🔧 Другое"
            ai_desc = description
            is_personal = any(kw in description.lower() for kw in ["себе", "для себя", "личн", "лично"])

        # Очищаем итоговое описание от служебных слов 'себе'/'для себя'
        ai_desc = re.sub(r"(?i)\b(себе|для себя|лично|личное|личный|личные)\b", "", ai_desc).strip()
        ai_desc = re.sub(r"\s+", " ", ai_desc).strip(" ,.-").capitalize() or "Расход"

        if is_personal:
            split_user_ids = [user["id"]]
            share_text = "👤 **Личный расход** (не делится на группу, долг другим не начислен ✅)"
        else:
            members = get_group_members_users(conn, group["id"])
            member_ids = [m["id"] for m in members]
            if len(member_ids) < 1:
                member_ids = [user["id"]]
            split_user_ids = member_ids
            share = round(amount / len(split_user_ids), 2)
            share_text = f"👥 Разделено на: {len(split_user_ids)} чел. ({share:,.0f}₽ каждый)"

        try:
            expense_id = add_expense(
                conn,
                group_id=group["id"],
                payer_id=user["id"],
                amount=amount,
                description=ai_desc,
                category=category,
                split_user_ids=split_user_ids,
            )
        except RoomNeedsMoreMembersError as err:
            await message.answer(f"⚠️ {err}. Сначала пригласите ещё одного участника.")
            return

        text = (
            f"✅ **Расход записан!**\n\n"
            f"💰 Сумма: **{amount:,.0f}₽**\n"
            f"📝 Описание: {ai_desc}\n"
            f"🏷 Категория: {category}\n"
            f"👤 Оплатил: {user['display_name']}\n"
            f"{share_text}"
        )
        await message.answer(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_webapp_keyboard(group["id"], "📱 Посмотреть баланс в WebApp")
        )

    except Exception as e:
        logger.error(f"Error in /add: {e}", exc_info=True)
        await message.answer("❌ Ошибка при добавлении расхода.")
    finally:
        conn.close()


# ─── Умный ввод (просто текстом) ─────────────────────────────


# ─── NLP Распознавание Долгов ─────────────────────────────────

def _normalize_name(name: str) -> str:
    """Удалить окончания дательного падежа для поиска участника."""
    clean = name.strip()
    if clean.lower().endswith("у") or clean.lower().endswith("ю"):
        return clean[:-1]
    if clean.lower().endswith("е"):
        return clean[:-1] + "а"
    return clean


def _find_member_by_name(members: list, query_name: str):
    """Поиск участника группы по имени/юзернейму."""
    q = query_name.lower().strip()
    q_norm = _normalize_name(q).lower()

    for m in members:
        dname = (m.get("display_name") or "").lower()
        uname = (m.get("username") or "").lower()
        if q == dname or q == uname or q_norm == dname or q_norm == uname:
            return m

    for m in members:
        dname = (m.get("display_name") or "").lower()
        if q_norm and (q_norm in dname or dname in q_norm):
            return m

    return None


@router.message(F.text & ~F.text.startswith("/"))
async def process_nlp_debts(message: Message):
    """
    NLP обработка фиксации и возврата долгов естественным языком:
    1. 'Иван должен мне 1500 за ужин'
    2. 'Я должен Ивану 800 за такси'
    3. 'Я вернул Ивану 500' / 'Иван вернул мне 500'
    """
    if message.chat.type not in ("group", "supergroup"):
        return await smart_input(message)

    text = message.text.strip()

    # Паттерн 1: "<X> должен мне <Y> [за <Z>]"
    m1 = re.match(r"(?i)^([А-Яа-яA-Za-z0-9_ -]+?)\s+должен\s+(?:мне)\s+(\d+(?:[.,]\d+)?)\s*(?:руб|р|₽)?(?:\s+(?:за|на)\s+(.+))?$", text)

    # Паттерн 2: "Я должен <X> <Y> [за <Z>]"
    m2 = re.match(r"(?i)^я\s+должен\s+([А-Яа-яA-Za-z0-9_ -]+?)\s+(\d+(?:[.,]\d+)?)\s*(?:руб|р|₽)?(?:\s+(?:за|на)\s+(.+))?$", text)

    # Паттерн 3: "Я вернул/отдал <X> <Y>"
    m3 = re.match(r"(?i)^я\s+(?:вернул|отдал|перев[её]л|погасил)\s+([А-Яа-яA-Za-z0-9_ -]+?)\s+(\d+(?:[.,]\d+)?)\s*(?:руб|р|₽)?(?:\s+(?:за|на)\s+(.+))?$", text)

    # Паттерн 4: "<X> вернул/отдал мне <Y>"
    m4 = re.match(r"(?i)^([А-Яа-яA-Za-z0-9_ -]+?)\s+(?:вернул|отдал|перев[её]л)\s+(?:мне)\s+(\d+(?:[.,]\d+)?)\s*(?:руб|р|₽)?(?:\s+(?:за|на)\s+(.+))?$", text)

    if not (m1 or m2 or m3 or m4):
        return await smart_input(message)

    user, group, conn = ensure_user_and_group(message)
    group_id = group["id"]
    members = get_group_members_users(conn, group_id)

    webapp_url = get_current_webapp_url(group_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📱 Открыть в Mini App", web_app=WebAppInfo(url=webapp_url))
    ]])

    try:
        # СЛУЧАЙ 1: X должен мне Y
        if m1:
            raw_debtor = m1.group(1).strip()
            amount = float(m1.group(2).replace(",", "."))
            desc = m1.group(3).strip() if m1.group(3) else "Долг"

            if amount <= 0:
                conn.close()
                return

            found_m = _find_member_by_name(members, raw_debtor)
            debtor_id = found_m["id"] if found_m else None
            debtor_name = found_m["display_name"] if found_m else raw_debtor

            debt = create_debt(
                conn=conn,
                group_id=group_id,
                creditor_user_id=user["id"],
                creditor_name=user["display_name"],
                debtor_user_id=debtor_id,
                debtor_name=debtor_name,
                amount=amount,
                description=desc,
                notification_frequency="none",
                created_by_user_id=user["id"]
            )

            conn.close()
            resp = (
                f"📝 **Долг зафиксирован!**\n\n"
                f"👤 Должник: **{debtor_name}**\n"
                f"💳 Кредитор: **{user['display_name']}** (Вы)\n"
                f"💰 Сумма: **{amount:,.2f} ₽**\n"
                f"📌 Назначение: {desc}\n"
                f"Чат: «{group['name']}»"
            )
            await message.answer(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
            return

        # СЛУЧАЙ 2: Я должен X Y
        if m2:
            raw_creditor = m2.group(1).strip()
            amount = float(m2.group(2).replace(",", "."))
            desc = m2.group(3).strip() if m2.group(3) else "Долг"

            if amount <= 0:
                conn.close()
                return

            found_m = _find_member_by_name(members, raw_creditor)
            creditor_id = found_m["id"] if found_m else None
            creditor_name = found_m["display_name"] if found_m else _normalize_name(raw_creditor)

            debt = create_debt(
                conn=conn,
                group_id=group_id,
                creditor_user_id=creditor_id,
                creditor_name=creditor_name,
                debtor_user_id=user["id"],
                debtor_name=user["display_name"],
                amount=amount,
                description=desc,
                notification_frequency="none",
                created_by_user_id=user["id"]
            )

            conn.close()
            resp = (
                f"📝 **Ваш долг зафиксирован!**\n\n"
                f"👤 Должник: **{user['display_name']}** (Вы)\n"
                f"💳 Кредитор: **{creditor_name}**\n"
                f"💰 Сумма: **{amount:,.2f} ₽**\n"
                f"📌 Назначение: {desc}\n"
                f"Чат: «{group['name']}»"
            )
            await message.answer(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
            return

        # СЛУЧАЙ 3: Я вернул X Y
        if m3:
            raw_creditor = m3.group(1).strip()
            amount = float(m3.group(2).replace(",", "."))
            note = m3.group(3).strip() if m3.group(3) else "Оплата через чат"

            if amount <= 0:
                conn.close()
                return

            found_m = _find_member_by_name(members, raw_creditor)
            norm_name = _normalize_name(raw_creditor)

            active_debts = get_group_debts(conn, group_id, user_id=user["id"], filter_tab="i_owe", status="active")
            active_debts += get_group_debts(conn, group_id, user_id=user["id"], filter_tab="i_owe", status="partially_paid")

            target_debt = None
            for d in active_debts:
                if found_m and d["creditor_user_id"] == found_m["id"]:
                    target_debt = d
                    break
                if norm_name.lower() in d["creditor_name"].lower():
                    target_debt = d
                    break

            if target_debt:
                res = add_debt_payment(conn, target_debt["id"], amount, user["id"], note)
                conn.close()
                if res["remaining_amount"] <= 0:
                    resp = (
                        f"🎉 **Долг полностью погашен!**\n\n"
                        f"Вы вернули **{target_debt['creditor_name']}** сумму **{amount:,.2f} ₽**.\n"
                        f"Долг «{target_debt['description']}» закрыт ✅"
                    )
                else:
                    resp = (
                        f"✅ **Платёж зафиксирован!**\n\n"
                        f"Внесено: **{amount:,.2f} ₽** кому: **{target_debt['creditor_name']}**\n"
                        f"Остаток долга: **{res['remaining_amount']:,.2f} ₽** (из {target_debt['original_amount']:,.2f} ₽)"
                    )
                await message.answer(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
                return
            else:
                conn.close()
                await message.answer(
                    f"ℹ️ Не найден активный долг перед **{raw_creditor}**.\n"
                    f"Проверьте список долгов командой /debts или в Mini App.",
                    reply_markup=kb
                )
                return

        # СЛУЧАЙ 4: X вернул мне Y
        if m4:
            raw_debtor = m4.group(1).strip()
            amount = float(m4.group(2).replace(",", "."))
            note = m4.group(3).strip() if m4.group(3) else "Возврат через чат"

            if amount <= 0:
                conn.close()
                return

            found_m = _find_member_by_name(members, raw_debtor)

            active_debts = get_group_debts(conn, group_id, user_id=user["id"], filter_tab="owed_to_me", status="active")
            active_debts += get_group_debts(conn, group_id, user_id=user["id"], filter_tab="owed_to_me", status="partially_paid")

            target_debt = None
            for d in active_debts:
                if found_m and d["debtor_user_id"] == found_m["id"]:
                    target_debt = d
                    break
                if raw_debtor.lower() in d["debtor_name"].lower():
                    target_debt = d
                    break

            if target_debt:
                res = add_debt_payment(conn, target_debt["id"], amount, user["id"], note)
                conn.close()
                if res["remaining_amount"] <= 0:
                    resp = (
                        f"🎉 **Долг закрыт!**\n\n"
                        f"**{target_debt['debtor_name']}** вернул вам **{amount:,.2f} ₽**.\n"
                        f"Долг «{target_debt['description']}» полностью погашен ✅"
                    )
                else:
                    resp = (
                        f"✅ **Платёж зафиксирован!**\n\n"
                        f"**{target_debt['debtor_name']}** выплатил **{amount:,.2f} ₽**\n"
                        f"Остаток долга перед вами: **{res['remaining_amount']:,.2f} ₽**"
                    )
                await message.answer(resp, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
                return
            else:
                conn.close()
                await message.answer(
                    f"ℹ️ Не найден активный долг от **{raw_debtor}** перед вами.\n"
                    f"Проверьте список долгов в Mini App.",
                    reply_markup=kb
                )
                return

    except Exception as e:
        logger.error(f"Error processing NLP debt: {e}", exc_info=True)
        try:
            conn.close()
        except Exception:
            pass


async def smart_input(message: Message):
    """Обработка текстового сообщения — попытка распознать расход через AI."""
    if message.chat.type not in ("group", "supergroup"):
        return

    text = message.text.strip()

    # Проверяем, содержит ли текст числа
    if not re.search(r'\d', text):
        return

    # Проверяем ключевые слова расходов
    expense_keywords = [
        "купил", "заплатил", "потратил", "оплатил", "стоил",
        "за ", "₽", "руб", "рубл", "р.", "р ",
    ]
    has_keyword = any(kw in text.lower() for kw in expense_keywords)

    if not has_keyword:
        return

    user, group, conn = ensure_user_and_group(message)
    conn.close()

    try:
        # AI извлекает данные
        ai_result = await categorize_expense(text)
        amount = ai_result.get("amount", 0)
        category = ai_result.get("category", "🔧 Другое")
        description = ai_result.get("description", text[:50])
        is_personal = ai_result.get("is_personal", False) or any(kw in text.lower() for kw in ["себе", "для себя", "личн", "лично"])

        # Очищаем название от служебных слов
        clean_desc = re.sub(r"(?i)\b(себе|для себя|лично|личное|личный|личные)\b", "", description).strip()
        clean_desc = re.sub(r"\s+", " ", clean_desc).strip(" ,.-").capitalize() or "Расход"

        if amount <= 0:
            return

        # Спрашиваем подтверждение
        cat_idx = CATEGORIES.index(category) if category in CATEGORIES else 10
        pers_flag = "1" if is_personal else "0"
        cb_data = f"exp:{amount}:{cat_idx}:{pers_flag}:{clean_desc[:20]}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Записать", callback_data=cb_data),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_expense"),
            ]
        ])

        personal_note = "\n👤 **Личный расход** (не делится на группу, долг другим не начисляется ✅)\n" if is_personal else ""
        await message.answer(
            f"🤖 Распознал расход:\n\n"
            f"💰 **{amount:,.0f}₽** — {clean_desc}\n"
            f"🏷 Категория: {category}"
            f"{personal_note}\n"
            f"Записать?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"Error in smart_input: {e}", exc_info=True)


# ─── Распознавание чеков по фото ──────────────────────────────

@router.message(F.photo)
async def handle_photo_receipt(message: Message, bot: Bot):
    """Обработка фото чека из магазина."""
    if message.chat.type not in ("group", "supergroup"):
        return

    user, group, conn = ensure_user_and_group(message)
    conn.close()

    status_msg = await message.answer("🔍 Сканирую чек...")

    try:
        photo = message.photo[-1]
        file_io = io.BytesIO()
        await bot.download(photo.file_id, destination=file_io)
        file_bytes = file_io.getvalue()

        result = parse_image_receipt(file_bytes)
        amount = result.get("amount", 0.0)
        desc = result.get("description", "Чек")
        cat = result.get("category", "🍞 Продукты")

        if amount > 0:
            cat_idx = CATEGORIES.index(cat) if cat in CATEGORIES else 10
            cb_data = f"exp:{amount}:{cat_idx}:0:{desc[:20]}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Записать чек", callback_data=cb_data),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_expense"),
                ]
            ])
            await status_msg.edit_text(
                f"🧾 **Чек успешно распознан!**\n\n"
                f"💰 Сумма: **{amount:,.0f}₽**\n"
                f"📝 Описание: {desc}\n"
                f"🏷 Категория: {cat}\n\n"
                f"Записать в общие расходы?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        else:
            await status_msg.edit_text(
                f"🧾 Чек получен, но не удалось автоматически извлечь сумму.\n"
                f"Вы можете записать его командой:\n`/add 450 {desc}`",
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception as e:
        logger.error(f"Error processing receipt photo: {e}", exc_info=True)
        await status_msg.edit_text("❌ Ошибка при обработке фотографии чека.")


# ─── Распознавание электронных чеков PDF (Сбер, банки) ────────

@router.message(F.document)
async def handle_pdf_receipt(message: Message, bot: Bot):
    """Обработка PDF файла чека (например, из приложения СберБанка)."""
    if message.chat.type not in ("group", "supergroup"):
        return

    doc = message.document
    if not (doc.file_name and doc.file_name.lower().endswith(".pdf")):
        return

    user, group, conn = ensure_user_and_group(message)
    conn.close()

    status_msg = await message.answer("📄 Читаю электронный PDF-чек...")

    try:
        file_io = io.BytesIO()
        await bot.download(doc.file_id, destination=file_io)
        file_bytes = file_io.getvalue()

        result = parse_pdf_receipt(file_bytes)
        amount = result.get("amount", 0.0)
        desc = result.get("description", "Электронный чек")
        cat = result.get("category", "🔧 Другое")

        if amount > 0:
            cat_idx = CATEGORIES.index(cat) if cat in CATEGORIES else 10
            cb_data = f"exp:{amount}:{cat_idx}:0:{desc[:20]}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Записать PDF-чек", callback_data=cb_data),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_expense"),
                ]
            ])
            await status_msg.edit_text(
                f"📄 **Чек из банка распознан!**\n\n"
                f"💰 Сумма: **{amount:,.0f}₽**\n"
                f"📝 Назначение: {desc}\n"
                f"🏷 Категория: {cat}\n\n"
                f"Внести в баланс группы?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        else:
            await status_msg.edit_text(
                f"📄 Документ обработан, но точная сумма не найдена.\n"
                f"Напишите: `/add 500 {desc}`",
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception as e:
        logger.error(f"Error reading PDF receipt: {e}", exc_info=True)
        await status_msg.edit_text("❌ Ошибка при чтении PDF документа.")


@router.callback_query(F.data.startswith("exp:"))
async def confirm_expense(callback: CallbackQuery):
    """Подтверждение расхода из умного ввода и чеков."""
    try:
        await callback.answer("⏳ Записываю...")
    except Exception:
        pass

    conn = None
    try:
        parts = callback.data.split(":")
        amount = float(parts[1])
        if len(parts) >= 5:
            # Новый надёжный формат: exp:{amount}:{cat_idx}:{pers_flag}:{description}
            try:
                cat_idx = int(parts[2])
                category = CATEGORIES[cat_idx] if 0 <= cat_idx < len(CATEGORIES) else "🔧 Другое"
            except (ValueError, IndexError):
                category = "🔧 Другое"
            is_pers_flag = (parts[3] == "1")
            description = ":".join(parts[4:]) if len(parts) > 4 else "Расход"
        elif len(parts) == 4:
            is_pers_flag = (parts[3] == "1")
            description = parts[2]
            category = "🔧 Другое"
        else:
            description = parts[2] if len(parts) > 2 else "Расход"
            is_pers_flag = False
            category = "🔧 Другое"

        conn = get_db()
        user = get_or_create_user(
            conn,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username or "",
            display_name=callback.from_user.full_name or "Аноним",
        )
        group = get_or_create_group(
            conn,
            chat_id=callback.message.chat.id,
            name=callback.message.chat.title or "Группа",
        )

        is_personal = is_pers_flag or any(kw in description.lower() for kw in ["себе", "для себя", "личн", "лично"])

        # Очищаем название от остатков 'себе'
        description = re.sub(r"(?i)\b(себе|для себя|лично|личное|личный|личные)\b", "", description).strip()
        description = re.sub(r"\s+", " ", description).strip(" ,.-").capitalize() or "Расход"

        if is_personal:
            split_user_ids = [user["id"]]
            share_text = "👤 **Личный расход** (не делится на группу, долг другим не начислен ✅)"
        else:
            members = get_group_members_users(conn, group["id"])
            member_ids = [m["id"] for m in members] if members else [user["id"]]
            split_user_ids = member_ids
            share = round(amount / len(split_user_ids), 2)
            share_text = f"👥 Разделено на {len(split_user_ids)} чел. ({share:,.0f}₽ каждый)"

        # Если категория не была передана через индекс, пробуем определить
        if category == "🔧 Другое":
            try:
                ai_result = await categorize_expense(description)
                cat_cand = ai_result.get("category")
                if cat_cand and cat_cand != "🔧 Другое":
                    category = cat_cand
            except Exception:
                pass

        try:
            add_expense(conn, group["id"], user["id"], amount, description, category, split_user_ids)
        except RoomNeedsMoreMembersError as err:
            await callback.message.answer(f"⚠️ {err}. Сначала пригласите ещё одного участника.")
            return

        text = (
            f"✅ **Записано!**\n\n"
            f"💰 **{amount:,.0f}₽** — {description} ({category})\n"
            f"👤 Оплатил: {user['display_name']}\n"
            f"{share_text}"
        )
        is_priv = callback.message.chat.type == "private"
        keyboard = get_webapp_keyboard(group["id"], "SberWise — ваш умный помощник", is_private=is_priv)
        try:
            await callback.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception as edit_err:
            logger.warning(f"edit_text with keyboard failed, falling back to text-only: {edit_err}")
            await callback.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=None,
            )

    except Exception as e:
        logger.error(f"Error confirming expense: {e}", exc_info=True)
        try:
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
        except Exception:
            pass
    finally:
        if conn:
            conn.close()


@router.callback_query(F.data == "cancel_expense")
async def cancel_expense(callback: CallbackQuery):
    await callback.message.edit_text("❌ Расход отменён.")


# ─── /balance ─────────────────────────────────────────────────

@router.message(Command("balance"))
async def cmd_balance(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)

    try:
        balances = get_group_balances(conn, group["id"])

        if not balances:
            await message.answer("📭 Пока нет записанных расходов.")
            return

        # Подставить имена
        named_balances = {}
        for uid, balance in balances.items():
            u = get_user_by_id(conn, uid)
            name = u["display_name"] if u else f"User#{uid}"
            named_balances[name] = balance

        # Текстовый баланс
        lines = ["📊 **Баланс группы:**\n"]
        for name, balance in sorted(named_balances.items(), key=lambda x: -x[1]):
            if balance > 0.01:
                lines.append(f"🟢 {name}: +{balance:,.0f}₽ (ему должны)")
            elif balance < -0.01:
                lines.append(f"🔴 {name}: {balance:,.0f}₽ (должен)")
            else:
                lines.append(f"⚪ {name}: 0₽ (в расчёте)")

        # Упрощённые долги
        debts = simplify_debts(balances)
        if debts:
            lines.append("\n💸 **Кто кому платит:**")
            for from_id, to_id, amt in debts:
                from_u = get_user_by_id(conn, from_id)
                to_u = get_user_by_id(conn, to_id)
                from_name = from_u["display_name"] if from_u else f"User#{from_id}"
                to_name = to_u["display_name"] if to_u else f"User#{to_id}"
                lines.append(f"  {from_name} → {to_name}: **{amt:,.0f}₽**")

        await message.answer("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

        # Отправить график
        try:
            chart_buf = create_balance_chart(named_balances)
            await message.answer_photo(
                BufferedInputFile(chart_buf.getvalue(), filename="balance.png"),
                caption="⚖️ **Балансы группы** (зеленый = вам должны, красный = вы должны)",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_webapp_keyboard(group["id"], "📱 Интерактивный баланс в WebApp"),
            )
        except Exception as chart_err:
            logger.warning(f"Could not render balance chart: {chart_err}")

    except Exception as e:
        logger.error(f"Error in /balance: {e}", exc_info=True)
        await message.answer("❌ Ошибка при расчёте баланса.")
    finally:
        conn.close()


# ─── /chart ───────────────────────────────────────────────────

@router.message(Command("chart"))
async def cmd_chart(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)

    try:
        totals = get_category_totals(conn, group["id"])

        if not totals:
            await message.answer("📭 Пока нет данных для графика. Добавьте расходы через `/add`!", parse_mode=ParseMode.MARKDOWN)
            return

        chart_buf = create_pie_chart(totals, title=f"Расходы: {message.chat.title}")
        await message.answer_photo(
            BufferedInputFile(chart_buf.read(), filename="chart.png"),
            caption="📊 Распределение расходов по категориям",
            reply_markup=get_webapp_keyboard(group["id"], "📊 Открыть диаграмму в WebApp"),
        )

    except Exception as e:
        logger.error(f"Error in /chart: {e}", exc_info=True)
        await message.answer("❌ Ошибка при создании графика.")
    finally:
        conn.close()


# ─── /history ─────────────────────────────────────────────────

@router.message(Command("history"))
async def cmd_history(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)

    try:
        expenses = get_group_expenses(conn, group["id"], limit=15)

        if not expenses:
            await message.answer("📭 Пока нет записанных расходов.")
            return

        lines = ["📋 **Последние расходы:**\n"]
        for i, exp in enumerate(expenses, 1):
            payer = get_user_by_id(conn, exp["paid_by"])
            payer_name = payer["display_name"] if payer else "?"
            date_str = exp["created_at"][:16].replace("T", " ") if exp["created_at"] else ""
            lines.append(
                f"{i}. {exp['category'] or '🔧'} **{exp['amount']:,.0f}₽** — {exp['description']}\n"
                f"   👤 {payer_name} | 📅 {date_str}"
            )

        await message.answer("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error in /history: {e}", exc_info=True)
        await message.answer("❌ Ошибка при загрузке истории.")
    finally:
        conn.close()


# ─── /simplify ────────────────────────────────────────────────

@router.message(Command("simplify"))
async def cmd_simplify(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)

    try:
        balances = get_group_balances(conn, group["id"])
        debts = simplify_debts(balances)

        if not debts:
            await message.answer("✅ Все расчёты завершены! Никто никому не должен 🎉")
            return

        lines = ["🔄 **Оптимальные переводы** (минимум транзакций):\n"]
        for i, (from_id, to_id, amt) in enumerate(debts, 1):
            from_u = get_user_by_id(conn, from_id)
            to_u = get_user_by_id(conn, to_id)
            from_name = from_u["display_name"] if from_u else f"User#{from_id}"
            to_name = to_u["display_name"] if to_u else f"User#{to_id}"

            try:
                reminder = await generate_debt_reminder(from_name, to_name, amt)
            except Exception:
                reminder = f"Напоминаю о долге {amt:,.0f}₽ 😊"
            lines.append(f"{i}. {from_name} → {to_name}: **{amt:,.0f}₽**\n   💬 _{reminder}_")

        lines.append(f"\n📊 Всего переводов: **{len(debts)}**")
        await message.answer("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error in /simplify: {e}", exc_info=True)
        await message.answer("❌ Ошибка при упрощении долгов.")
    finally:
        conn.close()


# ─── /settle @user <сумма> ────────────────────────────────────

@router.message(Command("settle"))
async def cmd_settle(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)

    try:
        args = message.text.split()
        if len(args) < 3:
            await message.answer(
                "❓ Формат: `/settle @username 300`\n"
                "Это значит: вы отдали @username 300₽",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        target_username = args[1].lstrip("@")
        try:
            amount = float(args[2].replace(",", "."))
        except ValueError:
            await message.answer("⚠️ Некорректная сумма.")
            return

        members = get_group_members_users(conn, group["id"])
        target_user = None
        for m in members:
            if m["username"] and m["username"].lower() == target_username.lower():
                target_user = m
                break
            if m["display_name"].lower() == target_username.lower():
                target_user = m
                break

        if target_user is None:
            await message.answer(f"⚠️ Пользователь @{target_username} не найден в группе.")
            return

        add_settlement(conn, group["id"], user["id"], target_user["id"], amount)

        await message.answer(
            f"✅ **Погашение записано!**\n\n"
            f"💸 {user['display_name']} → {target_user['display_name']}: **{amount:,.0f}₽**",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error(f"Error in /settle: {e}", exc_info=True)
        await message.answer("❌ Ошибка при записи погашения.")
    finally:
        conn.close()


# ─── /reset или /reset_month — обнуление трат за месяц ───────

@router.message(Command("reset"))
@router.message(Command("reset_month"))
@router.message(Command("clear"))
async def cmd_reset(message: Message):
    """Обнулить историю трат и взаиморасчётов группы за текущий месяц (или всю историю)."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)
    try:
        args = message.text.strip().split()
        if len(args) >= 2 and args[1].lower() in ("confirm", "да", "force"):
            # Быстрый сброс без дополнительного диалога
            count = reset_group_expenses(conn, group["id"], only_current_month=True)
            await message.answer(
                f"🗑️ **История трат за текущий месяц обнулена!**\n\n"
                f"• Удалено операций: **{count}**\n"
                f"• Все балансы и долги участников сброшены в **0 ₽** 🎉\n"
                f"Дашборд снова чистый!",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 Сбросить за этот месяц", callback_data=f"do_reset_month_{group['id']}"),
            ],
            [
                InlineKeyboardButton(text="💥 Сбросить вообще всё (всю историю)", callback_data=f"do_reset_all_{group['id']}"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="do_reset_cancel"),
            ]
        ])

        await message.answer(
            f"⚠️ **Подтверждение обнуления трат**\n\n"
            f"Группа: **«{group['name']}»**\n"
            f"Инициатор: **{user['display_name']}**\n\n"
            f"Выберите, что требуется сделать:\n"
            f"• **Сбросить за этот месяц** — обнулит все расходы и взаиморасчёты за текущий календарный месяц.\n"
            f"• **Сбросить вообще всё** — полная очистка всей базы расходов группы.\n\n"
            f"Все балансы и долги станут равны **0 ₽**.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    finally:
        conn.close()


@router.callback_query(F.data.startswith("do_reset_"))
async def callback_reset(callback: CallbackQuery):
    """Обработчик подтверждения сброса трат."""
    action = callback.data.replace("do_reset_", "")
    if action == "cancel":
        await callback.message.edit_text("❌ **Обнуление отменено.** Траты и балансы сохранены.", parse_mode=ParseMode.MARKDOWN)
        await callback.answer()
        return

    conn = get_db()
    try:
        if action.startswith("month_"):
            group_id = int(action.replace("month_", ""))
            count = reset_group_expenses(conn, group_id, only_current_month=True)
            await callback.message.edit_text(
                f"✨ **История трат за текущий месяц успешно обнулена!**\n\n"
                f"• Удалено операций: **{count}**\n"
                f"• Балансы всех участников: **0 ₽** 🎉\n\n"
                f"Можно начинать вести бюджет месяца с чистого листа!",
                parse_mode=ParseMode.MARKDOWN,
            )
        elif action.startswith("all_"):
            group_id = int(action.replace("all_", ""))
            count = reset_group_expenses(conn, group_id, only_current_month=False)
            await callback.message.edit_text(
                f"✨ **Вся история трат группы полностью обнулена!**\n\n"
                f"• Удалено операций: **{count}**\n"
                f"• Балансы участников: **0 ₽** 🎉\n\n"
                f"История очищена!",
                parse_mode=ParseMode.MARKDOWN,
            )
        await callback.answer("Готово!")
    finally:
        conn.close()


# ─── /budget_limit [сумма] ────────────────────────────────────

@router.message(Command("budget_limit"))
async def cmd_budget_limit(message: Message):
    """Просмотр и настройка месячного лимита бюджета группы."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)
    try:
        args = message.text.strip().split()
        if len(args) >= 2:
            try:
                raw_amt = args[1].replace(",", ".").replace(" ", "").replace("₽", "").replace("k", "000").replace("к", "000")
                new_limit = float(raw_amt)
                if new_limit <= 0:
                    raise ValueError()
                set_group_budget_limit(conn, group["id"], new_limit)
                await message.answer(
                    f"🎯 **Лимит бюджета обновлён!**\n\n"
                    f"Новый месячный лимит группы «{group['name']}»: **{new_limit:,.0f} ₽**.\n"
                    f"Бот будет отслеживать темп расходов и предупредит при превышении!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_webapp_keyboard(group["id"], "📱 Открыть дашборд бюджета"),
                )
                return
            except ValueError:
                await message.answer("⚠️ Укажите корректную сумму лимита, например: `/budget 60000`", parse_mode=ParseMode.MARKDOWN)
                return

        # Если без аргументов — показываем текущий статус
        target_limit = get_group_budget_limit(conn, group["id"])
        category_totals = get_category_totals(conn, group["id"])
        total_spent = sum(category_totals.values())

        now = datetime.now()
        forecast = calculate_budget_forecast(
            total_spent_month=total_spent,
            days_elapsed=max(1, now.day),
            days_in_month=30,
            target_budget=target_limit,
        )

        status_emoji = "🟢" if "нормы" in forecast["status"] else ("🟠" if "Повышенная" in forecast["status"] else "🔴")
        text = (
            f"⚡ **Предиктивный прогноз бюджета (AI Сбер)**\n\n"
            f"🎯 Лимит группы: **{target_limit:,.0f} ₽**\n"
            f"💸 Израсходовано: **{total_spent:,.0f} ₽** ({forecast['percent_used']}%)\n"
            f"📊 Темп трат: **{forecast['daily_burn_rate']:,.0f} ₽/день**\n"
            f"🚦 Статус: {status_emoji} **{forecast['status']}**\n\n"
            f"{forecast['forecast_message']}\n\n"
            f"💡 Чтобы установить свой лимит, напишите: `/budget 80000`"
        )
        await message.answer(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_webapp_keyboard(group["id"], "📱 Смотреть прогноз в WebApp"),
        )
    finally:
        conn.close()




# ─── Голосовой ввод расхода (Speech-To-Text) ──────────────────

@router.message(F.voice | F.audio)
async def handle_voice_expense(message: Message, bot: Bot):
    """Обработка голосового сообщения с расходом (STT + AI)."""
    if message.chat.type not in ("group", "supergroup"):
        return

    user, group, conn = ensure_user_and_group(message)
    group_id = group["id"]
    members = get_group_members_users(conn, group_id)
    conn.close()

    status_msg = await message.answer("🎙 Слушаю и расшифровываю голосовое сообщение...")

    try:
        voice = message.voice or message.audio
        file_io = io.BytesIO()
        await bot.download(voice.file_id, destination=file_io)
        file_bytes = file_io.getvalue()

        draft = await transcribe_and_parse_voice(
            audio_bytes=file_bytes,
            room_members=members,
            default_payer_id=user["id"],
        )

        total = draft.get("total_amount", 0.0)
        title = draft.get("title", "Расход")
        transcript = draft.get("transcription", "")
        items = draft.get("items", [])

        if total > 0:
            webapp_url = get_current_webapp_url(group_id)

            # Сохраняем расход с позициями
            conn_write = get_db()
            try:
                try:
                    res = add_expense_itemized(
                        conn=conn_write,
                        group_id=group_id,
                        payer_id=user["id"],
                        title=title,
                        items=items,
                        source_type="voice",
                    )
                except RoomNeedsMoreMembersError as err:
                    await status_msg.edit_text(f"⚠️ {err}. Сначала пригласите ещё одного участника.")
                    return
            finally:
                conn_write.close()

            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📱 Открыть комнату в Mini App", web_app=WebAppInfo(url=webapp_url)),
            ]])

            items_preview = []
            for it in items[:4]:
                items_preview.append(f"• **{it['name']}**: `{it['total_amount']:,.0f} ₽`")

            await status_msg.edit_text(
                f"🎙 **Голосовой расход записан в комнату!**\n\n"
                f"💬 *«{transcript}»*\n\n"
                f"💰 Итого: **{total:,.2f} ₽**\n"
                f"👤 Заплатил: **{user['display_name']}**\n"
                f"📋 Позиции:\n" + "\n".join(items_preview) + "\n\n"
                f"Баланс комнаты обновлён ✅",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb,
            )
        else:
            await status_msg.edit_text("🎙 Не удалось разобрать сумму трат из аудио. Попробуйте записать чётче или текстом.")
    except Exception as e:
        logger.error(f"Error processing voice: {e}", exc_info=True)
        await status_msg.edit_text("❌ Ошибка при обработке голосового сообщения.")


# ─── /settle и /summary — Итоги комнаты в чат ────────────────

@router.message(Command("summary"))
async def cmd_room_summary(message: Message):
    """Опубликовать итоги комнаты и минимальные взаиморасчёты в чат."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда доступна только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)
    group_id = group["id"]
    try:
        settlement = calculate_room_settlement(conn, group_id, user["id"])
        total_spent = settlement.get("total_expenses", 0.0)
        transfers = settlement.get("transfers", [])
        my_res = settlement.get("my_result", 0.0)

        webapp_url = get_current_webapp_url(group_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📱 Открыть в Mini App", web_app=WebAppInfo(url=webapp_url)),
        ]])

        res_sign = "+" if my_res > 0 else ""
        my_note = f"Ваш личный баланс: **{res_sign}{my_res:,.2f} ₽**\n" if my_res != 0 else "Ваш баланс сведён в ноль.\n"

        lines = [
            f"💸 **Итоги комнаты «{group['name']}»**\n",
            f"📊 **Всего расходов:** `{total_spent:,.2f} ₽`",
            f"👤 {my_note}",
        ]

        if transfers:
            lines.append("⚡ **Минимальные переводы для полного расчета:**")
            for t in transfers:
                lines.append(f"• **{t['from_name']}** → **{t['to_name']}**: `{t['amount']:,.2f} ₽`")
        else:
            lines.append("🎉 **Все долги закрыты, взаиморасчёты завершены!**")

        await message.answer("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    finally:
        conn.close()


# ─── /remind [минуты] — настройка AI-напоминаний ────────────────

def format_interval_str(minutes: int) -> str:
    """Форматирование интервала в читаемую строку."""
    if minutes <= 0:
        return "выключен"
    if minutes < 60:
        return f"{minutes} мин."
    hours = minutes / 60
    if minutes % 60 == 0:
        return f"{int(hours)} ч. ({minutes} мин.)"
    return f"{hours:.1f} ч. ({minutes} мин.)"



@router.message(Command("remind"))
async def cmd_remind(message: Message):
    """Настройка периодических AI-дайджестов: интервал задаётся в минутах (например: /remind 10)."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)
    try:
        args = message.text.strip().split()

        # Если передан аргумент — установить интервал напрямую
        if len(args) >= 2:
            arg = args[1].lower().strip()

            # Выключить
            if arg in ("0", "off", "выкл", "стоп", "нет", "откл"):
                set_reminder_interval(conn, group["id"], 0)
                await message.answer(
                    "🔕 **AI-дайджест выключен.**\n\n"
                    "Бот больше не будет отправлять периодические напоминания в этот чат.\n"
                    "Чтобы включить обратно, укажите интервал в минутах: `/remind 10`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            try:
                # Поддержка формата '10', '10м', '10мин', '10m', '2h', '2ч'
                if "ч" in arg or "h" in arg:
                    hours_val = float(arg.replace("ч", "").replace("h", "").replace(",", "."))
                    minutes = int(hours_val * 60)
                else:
                    clean_arg = arg.replace("мин", "").replace("min", "").replace("m", "").replace("м", "")
                    minutes = int(clean_arg)

                if minutes < 1 or minutes > 43200:
                    await message.answer(
                        "⚠️ Укажите интервал от 1 до 43200 минут (до 30 дней).\n"
                        "Пример: `/remind 10` (каждые 10 минут)\n"
                        "Пример: `/remind 30` (каждые 30 минут)\n"
                        "Отключить: `/remind 0`",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return

                set_reminder_interval(conn, group["id"], minutes)
                int_str = format_interval_str(minutes)
                await message.answer(
                    f"✅ **AI-дайджест включён: каждые {int_str}!**\n\n"
                    f"🤖 Бот будет регулярно отправлять в этот чат:\n"
                    f"• 💡 Анализ паттернов трат и советы по оптимизации\n"
                    f"• 💸 Вежливые напоминания о долгах\n"
                    f"• 📊 Прогноз бюджета и предупреждения\n\n"
                    f"Чтобы изменить: `/remind <минуты>` (например: `/remind 15`)\n"
                    f"Чтобы отключить: `/remind 0`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            except (ValueError, TypeError):
                await message.answer(
                    "⚠️ Не удалось распознать интервал.\n"
                    "Укажите время в минутах. Например:\n"
                    "• `/remind 10` — каждые 10 минут\n"
                    "• `/remind 30` — каждые 30 минут\n"
                    "• `/remind 60` — каждый час\n"
                    "• `/remind 0` — выключить",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

        # Без аргументов — показать кнопки выбора и текущий статус
        current = get_reminder_interval(conn, group["id"])
        status = format_interval_str(current)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⏱️ 10 мин" + (" ✅" if current == 10 else ""), callback_data="remind_10"),
                InlineKeyboardButton(text="⏱️ 30 мин" + (" ✅" if current == 30 else ""), callback_data="remind_30"),
                InlineKeyboardButton(text="⏱️ 60 мин" + (" ✅" if current == 60 else ""), callback_data="remind_60"),
            ],
            [
                InlineKeyboardButton(text="⏰ 120 мин (2ч)" + (" ✅" if current == 120 else ""), callback_data="remind_120"),
                InlineKeyboardButton(text="⏰ 1440 мин (24ч)" + (" ✅" if current == 1440 else ""), callback_data="remind_1440"),
                InlineKeyboardButton(text="🔕 Выключить" + (" ✅" if current == 0 else ""), callback_data="remind_0"),
            ],
        ])

        await message.answer(
            f"🤖 **Настройка AI-дайджеста**\n\n"
            f"Текущий режим: **каждые {status}**\n\n"
            f"Вы можете задать **любое время в минутах** командой:\n"
            f"`/remind <минуты>` — например `/remind 10`, `/remind 15`, `/remind 45`\n\n"
            f"Или выберите быстрый вариант ниже:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    finally:
        conn.close()


@router.callback_query(F.data.startswith("remind_"))
async def callback_remind(callback: CallbackQuery):
    """Обработка выбора интервала AI-дайджеста через кнопки."""
    minutes = int(callback.data.replace("remind_", ""))
    chat_id = callback.message.chat.id

    conn = get_db()
    try:
        group_row = conn.execute(
            "SELECT id, name FROM groups WHERE telegram_chat_id = ?", (chat_id,)
        ).fetchone()
        if not group_row:
            await callback.answer("Группа не найдена!", show_alert=True)
            return

        group_id = group_row["id"]
        set_reminder_interval(conn, group_id, minutes)

        if minutes == 0:
            await callback.message.edit_text(
                "🔕 **AI-дайджест выключен.**\n\n"
                "Бот больше не будет отправлять периодические напоминания.\n"
                "Включить обратно: `/remind 10` или `/remind`",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            int_str = format_interval_str(minutes)
            await callback.message.edit_text(
                f"✅ **AI-дайджест включён: каждые {int_str}!**\n\n"
                f"🤖 Бот будет отправлять:\n"
                f"• 💡 AI-анализ паттернов трат\n"
                f"• 💸 Напоминания о долгах\n"
                f"• 📊 Прогноз бюджета\n\n"
                f"Задать любой интервал: `/remind <минуты>` | Выключить: `/remind 0`",
                parse_mode=ParseMode.MARKDOWN,
            )
        await callback.answer()
    finally:
        conn.close()


# ─── /debt_reminders — reminders for existing manual debts ─────

DEBT_REMINDER_LABELS = {
    "none": "Выключены", "10_min": "Каждые 10 минут", "30_min": "Каждые 30 минут",
    "3_times_a_day": "3 раза в день", "daily": "Ежедневно",
    "every_3_days": "Раз в 3 дня", "weekly": "Еженедельно",
}


def debt_reminder_controls(debt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔕 Выключить", callback_data=f"debtremind:set:{debt_id}:none"),
            InlineKeyboardButton(text="🗓 Ежедневно", callback_data=f"debtremind:set:{debt_id}:daily"),
        ],
        [
            InlineKeyboardButton(text="⏱ 30 минут", callback_data=f"debtremind:set:{debt_id}:30_min"),
            InlineKeyboardButton(text="📅 Раз в 3 дня", callback_data=f"debtremind:set:{debt_id}:every_3_days"),
        ],
        [InlineKeyboardButton(text="⬅️ К списку долгов", callback_data="debtremind:list")],
    ])


async def render_debt_reminder_list(message: Message, user_id: int, edit: bool = False):
    """Show only debts whose reminder schedule this user is allowed to change."""
    conn = get_db()
    try:
        group = get_group_by_chat_id(conn, message.chat.id)
        if not group:
            text = "Комната для этого чата не найдена. Сначала выполните /connect."
            if edit:
                await message.edit_text(text)
            else:
                await message.answer(text)
            return
        debts = [d for d in get_group_debts(conn, group["id"], status="active") + get_group_debts(conn, group["id"], status="partially_paid")
                 if int(d.get("creditor_user_id") or 0) == int(user_id) or int(d.get("created_by_user_id") or 0) == int(user_id)]
        if not debts:
            text = "Активных долгов, напоминаниями которых вы можете управлять, нет."
            if edit:
                await message.edit_text(text)
            else:
                await message.answer(text)
            return
        rows, lines = [], ["🔔 **Напоминания по долгам**", "Выберите долг, чтобы изменить его частоту:\n"]
        for debt in debts[:12]:
            title = (debt.get("description") or "Долг").strip()[:28]
            lines.append(f"• {debt['debtor_name']} → {debt['creditor_name']} · **{debt['remaining_amount']:,.0f} ₽**\n  _{title} · {DEBT_REMINDER_LABELS.get(debt.get('notification_frequency'), 'По графику')}_")
            rows.append([InlineKeyboardButton(text=f"{debt['debtor_name']} · {debt['remaining_amount']:,.0f} ₽", callback_data=f"debtremind:pick:{debt['id']}")])
        markup = InlineKeyboardMarkup(inline_keyboard=rows)
        if edit:
            await message.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        else:
            await message.answer("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    finally:
        conn.close()


@router.message(Command("debt_reminders"))
async def cmd_debt_reminders(message: Message):
    """Configure reminder frequency for existing debts from the group chat."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Команду /debt_reminders нужно отправить в группе комнаты.")
        return
    conn = get_db()
    try:
        user = get_or_create_user(conn, message.from_user.id, message.from_user.username or "", message.from_user.full_name or "Участник")
    finally:
        conn.close()
    await render_debt_reminder_list(message, user["id"])


@router.callback_query(F.data.startswith("debtremind:"))
async def callback_debt_reminders(callback: CallbackQuery):
    parts = callback.data.split(":")
    conn = get_db()
    try:
        user = get_or_create_user(conn, callback.from_user.id, callback.from_user.username or "", callback.from_user.full_name or "Участник")
    finally:
        conn.close()
    if len(parts) == 2 and parts[1] == "list":
        await render_debt_reminder_list(callback.message, user["id"], edit=True)
        await callback.answer()
        return
    if len(parts) < 3:
        await callback.answer("Не удалось обработать команду", show_alert=True)
        return

    try:
        debt_id = int(parts[2])
    except ValueError:
        await callback.answer("Некорректный долг", show_alert=True)
        return

    conn = get_db()
    try:
        group = get_group_by_chat_id(conn, callback.message.chat.id)
        debt = get_debt_by_id(conn, debt_id, group["id"] if group else None)
        managers = {int(debt.get("creditor_user_id") or 0), int(debt.get("created_by_user_id") or 0)} if debt else set()
        if not group or not debt or int(user["id"]) not in managers:
            await callback.answer("Вы не можете менять напоминания для этого долга", show_alert=True)
            return
        if parts[1] == "pick":
            text = (f"🔔 **Настройка напоминаний**\n\n"
                    f"{debt['debtor_name']} → {debt['creditor_name']} · **{debt['remaining_amount']:,.0f} ₽**\n"
                    f"_{debt.get('description') or 'Долг'}_\n\n"
                    f"Сейчас: **{DEBT_REMINDER_LABELS.get(debt.get('notification_frequency'), 'По графику')}**")
            await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=debt_reminder_controls(debt_id))
            await callback.answer()
            return
        if len(parts) != 4 or parts[1] != "set" or parts[3] not in DEBT_REMINDER_LABELS:
            await callback.answer("Некорректная частота", show_alert=True)
            return
        frequency = parts[3]
        updated = update_debt_reminder_preferences(conn, debt_id, frequency)
        text = (f"✅ Напоминания обновлены\n\n{updated['debtor_name']} → {updated['creditor_name']} · **{updated['remaining_amount']:,.0f} ₽**\n"
                f"Новый режим: **{DEBT_REMINDER_LABELS[frequency]}**")
        await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=debt_reminder_controls(debt_id))
        await callback.answer("Сохранено")
    finally:
        conn.close()


# ─── /app или /webapp ─────────────────────────────────────────

@router.message(Command("app"))
@router.message(Command("webapp"))
async def cmd_webapp(message: Message):
    """Открыть интерактивный Mini App дашборд."""
    user, group, conn = ensure_user_and_group(message)
    if group:
        group_id = group["id"]
    else:
        user_groups = get_user_groups(conn, user["id"])
        group_id = user_groups[0]["id"] if user_groups else 1
    conn.close()

    is_priv = (message.chat.type == "private")
    url = get_current_webapp_url(group_id)
    keyboard = get_webapp_keyboard(group_id, "SberWise — ваш умный помощник", is_private=is_priv)

    title = message.chat.title or "SberWise"
    text = (
        f"📱 **Приложение SberWise · «{title}»**\n\n"
        f"• Аналитика расходов и круговая диаграмма\n"
        f"• Матрица взаиморасчетов и сальдо каждого\n"
        f"• 🏆 Альтернативный скоринг Сбера (300–850)\n"
        f"• 🤖 Предиктивная аналитика сгорания бюджета\n\n"
    )
    if is_priv:
        text += "Нажмите кнопку ниже, чтобы открыть SberWise прямо в Telegram:"
    else:
        text += (
            f"🌐 Прямая ссылка: {url}\n\n"
            "Нажмите кнопку ниже, чтобы открыть SberWise:"
        )

    await message.answer(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


# ─── /score (Альтернативный Скоринг Сбера) ───────────────────

@router.message(Command("score"))
async def cmd_score(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)

    try:
        members = get_group_members_users(conn, group["id"])
        balances = get_group_balances(conn, group["id"])

        lines = [
            "🏆 **Альтернативный Скоринг Сбера (300–850 FICO)**\n",
            "_Оценка финансовой дисциплины и кредитоспособности участников на основе микротранзакций в группе:_\n"
        ]

        for member in members:
            uid = member["id"]
            bal = balances.get(uid, 0.0)
            exp_count = get_user_expense_count(conn, uid, group["id"])

            paid_row = conn.execute(
                "SELECT SUM(amount) FROM expenses WHERE paid_by = ? AND group_id = ?",
                (uid, group["id"]),
            ).fetchone()
            paid_total = paid_row[0] or 0.0

            share_row = conn.execute("""
                SELECT SUM(es.share) FROM expense_splits es
                JOIN expenses e ON e.id = es.expense_id
                WHERE es.user_id = ? AND e.group_id = ?
            """, (uid, group["id"])).fetchone()
            share_total = share_row[0] or 0.0

            receipts_count = conn.execute(
                "SELECT COUNT(*) FROM expenses WHERE paid_by = ? AND group_id = ? AND (description LIKE '%чек%' OR description LIKE '%оплата%')",
                (uid, group["id"]),
            ).fetchone()[0] or 0

            profile = calculate_comprehensive_score(
                user_id=uid,
                user_display_name=member["display_name"],
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

            score = profile["score"]
            grade = profile["grade"]
            badge = profile["badge"]
            pct = profile["percentage"]
            bar_len = int(pct / 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)

            lines.append(
                f"👤 **{member['display_name']}** — {badge}\n"
                f"   📊 Скоринг: **{score}** / 850 `[{bar}]` ({grade})\n"
                f"   • Дисциплина: {profile['factors']['discipline']['value']}% | Чеки: {receipts_count}\n"
                f"   • Оплачено: {paid_total:,.0f}₽ | Сальдо: {bal:+,.0f}₽\n"
                f"   💬 _{profile['verdict']}_\n"
            )

        lines.append("💡 _Сбер может использовать этот скоринг для одобрения кредитных карт студентам и фрилансерам без 2-НДФЛ._")

        await message.answer(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_webapp_keyboard(group['id'], "📱 Открыть Скоринг-карты в WebApp")
        )

    except Exception as e:
        logger.error(f"Error in /score: {e}", exc_info=True)
        await message.answer("❌ Ошибка при расчёте скоринга.")
    finally:
        conn.close()


# ─── /budget и /forecast (Предиктивная аналитика) ────────────

@router.message(Command("budget"))
@router.message(Command("forecast"))
async def cmd_budget(message: Message):
    """Предиктивная аналитика бюджета (AI-фича из кейса Сбера)."""
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)

    try:
        totals = get_category_totals(conn, group["id"])
        total_spent = sum(totals.values())

        if total_spent <= 0:
            await message.answer("📭 В группе пока нет трат для прогнозирования бюджета.")
            return

        now = datetime.now()
        forecast = calculate_budget_forecast(
            total_spent_month=total_spent,
            days_elapsed=max(1, now.day),
            days_in_month=30,
            target_budget=max(50000.0, total_spent * 1.35),
        )

        pct = int(forecast["percent_used"])
        bar_len = min(10, int(pct / 10))
        bar = "█" * bar_len + "░" * (10 - bar_len)

        text = (
            f"⚡ **Предиктивный анализ бюджета группы:**\n\n"
            f"💰 Всего потрачено: **{total_spent:,.0f}₽** из лимита **{forecast['target_budget']:,.0f}₽**\n"
            f"📊 Заполнено: `[{bar}]` **{forecast['percent_used']}%**\n"
            f"🔥 Скорость трат (burn rate): **{forecast['daily_burn_rate']:,.0f}₽/день**\n"
            f"📈 Прогноз на конец месяца: **{forecast['projected_month_end']:,.0f}₽**\n"
            f"Статус: **{forecast['status']}**\n\n"
            f"{forecast['forecast_message']}\n"
        )

        await message.answer(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_webapp_keyboard(group['id'], "📱 Открыть Дашборд бюджета")
        )

    except Exception as e:
        logger.error(f"Error in /budget: {e}", exc_info=True)
        await message.answer("❌ Ошибка при прогнозировании бюджета.")
    finally:
        conn.close()


# ─── /ai_status ───────────────────────────────────────────────

@router.message(Command("ai_status"))
async def cmd_ai_status(message: Message):
    """Диагностика активных AI-модулей."""
    status_msg = await message.answer("🔍 Проверяю состояние AI-провайдеров...")
    try:
        status = await get_ai_engine_status()

        lines = [
            "🤖 **Статус AI-модулей бота:**\n",
            f"⭐ **Активный провайдер:** `{status['active_provider']}`\n",
            f"1. **Локальный семантический NLP**: ✅ `{status['local_nlp']['detail']}`",
            f"2. **OpenAI GPT-4o-mini**: {'✅' if status['openai']['status'] == 'active' else '⚠️'} `{status['openai']['detail']}`",
            f"3. **Google Gemini**: {'✅' if status['gemini']['status'] == 'active' else 'ℹ️'} `{status['gemini']['detail']}`\n",
            "💡 _Если пополнить баланс OpenAI на 5$, бот автоматически переключится на GPT-4o-mini!_"
        ]

        await status_msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error in /ai_status: {e}", exc_info=True)
        await status_msg.edit_text("❌ Ошибка при проверке статуса AI.")


# ─── /tips ────────────────────────────────────────────────────

@router.message(Command("tips"))
async def cmd_tips(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("⚠️ Эта команда работает только в групповых чатах!")
        return

    user, group, conn = ensure_user_and_group(message)

    try:
        totals = get_category_totals(conn, group["id"])

        if not totals:
            await message.answer("📭 Пока недостаточно данных для анализа. Добавьте несколько расходов!")
            return

        await message.answer("🤖 Анализирую ваши расходы...")

        summary = "\n".join([f"- {cat}: {amt:,.0f}₽" for cat, amt in totals.items()])
        summary += f"\n\nИтого: {sum(totals.values()):,.0f}₽"

        tips = await generate_spending_tips(summary)
        await message.answer(f"💡 **AI-советы по оптимизации:**\n\n{tips}", parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error in /tips: {e}", exc_info=True)
        await message.answer("❌ Ошибка при генерации советов.")
    finally:
        conn.close()


# ─── /help ────────────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 **Команды бота SberWise:**\n\n"
        "📱 **Mini App:**\n"
        "• `/app` или `/webapp` — открыть интерактивный дашборд\n\n"
        "💳 **Расходы и чеки:**\n"
        "• `/add 500 обед` — записать расход\n"
        "• Или текстом: _\"купил хлеб 80р\"_\n"
        "• 📸 Фото кассового чека (QR-код ФНС)\n"
        "• 📄 PDF-квитанция из Сбера или банка\n\n"
        "⚖️ **Баланс и взаиморасчеты:**\n"
        "• `/balance` — кто кому должен (с графиком)\n"
        "• `/simplify` — оптимальные переводы (минимум транзакций)\n"
        "• `/settle @user 300` — отметить возврат долга\n"
        "• `/budget_limit 50000` — установить месячный лимит комнаты\n"
        "• `/reset` — 🗑️ **обнулить траты за этот месяц** (сброс в 0 ₽)\n\n"
        "🏆 **Аналитика и Скоринг (Кейс 3 Сбер):**\n"
        "• `/score` — альтернативный скоринг Сбера (300–850 FICO)\n"
        "• `/budget` или `/forecast` — предиктивный прогноз исчерпания бюджета\n"
        "• `/chart` — круговая диаграмма по категориям\n"
        "• `/tips` — AI-советы по оптимизации трат\n"
        "• `/history` — последние 15 операций\n"
        "• `/ai_status` — состояние подключенных AI-сетей\n\n"
        "🤖 **AI-дайджест и напоминания:**\n"
        "• `/remind <минуты>` — задать любой интервал в минутах (напр. `/remind 10`)\n"
        "• `/remind` — меню быстрых кнопок напоминаний\n"
        "• `/remind 0` — выключить дайджест\n"
        "• `/debt_reminders` — изменить напоминания уже созданного долга\n"
    )
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)


# ─── Запуск ───────────────────────────────────────────────────

async def ai_digest_scheduler(bot: Bot):
    """
    Фоновый планировщик AI-дайджестов.
    Проверяет каждые 30 секунд, нужно ли отправить дайджест в какую-либо группу.
    """
    logger.info("🤖 AI-дайджест планировщик запущен")
    while True:
        try:
            await asyncio.sleep(30)  # Проверяем каждые 30 секунд для минутной точности

            conn = get_db()
            try:
                groups = get_all_groups_with_reminders(conn)
                now = datetime.now()

                for grp in groups:
                    interval_minutes = grp.get("reminder_interval_minutes") or (grp.get("reminder_interval_hours", 0) * 60)
                    if not interval_minutes or interval_minutes <= 0:
                        continue

                    last_at = grp.get("last_reminder_at")

                    # Проверяем, прошло ли достаточно времени
                    if last_at:
                        try:
                            last_dt = datetime.fromisoformat(last_at)
                            if now - last_dt < timedelta(minutes=interval_minutes):
                                continue  # Ещё рано
                        except (ValueError, TypeError):
                            pass  # Некорректная дата — отправляем

                    # Пришло время отправить AI-дайджест!
                    group_id = grp["id"]
                    chat_id = grp["telegram_chat_id"]
                    group_name = grp.get("name", "Группа")

                    # Собираем данные
                    members = get_group_members_users(conn, group_id)
                    category_totals = get_category_totals(conn, group_id)
                    total_spent = sum(category_totals.values())
                    balances = get_group_balances(conn, group_id)
                    debts_raw = simplify_debts(balances)

                    # Пропускаем пустые группы (нет трат и нет долгов)
                    if total_spent == 0 and len(debts_raw) == 0:
                        continue

                    # Подготавливаем simplified_debts с именами
                    simplified_debts = []
                    for from_id, to_id, amount in debts_raw:
                        from_user = get_user_by_id(conn, from_id)
                        to_user = get_user_by_id(conn, to_id)
                        simplified_debts.append({
                            "from_name": from_user["display_name"] if from_user else f"User#{from_id}",
                            "to_name": to_user["display_name"] if to_user else f"User#{to_id}",
                            "amount": amount,
                        })

                    # Прогноз бюджета
                    target_limit = get_group_budget_limit(conn, group_id)
                    forecast = calculate_budget_forecast(
                        total_spent_month=total_spent,
                        days_elapsed=max(1, now.day),
                        days_in_month=30,
                        target_budget=target_limit,
                    )

                    # Генерируем AI-дайджест
                    digest_text = await generate_ai_digest(
                        group_name=group_name,
                        category_totals=category_totals,
                        simplified_debts=simplified_debts,
                        budget_forecast=forecast,
                        total_expenses=total_spent,
                        members_count=len(members),
                    )

                    # Отправляем в чат
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=digest_text,
                            parse_mode=ParseMode.MARKDOWN,
                        )
                        update_last_reminder_at(conn, group_id)
                        logger.info(f"🤖 AI-дайджест отправлен в группу «{group_name}» (chat_id={chat_id})")
                    except Exception as e:
                        logger.warning(f"Ошибка отправки AI-дайджеста в чат {chat_id}: {e}")

            finally:
                conn.close()

        except asyncio.CancelledError:
            logger.info("🤖 AI-дайджест планировщик остановлен")
            break
        except Exception as e:
            logger.error(f"Ошибка в AI-дайджест планировщике: {e}")
            await asyncio.sleep(60)  # При ошибке ждём минуту



# ─── Фоновый воркер напоминаний о долгах ───────────────────────

async def debt_reminder_worker(bot: Bot):
    """
    Фоновый воркер напоминаний о долгах.
    Проверяет раз в 30 секунд таблицу debts на наличие долгов, требующих уведомления:
    1. Напоминания по расписанию (10 мин, 30 мин, 3 раза в день, ежедневно, раз в 3 дня, custom в минутах).
    2. Pre-due напоминание (за 24 часа до наступления срока).
    3. Доставка должнику в ЛС; при ошибке (или если нет telegram_id) — фоллбэк кредитору.
    4. Автоматический расчёт и обновление следующего времени напоминания.
    """
    logger.info("🔔 Фоновый воркер напоминаний о долгах запущен")
    while True:
        try:
            await asyncio.sleep(30)
            conn = get_db()
            now = datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")

            pending = get_pending_debt_reminders(conn, now_str)
            for debt in pending:
                debt_id = debt["id"]
                # A second running worker (or a restart overlap) must not deliver
                # the same reminder before this worker advances its schedule.
                if not claim_due_debt_reminder(conn, debt_id, now_str):
                    continue
                debtor_tg_id = None
                creditor_tg_id = None

                if debt["debtor_user_id"]:
                    du = get_user_by_id(conn, debt["debtor_user_id"])
                    if du and du.get("telegram_id"):
                        debtor_tg_id = du["telegram_id"]

                if debt["creditor_user_id"]:
                    cu = get_user_by_id(conn, debt["creditor_user_id"])
                    if cu and cu.get("telegram_id"):
                        creditor_tg_id = cu["telegram_id"]

                is_pre_due = False
                if debt.get("due_datetime") and not debt.get("pre_due_reminder_sent_at"):
                    try:
                        due_dt = datetime.strptime(debt["due_datetime"], "%Y-%m-%d %H:%M:%S")
                        if due_dt - timedelta(hours=24) <= now < due_dt:
                            is_pre_due = True
                    except Exception:
                        pass

                is_overdue = bool(debt.get("due_datetime") and debt["due_datetime"] < now_str)

                if is_pre_due:
                    title = "⏳ **Напоминание о приближении срока возврата долга**"
                elif is_overdue:
                    title = "🔴 **Внимание! Срок возврата долга истёк**"
                else:
                    title = "🔔 **Напоминание о задолженности**"

                msg_text = (
                    f"{title}\n\n"
                    f"Кому: **{debt['creditor_name']}**\n"
                    f"Сумма к возврату: **{debt['remaining_amount']:,.2f} ₽**"
                )
                if debt.get("description"):
                    msg_text += f"\n📌 Назначение: {debt['description']}"
                if debt.get("due_datetime"):
                    msg_text += f"\n⏰ Срок: {debt['due_datetime']}"
                msg_text += f"\nГруппа: «{debt.get('group_name', 'SberWise')}»"

                sent_to_debtor = False
                if debtor_tg_id:
                    try:
                        await bot.send_message(
                            chat_id=debtor_tg_id,
                            text=msg_text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        sent_to_debtor = True
                    except Exception as send_err:
                        logger.warning(f"Не удалось отправить напоминание должнику {debtor_tg_id}: {send_err}")

                sent_to_creditor = False
                if not sent_to_debtor and creditor_tg_id:
                    fallback_text = (
                        f"⚠️ **Уведомление кредитору**\n\n"
                        f"Подошло время напоминания по долгу от **{debt['debtor_name']}** на сумму **{debt['remaining_amount']:,.2f} ₽**.\n"
                        f"Бот не смог отправить сообщение должнику напрямую в Telegram (пользователь не запустил бота в ЛС).\n"
                        f"Напомните ему в общем чате или лично!"
                    )
                    try:
                        await bot.send_message(
                            chat_id=creditor_tg_id,
                            text=fallback_text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        sent_to_creditor = True
                    except Exception as fb_err:
                        logger.warning(f"Не удалось отправить фоллбэк кредитору {creditor_tg_id}: {fb_err}")

                freq = debt.get("notification_frequency", "none")
                custom_h = debt.get("custom_reminder_interval_hours")
                custom_m = debt.get("custom_reminder_interval_minutes")
                next_rem = calculate_next_reminder(
                    freq, now, custom_minutes=custom_m, custom_hours=custom_h
                ) if freq != "none" else None

                update_debt_reminder_schedule(
                    conn=conn,
                    debt_id=debt_id,
                    last_reminder_at=now_str,
                    next_reminder_at=next_rem,
                    pre_due_reminder_sent_at=now_str if is_pre_due else debt.get("pre_due_reminder_sent_at"),
                )
                if not (sent_to_debtor or sent_to_creditor):
                    logger.warning("Напоминание debt_id=%s не доставлено; следующая попытка будет по расписанию", debt_id)

            conn.close()
        except asyncio.CancelledError:
            logger.info("🔔 Фоновый воркер напоминаний остановлен")
            break
        except Exception as e:
            logger.error(f"Ошибка в воркере напоминаний: {e}", exc_info=True)


async def main():
    init_db()
    logger.info("✅ База данных инициализирована")

    # 1. Запуск встроенного веб-сервера для Telegram Mini App
    web_runner = await start_web_server(port=WEBAPP_PORT)

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # 2. Определение URL Telegram Mini App и Menu Button (Section 2, 3, 11, 13)
    if IS_PRODUCTION_DEPLOYMENT:
        logger.info(f"🚀 ПРОДАКШН РЕЖИМ АКТИВЕН: Постоянный HTTPS URL = {WEBAPP_URL}")
        logger.info("🛡️ Эфемерные туннели полностью отключены. Сервис работает на постоянном домене.")
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="SberWise",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
            )
            logger.info(f"✅ Telegram Menu Button установлен на постоянный URL: {WEBAPP_URL}")
        except Exception as e:
            logger.warning(f"Не удалось установить MenuButtonWebApp: {e}")
    else:
        # Локальная разработка: опрос и запуск SSH-туннеля для тестирования на ПК
        loop = asyncio.get_running_loop()

        def on_tunnel_url_changed(new_url: str):
            if not new_url:
                return
            async def _do_update():
                try:
                    await bot.set_chat_menu_button(
                        menu_button=MenuButtonWebApp(
                            text="SberWise",
                            web_app=WebAppInfo(url=f"{new_url}/webapp")
                        )
                    )
                    logger.info(f"🔄 Telegram Menu Button обновлен: {new_url}/webapp")
                except Exception as ex:
                    logger.warning(f"Не удалось обновить MenuButtonWebApp: {ex}")
            asyncio.run_coroutine_threadsafe(_do_update(), loop)

        set_on_url_change(on_tunnel_url_changed)

        # SSH tunnel performs blocking subprocess I/O; keep it off the asyncio event loop
        # so the local API and Telegram polling remain responsive while it connects.
        tunnel_url = await asyncio.to_thread(start_tunnel, port=WEBAPP_PORT)
        if tunnel_url:
            logger.info(f"🌐 Dev-туннель активен: {tunnel_url}/webapp")
            try:
                await bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(
                        text="SberWise",
                        web_app=WebAppInfo(url=f"{tunnel_url}/webapp")
                    )
                )
                logger.info("✅ Установлена нативная кнопка меню Telegram: SberWise")
            except Exception as e:
                logger.warning(f"Не удалось установить MenuButtonWebApp: {e}")
        else:
            logger.info(f"ℹ️ WebApp доступен локально: http://localhost:{WEBAPP_PORT}/webapp")

    # 4. Запуск фонового AI-дайджест планировщика
    scheduler_task = asyncio.create_task(ai_digest_scheduler(bot))
    logger.info("🤖 AI-дайджест планировщик активирован")

    # 5. Запуск фонового воркера напоминаний о долгах
    debt_worker_task = asyncio.create_task(debt_reminder_worker(bot))
    logger.info("🔔 Воркер напоминаний о долгах активирован")

    logger.info("🚀 СберСплит Бот + Mini App запущены!")
    try:
        # Устойчивое удаление вебхука при старте (с ретраями при сетевых сбоях)
        for attempt in range(5):
            try:
                await bot.delete_webhook(drop_pending_updates=True)
                break
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}/5 подключения к Telegram API ({e}), повтор через 2 сек...")
                await asyncio.sleep(2)

        backoff = BackoffConfig(min_delay=0.5, max_delay=3.0, factor=1.2, jitter=0.1)
        while True:
            try:
                await dp.start_polling(bot, handle_as_tasks=True, backoff_config=backoff)
                break
            except Exception as e:
                logger.warning(f"Сетевой сбой в Telegram polling ({e}), повтор через 3 сек...")
                await asyncio.sleep(3)
    finally:
        scheduler_task.cancel()
        debt_worker_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        try:
            await debt_worker_task
        except asyncio.CancelledError:
            pass
        stop_tunnel()
        await web_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
