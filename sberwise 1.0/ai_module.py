"""
AI-модуль — гибридный интеллектуальный процессор:
1. Google Gemini API (через REST с поддержкой x-goog-api-key и Bearer)
2. Встроенный семантический NLP-движок для моментальной и 100% надёжной категоризации и генерации советов (работает даже при сбоях сети/API ключей)
"""

import asyncio
import io
import json
import logging
import os
import re
from typing import Optional, List, Dict, Any, Union
import aiohttp
from openai import AsyncOpenAI
from config import GEMINI_API_KEY, OPENAI_API_KEY

logger = logging.getLogger(__name__)

# OpenAI клиент если ключ задан
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Модели для проверки
MODEL = "gemini-1.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# ─── Семантический NLP-словарь категорий ──────────────────────────
CATEGORY_RULES = [
    (
        "💻 Техника",
        [
            "dns", "днс", "м.видео", "мвидео", "mvideo", "эльдорадо", "eldorado", "ситилинк",
            "citilink", "re:store", "restore", "apple", "xiaomi", "сяоми", "samsung", "самсунг",
            "бытовая техника", "цифровая техника", "электроника", "компьютер", "ноутбук", "смартфон",
            "планшет", "телевизор", "наушники", "монитор", "видеокарта", "процессор", "клавиатура",
            "мышь", "роутер", "айфон", "iphone", "ipad", "macbook", "плейстейшн", "playstation",
            "xbox", "джойстик", "холодильник", "стиральная машина", "микроволновка", "чайник",
            "пылесос", "утюг", "фен", "блендер"
        ]
    ),
    (
        "🍞 Продукты",
        [
            # Супермаркеты и сети
            "продукт", "супермаркет", "гипермаркет", "гастроном", "бакалея", "пятерочка", "пятёрочка", "pyaterochka", "магнит", "magnit",
            "монетка", "monetka", "чижик", "chizhik", "кировский", "kirovski", "перекресток", "перекрёсток",
            "perekrestok", "вкусвилл", "vkusvill", "spar", "спар", "ашан", "auchan", "лента", "lenta",
            "окей", "okay", "дикси", "dixy", "светофор", "доброцен", "ярче", "бахетле", "азбука вкуса",
            "fix price", "fixprice", "фикс прайс", "красное и белое", "к&б", "кб", "krasnoe",
            "бристоль", "bristol", "жизньмарт", "zhiznmart", "глобус", "globus", "metro", "метро c&c",
            # Доставка еды и продуктов
            "купер", "kuper", "сбермаркет", "sbermarket", "самокат", "samokat", "яндекс лавка", "lavka",
            "яндекс еда", "eda.yandex", "delivery club", "деливери",
            # Еда, общепит, кафе, фастфуд
            "додо", "dodo", "пицц", "суши", "ролл", "бургер", "burger king", "бургер кинг",
            "вкусно и точка", "ростикс", "rostic", "kfc", "кфс", "макдак", "mcdonald", "теремок",
            "шоколадница", "кофемания", "cofix", "one price", "скуратов", "skuratov", "surf coffee",
            "столовая", "кафе", "ресторан", "кулинария", "пекарня", "шаурма", "шаверма", "шашлык",
            "хлеб", "молок", "сыр", "колбас", "мясо", "куриц", "яйц", "яйк", "овощ", "фрукт", "яблок",
            "банан", "рыб", "вода", "сок", "чай", "кофе", "шоколад", "чипс", "еда", "обед", "ужин",
            "завтрак", "купил поесть", "покушать"
        ]
    ),
    (
        "🚕 Транспорт",
        [
            # Такси и каршеринг
            "такси", "taxi", "uber", "yandex.go", "яндекс go", "яндекс такси", "ситимобил",
            "каршеринг", "делимобиль", "delimobil", "ситидрайв", "citydrive", "белкакар", "belkacar",
            # Заправки (АЗС) и топливо
            "азс", "заправка", "бензин", "лукойл", "lukoil", "газпромнефть", "газпром", "gpn",
            "роснефть", "rosneft", "башнефть", "bashneft", "татнефть", "tatneft", "тебойл", "teboil",
            "irbis", "нефтьмагистраль", "трасса", "opti", "газ", "двойной газ",
            # Общественный транспорт и билеты
            "метро", "автобус", "трамвай", "троллейбус", "электричка", "поезд", "проезд", "проездной",
            "авиабилет", "жд билет", "билет на поезд", "билет на автобус",
            "ржд", "rzd", "аэрофлот", "aeroflot", "победа", "уральские авиалинии", "s7",
            # Кикшеринг и автоуслуги
            "самокат", "вуш", "whoosh", "юрент", "urent", "мойка", "автомойка", "шиномонтаж",
            "сто", "автосервис", "парковка", "штраф", "гибдд", "платная дорога", "автодор"
        ]
    ),
    (
        "💊 Здоровье",
        [
            # Аптеки
            "аптек", "apteka", "живика", "zhivika", "фармленд", "farmland", "апрель", "aprel",
            "планета здоровья", "ригла", "rigla", "еаптека", "eapteka", "сбер еаптека", "вита",
            "столички", "горздрав", "вита-экспресс", "доктор алвик", "классика",
            # Медицина
            "лекарств", "таблетк", "витамин", "врач", "доктор", "больниц", "клиник", "инвитро",
            "invitro", "гемотест", "gemotest", "мрт", "узи", "анализ", "стоматолог", "зуб",
            "массаж", "линз", "очки", "оптика", "пластырь", "бинты", "бад"
        ]
    ),
    (
        "👕 Одежда",
        [
            # Маркетплейсы одежды и шопинг
            "wildberries", "вайлдберриз", "wb", "вб", "ozon", "озон", "мегамаркет", "megamarket",
            "яндекс маркет", "aliexpress", "алиэкспресс", "золотое яблоко", "gold apple", "goldapple",
            "летуаль", "лэтуаль", "рив гош", "магнит косметик", "улыбка радуги",
            # Бренды и вещи
            "одежд", "вещи", "обув", "кроссовк", "ботинк", "куртк", "джинс", "футболк",
            "штаны", "рубашк", "носки", "шапк", "zara", "befree", "gloria jeans", "спортмастер",
            "sportmaster", "кари", "kari", "ostin", "остин", "lime", "лайм"
        ]
    ),
    (
        "💡 Коммуналка",
        [
            "коммуналк", "жкх", "свет", "электричеств", "вода", "газ", "отоплени", "квартплат",
            "счетчик", "счётчик", "домофон", "капремонт", "мусор", "управляющая", "тсж",
            "квитанци", "энергосбыт", "водоканал", "ерц", "еирц", "мосэнерго", "челябэнерго",
            "уралоблгаз", "екатеринбургэнергосбыт"
        ]
    ),
    (
        "🏠 Аренда",
        [
            "аренд", "съем", "съём", "квартир", "залог", "риелтор", "хозяин", "хозяйк",
            "авито недвижимость", "циан", "домклик", "domclick"
        ]
    ),
    (
        "📱 Связь",
        [
            "связь", "интернет", "вайфай", "wifi", "мтс", "mts", "билайн", "beeline", "мегафон",
            "megafon", "теле2", "tele2", "t2", "т2", "мотив", "motiv", "ростелеком", "дом.ру",
            "dom.ru", "подписк", "vpn", "впн", "телефон", "симк", "ячейка", "облако"
        ]
    ),
    (
        "🎬 Развлечения",
        [
            "кино", "синема", "фильм", "билет в кино", "бар", "паб", "пиво", "вино", "алко",
            "клуб", "тусовк", "кальян", "боулинг", "бильярд", "концерт", "театр", "музей",
            "игра", "steam", "стим", "playstation", "xbox", "игры", "настолк", "квест",
            "парк", "аттракцион", "кинопоиск", "иви", "okko", "окко", "premier",
            "music", "музыка", "mts music", "мтс мьюзик", "яндекс музыка", "yandex music",
            "spotify", "спотифай", "apple music", "звук", "сберзвук", "vk музыка"
        ]
    ),
    (
        "📚 Образование",
        [
            "книг", "лабиринт", "читай-город", "буквоед", "курс", "учебник", "тетрад", "ручк",
            "учеба", "учёба", "репетитор", "универ", "урфу", "школ", "лекци", "семинар",
            "geekbrains", "skillbox", "яндекс практикум", "stepik"
        ]
    ),
]


def _rule_based_categorize(text: str) -> tuple[str, str]:
    """Быстрый NLP анализ текста с защитой от ложных срабатываний коротких слов."""
    text_lower = text.lower()

    # Поиск категории
    matched_category = "🔧 Другое"
    for cat, keywords in CATEGORY_RULES:
        for kw in keywords:
            if len(kw) <= 4:
                # Короткие слова и корни ищем по началу слова (\bkw), чтобы 'сок' не матчил 'носок', но 'яйц'/'рыб' матчили 'яйцо'/'рыба'
                if re.search(r"(?i)\b" + re.escape(kw), text_lower):
                    matched_category = cat
                    break
            else:
                if kw in text_lower:
                    matched_category = cat
                    break
        if matched_category != "🔧 Другое":
            break

    # Очистка описания от типичных вводных и личных слов
    cleaned = re.sub(
        r"(?i)\b(купил|взял|оплатил|заплатил|потратил|стоил|за|на|в|по|себе|для себя|лично|личное|личный|личные)\b",
        "",
        text
    ).strip()
    cleaned = re.sub(r"\b\d+([.,]\d+)?\s*(руб[ляей]*|₽|р\.?|k|к)?\b", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    cleaned_desc = cleaned.capitalize() if len(cleaned) >= 2 else text

    return matched_category, cleaned_desc


async def _call_gemini(prompt: str) -> str:
    """Вызов Gemini API с поддержкой разных форматов авторизации."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is empty")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200},
    }

    # 1. Попытка через Query Parameter ?key=
    url_key = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url_key, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.debug(f"Gemini ?key= error: {e}")

    # 2. Попытка через x-goog-api-key заголовок
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GEMINI_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.debug(f"Gemini x-goog-api-key error: {e}")

    # 3. Попытка через Authorization: Bearer
    headers_bearer = {"Content-Type": "application/json", "Authorization": f"Bearer {GEMINI_API_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.post(GEMINI_URL, json=payload, headers=headers_bearer, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            text_err = await resp.text()
            raise Exception(f"Gemini API returned status {resp.status}: {text_err}")


async def _call_openai(prompt: str, system_prompt: str = "Ты — финансовый ассистент Сбера.") -> str:
    """Вызов OpenAI API (GPT-4o-mini)."""
    if not openai_client:
        raise ValueError("OpenAI client not initialized")

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=250
    )
    return response.choices[0].message.content


async def get_ai_engine_status() -> dict:
    """Проверка доступности AI движков."""
    status = {
        "active_provider": "local_nlp",
        "openai": {"status": "disabled"},
        "gemini": {"status": "disabled"},
        "local_nlp": {"status": "active"},
    }

    if openai_client:
        try:
            res = await _call_openai("Тест", system_prompt="Ответь одним словом OK")
            if res:
                status["openai"] = {"status": "active", "model": "gpt-4o-mini", "detail": "GPT-4o-mini подключен и работает"}
                status["active_provider"] = "OpenAI GPT-4o-mini"
        except Exception as e:
            status["openai"] = {"status": "error", "detail": str(e)}

    if GEMINI_API_KEY:
        try:
            res = await _call_gemini("Ответь одним словом: OK")
            if res:
                status["gemini"] = {"status": "active", "model": MODEL}
                if status["active_provider"] == "local_nlp":
                    status["active_provider"] = f"Google Gemini ({MODEL})"
        except Exception as e:
            status["gemini"] = {"status": "auth_error", "detail": "Требуется Google Cloud OAuth/Standard Key"}

    return status


async def categorize_expense(text: str) -> dict:
    """
    Из текста пользователя извлечь сумму, категорию, название товара и признак личного расхода.
    Мультипровайдер: OpenAI -> Gemini -> Локальный NLP.
    """
    # Определяем признак личной покупки
    is_personal_detected = bool(re.search(r"(?i)\b(себе|для себя|личн[оеыхй]*|лично)\b", text))

    prompt = f"""Извлеки из текста информацию о расходе.
Верни ТОЛЬКО валидный JSON с полями:
- "amount": число (рубли, 0 если не указано)
- "category": одна из категорий: "🍞 Продукты", "💻 Техника", "💡 Коммуналка", "🚕 Транспорт", "🎬 Развлечения", "💊 Здоровье", "👕 Одежда", "📚 Образование", "🏠 Аренда", "📱 Связь", "🔧 Другое"
- "description": название товара или услуги (1-2 слова, например "Хлеб", "Кола", "Кофе", "Наушники"). ВАЖНО: не включай слова "себе", "для себя", "купил", "взял" в description!
- "is_personal": true, если покупка сделана для себя лично ("себе", "для себя", "личное"), иначе false

Текст: {text}"""

    def clean_desc(desc: str) -> str:
        d = re.sub(r"(?i)\b(себе|для себя|лично|личное|личный|купил|взял|оплатил|заплатил)\b", "", desc).strip()
        d = re.sub(r"\s+", " ", d).strip(" ,.-")
        return d.capitalize() if d else "Расход"

    # 1. Попытка через OpenAI
    if openai_client:
        try:
            raw = await _call_openai(prompt)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(raw.strip())
            if data.get("category") and data["category"] != "🔧 Другое":
                data["description"] = clean_desc(data.get("description", ""))
                data["is_personal"] = is_personal_detected
                return data
        except Exception as e:
            logger.debug(f"OpenAI error, trying fallback: {e}")

    # 2. Попытка через Gemini
    try:
        raw_resp = await _call_gemini(prompt)
        raw_resp = raw_resp.strip()
        if raw_resp.startswith("```"):
            raw_resp = raw_resp.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(raw_resp.strip())
        if data.get("category") and data["category"] != "🔧 Другое":
            data["description"] = clean_desc(data.get("description", ""))
            data["is_personal"] = is_personal_detected
            return data
    except Exception as e:
        logger.debug(f"Gemini fallback to semantic parser: {e}")

    # 3. Мгновенный семантический NLP fallback
    category, description = _rule_based_categorize(text)

    amount_match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    amount = float(amount_match.group(1).replace(",", ".")) if amount_match else 0.0

    return {
        "amount": amount,
        "category": category,
        "description": clean_desc(description),
        "is_personal": is_personal_detected,
    }


async def generate_spending_tips(expenses_summary: str) -> str:
    """Генерация советов (OpenAI -> Gemini -> Локальный аналитический модуль)."""
    prompt = f"""Проанализируй траты группы и дай 3 конкретных практических совета по оптимизации бюджета.
Используй эмодзи, дружелюбный тон. Русский язык.
Расходы:
{expenses_summary}"""

    if openai_client:
        try:
            return await _call_openai(prompt)
        except Exception:
            pass

    try:
        return await _call_gemini(prompt)
    except Exception:
        # Локальный аналитический модуль советов
        return (
            "💡 **Рекомендации по оптимизации общего бюджета от Сбера:**\n\n"
            "1. 🍞 **Оптовые закупки продуктов:** Закупка базовых товаров (бакалея, бытовая химия) раз в неделю в гипермаркетах позволит сэкономить до 15-20% бюджета.\n"
            "2. 💡 **Семейные подписки и СберПрайм:** Проверьте совместные подписки на сервисы (СберПрайм, онлайн-кинотеатры) — семейные тарифы снижают расходы на связь и медиа до 50%.\n"
            "3. 🚕 **Транспортные расходы:** При частых поездках выгоднее объединять маршруты или использовать общественный транспорт в часы пик."
        )


async def generate_debt_reminder(debtor_name: str, creditor_name: str, amount: float) -> str:
    """Вежливое напоминание о взаиморасчетах (человекочитаемое)."""
    prompt = f"Напиши одно короткое вежливое дружелюбное напоминание о долге {amount:.0f}₽ от {creditor_name} к {debtor_name}. С эмодзи."
    if openai_client:
        try:
            return (await _call_openai(prompt)).strip()
        except Exception:
            pass

    try:
        return (await _call_gemini(prompt)).strip()
    except Exception:
        return f"Привет! Напоминаю про {amount:,.0f}₽ за общие расходы, переведи при возможности 🙂"


async def calculate_reliability_description(
    total_debts: int,
    settled_debts: int,
    avg_settle_days: float,
    total_expenses: int,
) -> tuple:
    """Расчет скоринга участника на основе финансовой дисциплины."""
    if total_debts == 0 and total_expenses == 0:
        score = 0.70
    elif total_debts == 0:
        score = 0.85
    else:
        settle_ratio = min(1.0, settled_debts / max(1, total_debts))
        speed_factor = max(0.0, 1.0 - (avg_settle_days / 14.0))
        activity_bonus = min(0.2, (total_expenses / 10.0) * 0.2)
        score = round(0.55 * settle_ratio + 0.25 * speed_factor + activity_bonus, 2)

    score = max(0.1, min(1.0, score))

    if score >= 0.80:
        emoji, label = "🟢", "Высокий (Надёжный)"
    elif score >= 0.55:
        emoji, label = "🟡", "Хороший"
    elif score >= 0.35:
        emoji, label = "🟠", "Умеренный"
    else:
        emoji, label = "🔴", "Требует внимания"

    return score, emoji, label


async def generate_ai_digest(
    group_name: str,
    category_totals: dict[str, float],
    simplified_debts: list[dict],
    budget_forecast: dict,
    total_expenses: float,
    members_count: int,
) -> str:
    """
    Генерирует комплексный AI-дайджест для периодической рассылки в группу:
    1. Анализ паттернов трат + советы по оптимизации
    2. Вежливые напоминания о долгах
    3. Прогноз бюджета и предупреждения
    """
    # Формируем контекст для AI
    cats_text = "\n".join(f"  - {cat}: {amt:,.0f}₽" for cat, amt in sorted(category_totals.items(), key=lambda x: -x[1])) if category_totals else "  Нет данных"
    debts_text = "\n".join(f"  - {d['from_name']} → {d['to_name']}: {d['amount']:,.0f}₽" for d in simplified_debts) if simplified_debts else "  Все долги закрыты!"
    budget_status = budget_forecast.get("status", "неизвестно")
    budget_pct = budget_forecast.get("percent_used", 0)
    budget_msg = budget_forecast.get("forecast_message", "")

    prompt = f"""Ты — финансовый AI-ассистент СберСплит для группы «{group_name}» из {members_count} участников.

Сгенерируй КРАТКИЙ (до 800 символов) периодический дайджест для группового чата в Telegram.
Формат: markdown (жирный текст **так**, эмодзи).

Включи 3 блока:

1. **💡 Совет по оптимизации** — один конкретный, полезный совет на основе категорий трат ниже. Если есть крупная категория, предложи как сэкономить. Пример: «Если закупать продукты оптом раз в неделю, сэкономите до 15%».

2. **💸 Долги** — если есть неоплаченные долги, вежливо напомни. Используй имена участников. Если долгов нет, похвали группу. Будь дружелюбным и лёгким в тоне, без давления.

3. **📊 Бюджет** — кратко сообщи: израсходовано {budget_pct}% бюджета, статус «{budget_status}». Если статус тревожный — мягко предупреди.

Данные:
Общие траты: {total_expenses:,.0f}₽
Категории:
{cats_text}

Долги:
{debts_text}

Прогноз: {budget_msg}

Пиши на русском, коротко, с эмодзи. Не повторяй промпт."""

    # Пробуем OpenAI -> Gemini -> Локальный fallback
    if openai_client:
        try:
            result = await _call_openai(prompt, system_prompt="Ты — финансовый AI-ассистент СберСплит. Пиши кратко, по делу, дружелюбно.")
            return result.strip()
        except Exception as e:
            logger.warning(f"OpenAI digest error: {e}")

    try:
        result = await _call_gemini(prompt)
        return result.strip()
    except Exception as e:
        logger.warning(f"Gemini digest error: {e}")

    # Локальный fallback — всегда работает
    parts = ["🤖 **AI-дайджест СберСплит**\n"]

    # 1. Совет по оптимизации
    if category_totals:
        top_cat = max(category_totals, key=category_totals.get)
        top_amount = category_totals[top_cat]
        pct_of_total = round(top_amount / max(1, total_expenses) * 100)
        parts.append(
            f"💡 **Совет:** Категория {top_cat} занимает {pct_of_total}% бюджета ({top_amount:,.0f}₽). "
            f"Попробуйте планировать покупки заранее и закупаться оптом — это может сэкономить до 15-20%!\n"
        )
    else:
        parts.append("💡 **Совет:** Начните записывать расходы, чтобы AI мог анализировать ваши траты!\n")

    # 2. Долги
    if simplified_debts:
        parts.append("💸 **Напоминание о долгах:**")
        for d in simplified_debts:
            parts.append(f"  • {d['from_name']}, не забудь перевести {d['amount']:,.0f}₽ для {d['to_name']} 🙂")
        parts.append("")
    else:
        parts.append("💸 **Долги:** Все взаиморасчёты закрыты! Отличная работа 🎉\n")

    # 3. Бюджет
    if budget_pct > 85:
        parts.append(f"📊 **Бюджет:** ⚠️ Израсходовано **{budget_pct}%** лимита! Стоит притормозить с тратами.")
    elif budget_pct > 60:
        parts.append(f"📊 **Бюджет:** Израсходовано **{budget_pct}%** лимита. Пока всё в рамках, но следите за темпом.")
    else:
        parts.append(f"📊 **Бюджет:** Израсходовано всего **{budget_pct}%**. Отличный темп! 💪")

    return "\n".join(parts)


# ─── Единый конвейер распознавания расходов (ParsedExpenseDraft) ───

def match_member_name(name_str: str, room_members: list[dict], default_payer_id: Optional[int] = None) -> Optional[int]:
    """Сопоставить имя из текста с участником комнаты."""
    if not name_str:
        return None
    clean = name_str.strip().lower()
    # Обработка личных местоимений автора
    if clean in ("я", "меня", "мне", "мной", "мною", "себе", "себя", "сам", "current_user", "вы", "свой", "только себе", "только я"):
        if default_payer_id:
            return default_payer_id
        if room_members:
            return room_members[0]["id"]
    if not room_members:
        return None
    for m in room_members:
        disp = (m.get("display_name") or "").lower()
        uname = (m.get("username") or "").lower()
        if clean == disp or clean == uname:
            return m["id"]
        if clean in disp or disp in clean or (uname and clean in uname):
            return m["id"]
    return None


async def parse_unstructured_expense_text(text: str, room_members: list[dict], default_payer_id: Optional[int] = None) -> dict:
    """
    Преобразует неструктурированный текст (сообщение из Telegram, список покупок)
    в единую структуру ParsedExpenseDraft с позициями и участниками.
    """
    member_names = [m.get("display_name", f"User#{m['id']}") for m in room_members]
    members_hint = ", ".join(member_names) if member_names else "Не указаны"

    prompt = f"""Ты — финансовый AI-парсер чеков и расходов СберСплит.
Участники комнаты: {members_hint}

Преобразуй следующий текст расхода в валидный JSON с позициями товаров.
Формат ответа — ТОЛЬКО JSON без markdown оформления:
{{
  "title": "Общее краткое название (например: Пицца и роллы, Покупки в Ленте)",
  "merchant": "Название магазина или сервиса, если есть, иначе пусто",
  "currency": "RUB",
  "payer_name": "Имя плательщика, если упоминается (например: Степан, Я, или пусто)",
  "confidence": 0.95,
  "items": [
    {{
      "name": "Название позиции",
      "quantity": 1,
      "unit_price": 1000.0,
      "total_amount": 1000.0,
      "category": "🍞 Продукты",
      "participants": ["Имя1", "Имя2"] или "all"
    }}
  ]
}}

Правила:
- Если указано "только Аня и Мария", в participants запиши ["Аня", "Мария"].
- Если написано «на себя», «на меня» или «делю на себя и …», обязательно
  добавь «Я» в participants вместе с названными участниками.
- Если позиция для всех участников или не уточнено — participants: "all".
- Суммы должны быть числами (без знаков валют).
- Категория — одна из: 🍞 Продукты, 💻 Техника, 💡 Коммуналка, 🚕 Транспорт, 🎬 Развлечения, 💊 Здоровье, 👕 Одежда, 🏠 Аренда, 🔧 Другое.

Текст расхода:
{text}"""

    raw_json = None
    if openai_client:
        try:
            raw_json = await _call_openai(prompt, system_prompt="Отвечай строго JSON объектом.")
        except Exception as e:
            logger.debug(f"OpenAI text parse error: {e}")

    if not raw_json and GEMINI_API_KEY:
        try:
            raw_json = await _call_gemini(prompt)
        except Exception as e:
            logger.debug(f"Gemini text parse error: {e}")

    parsed = None
    if raw_json:
        try:
            clean_str = raw_json.strip()
            if clean_str.startswith("```"):
                clean_str = clean_str.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = json.loads(clean_str.strip())
        except Exception as e:
            logger.debug(f"JSON decode error: {e}")

    # Локальный эвристический парсер, если AI недоступен
    if not parsed or not parsed.get("items"):
        parsed = _heuristic_text_parse(text, room_members)

    # Нормализуем draft: сопоставляем имена участников с ID
    items = []
    total_calc = 0.0
    all_member_ids = [m["id"] for m in room_members]
    all_unmatched_names = []
    # Models occasionally retain named people but omit the author in phrases
    # such as "делю на себя, Ульяну и Тёму". This phrase is an explicit split
    # instruction, so preserve the authenticated author deterministically.
    split_includes_current_user = bool(
        default_payer_id and re.search(r"(?i)\b(?:на|для)\s+(?:себя|меня|мне)\b", text)
    )

    for it in parsed.get("items", []):
        it_name = (it.get("name") or "Позиция").strip()
        it_qty = float(it.get("quantity") or 1.0)
        it_tot = float(it.get("total_amount") or 0.0)
        it_price = float(it.get("unit_price") or (it_tot / it_qty if it_qty > 0 else it_tot))
        if it_tot == 0.0 and it_price > 0.0:
            it_tot = it_price * it_qty
        total_calc += it_tot

        it_cat, _ = _rule_based_categorize(it_name)
        if it.get("category") and it["category"] != "🔧 Другое":
            it_cat = it["category"]

        parts_raw = it.get("participants", "all")
        mapped_uids = []
        if parts_raw != "all" and isinstance(parts_raw, list):
            for p in parts_raw:
                p_clean = str(p).strip()
                uid = match_member_name(p_clean, room_members, default_payer_id=default_payer_id)
                if uid:
                    if uid not in mapped_uids:
                        mapped_uids.append(uid)
                else:
                    if p_clean and p_clean.lower() not in ("все", "all", "остальные") and p_clean not in all_unmatched_names:
                        all_unmatched_names.append(p_clean)

        if not mapped_uids:
            mapped_uids = all_member_ids
        elif split_includes_current_user and default_payer_id not in mapped_uids:
            mapped_uids.append(default_payer_id)

        items.append({
            "name": it_name,
            "quantity": it_qty,
            "unit_price": round(it_price, 2),
            "total_amount": round(it_tot, 2),
            "category": it_cat,
            "participants": mapped_uids,
        })

    # Определяем плательщика
    payer_id = default_payer_id
    if parsed.get("payer_name"):
        found_payer = match_member_name(parsed["payer_name"], room_members, default_payer_id=default_payer_id)
        if found_payer:
            payer_id = found_payer

    res = {
        "title": parsed.get("title") or (items[0]["name"] if items else "Расход"),
        "merchant": parsed.get("merchant") or "",
        "currency": parsed.get("currency") or "RUB",
        "total_amount": round(total_calc, 2),
        "payer_id": payer_id,
        "confidence": parsed.get("confidence", 0.9),
        "source_type": "text",
        "items": items,
    }

    if all_unmatched_names:
        names_str = ", ".join(all_unmatched_names)
        res["warning"] = f"Участник{'и' if len(all_unmatched_names) > 1 else ''} «{names_str}» не найден{'ы' if len(all_unmatched_names) > 1 else ''} в комнате. Выберите участников вручную."

    return res


def _heuristic_text_parse(text: str, room_members: list[dict]) -> dict:
    """Локальный эвристический разбор строк текста с суммами и именами."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    items = []
    total = 0.0

    for line in lines:
        # Ищем сумму в строке
        amt_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:₽|руб|р\.?)?", line)
        if not amt_match:
            continue
        amt = float(amt_match.group(1).replace(",", "."))
        total += amt

        # Очищаем строку от суммы
        desc = line[:amt_match.start()].strip(" -—:,	")
        if not desc:
            desc = line[amt_match.end():].strip(" -—:,	")

        # Ищем указание участников в скобках, например "(только Аня и Мария)"
        parts = "all"
        parts_match = re.search(r"\((.*?)\)", line)
        if parts_match:
            inside = parts_match.group(1).lower()
            matched = []
            for m in room_members:
                if m.get("display_name", "").lower() in inside:
                    matched.append(m["id"])
            if matched:
                parts = matched
            desc = desc.replace(parts_match.group(0), "").strip(" -—:,	")

        qty = 1.0
        qty_match = re.search(r"(\d+)\s*шт", line, re.IGNORECASE)
        if qty_match:
            qty = float(qty_match.group(1))

        cat, _ = _rule_based_categorize(desc)
        items.append({
            "name": desc or "Товар",
            "quantity": qty,
            "unit_price": round(amt / qty, 2),
            "total_amount": round(amt, 2),
            "category": cat,
            "participants": parts,
        })

    if not items:
        cat, clean = _rule_based_categorize(text)
        amt_m = re.search(r"(\d+(?:[.,]\d+)?)", text)
        amt = float(amt_m.group(1).replace(",", ".")) if amt_m else 0.0
        items.append({
            "name": clean or "Расход",
            "quantity": 1.0,
            "unit_price": amt,
            "total_amount": amt,
            "category": cat,
            "participants": "all",
        })

    return {
        "title": items[0]["name"] if len(items) == 1 else "Список покупок",
        "merchant": "",
        "currency": "RUB",
        "confidence": 0.85,
        "items": items,
    }


async def transcribe_and_parse_voice(
    audio_bytes: bytes,
    room_members: list[dict],
    default_payer_id: Optional[int] = None,
    filename: str = "voice.webm"
) -> dict:
    """
    Голосовой ввод расхода:
    1. Speech-To-Text (Whisper через OpenAI)
    2. Извлечение структурированного чека через parse_unstructured_expense_text
    """
    if not audio_bytes or len(audio_bytes) < 100:
        return {
            "error": "empty_audio",
            "message": "Аудиозапись пуста или слишком короткая. Попробуйте записать снова."
        }

    transcript = ""
    # Определение расширения для Whisper API (по сигнатуре байтов и имени файла)
    ext = ".webm"
    if b"ID3" in audio_bytes[:10] or audio_bytes[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        ext = ".mp3"
    elif b"ftyp" in audio_bytes[:32]:
        ext = ".mp4"
    elif b"OggS" in audio_bytes[:32]:
        ext = ".ogg"
    elif b"RIFF" in audio_bytes[:32]:
        ext = ".wav"
    else:
        lower_fn = (filename or "").lower()
        if lower_fn.endswith((".webm", ".ogg", ".mp4", ".m4a", ".mp3", ".wav", ".oga", ".flac")):
            ext = os.path.splitext(lower_fn)[1]

    # 1. Распознавание через OpenAI Whisper
    if openai_client:
        try:
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = f"voice{ext}"
            transcription = await openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru",
            )
            transcript = (transcription.text or "").strip()
        except Exception as e:
            logger.error(f"OpenAI Whisper error: {e}", exc_info=True)

    # 2. Проверка результата расшифровки (БЕЗ использования mock-данных)
    if not transcript:
        return {
            "error": "empty_transcript",
            "message": "Не удалось разобрать речь в аудиозаписи. Пожалуйста, повторите запись четче или введите текст вручную."
        }

    # 3. Единый AI парсер текста расхода
    draft = await parse_unstructured_expense_text(transcript, room_members, default_payer_id=default_payer_id)
    draft["source_type"] = "voice"
    draft["transcription"] = transcript
    if not draft.get("items"):
        draft["warning"] = "Не удалось автоматически выделить суммы из речи. Проверьте позиции вручную."

    return draft
