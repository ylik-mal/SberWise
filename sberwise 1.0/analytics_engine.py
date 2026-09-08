"""
analytics_engine.py — Модуль реальной аналитики расходов комнат СберСплит.

Реализует:
1. Фильтрацию расходов строго по group_id и временному диапазону.
2. Поддержку периодов:
   - current_month (Текущий календарный месяц, агрегация по календарным неделям)
   - prev_month (Прошлый календарный месяц)
   - 7_days (Последние 7 дней, посуточная динамика)
   - 30_days (Последние 30 дней, недельные интервалы)
   - all_time (За всё время, адаптивная агрегация: дни / недели / месяцы)
   - custom (Произвольный диапазон дат YYYY-MM-DD)
3. Расчёт метрик:
   - Общая сумма (total)
   - Количество покупок (count)
   - Средний чек (average = total / count, без деления на 0)
   - Распределение по категориям с процентами
   - Динамический таймлайн для графиков (Chart.js)
"""

import sqlite3
import calendar
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

RU_MONTHS_SHORT = [
    "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек"
]

RU_MONTHS_FULL = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

RU_MONTHS_GENITIVE = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]


def format_short_date(d: date) -> str:
    """Форматирует дату в виде: 4 сен."""
    return f"{d.day} {RU_MONTHS_SHORT[d.month - 1]}"


def format_full_date(d: date) -> str:
    """Форматирует дату в виде: 4 сентября 2026."""
    return f"{d.day} {RU_MONTHS_GENITIVE[d.month - 1]} {d.year}"


def get_month_calendar_weeks(year: int, month: int) -> List[Dict[str, Any]]:
    """
    Разбивает месяц на реальные календарные недели (пн-вс).
    Пример для сентября 2026:
    1–6 сен, 7–13 сен, 14–20 сен, 21–27 сен, 28–30 сен.
    """
    num_days = calendar.monthrange(year, month)[1]
    weeks = []
    curr_start = 1

    for day in range(1, num_days + 1):
        weekday = calendar.weekday(year, month, day)  # 0=Monday, 6=Sunday
        if weekday == 6 or day == num_days:
            start_date = date(year, month, curr_start)
            end_date = date(year, month, day)
            m_short = RU_MONTHS_SHORT[month - 1]
            m_full = RU_MONTHS_GENITIVE[month - 1]

            if curr_start == day:
                lbl = f"{curr_start} {m_short}"
                full_lbl = f"{curr_start} {m_full} {year}"
            else:
                lbl = f"{curr_start}–{day} {m_short}"
                full_lbl = f"{curr_start}–{day} {m_full} {year}"

            weeks.append({
                "label": lbl,
                "full_label": full_lbl,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "amount": 0.0
            })
            curr_start = day + 1

    return weeks


def get_daily_buckets(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """Создает посуточные корзины для таймлайна (например, для 7 дней)."""
    buckets = []
    curr = start_date
    while curr <= end_date:
        buckets.append({
            "label": format_short_date(curr),
            "full_label": format_full_date(curr),
            "start_date": curr.strftime("%Y-%m-%d"),
            "end_date": curr.strftime("%Y-%m-%d"),
            "amount": 0.0
        })
        curr += timedelta(days=1)
    return buckets


def get_interval_buckets(start_date: date, end_date: date, interval_days: int = 7) -> List[Dict[str, Any]]:
    """Создает корзины фиксированного интервала (например, по 7 дней)."""
    buckets = []
    curr = start_date
    while curr <= end_date:
        chunk_end = min(curr + timedelta(days=interval_days - 1), end_date)
        if curr == chunk_end:
            lbl = format_short_date(curr)
            full_lbl = format_full_date(curr)
        else:
            if curr.month == chunk_end.month:
                lbl = f"{curr.day}–{chunk_end.day} {RU_MONTHS_SHORT[curr.month - 1]}"
                full_lbl = f"{curr.day}–{chunk_end.day} {RU_MONTHS_GENITIVE[curr.month - 1]} {curr.year}"
            else:
                lbl = f"{curr.day} {RU_MONTHS_SHORT[curr.month - 1]}–{chunk_end.day} {RU_MONTHS_SHORT[chunk_end.month - 1]}"
                full_lbl = f"{curr.day} {RU_MONTHS_GENITIVE[curr.month - 1]} – {chunk_end.day} {RU_MONTHS_GENITIVE[chunk_end.month - 1]} {chunk_end.year}"

        buckets.append({
            "label": lbl,
            "full_label": full_lbl,
            "start_date": curr.strftime("%Y-%m-%d"),
            "end_date": chunk_end.strftime("%Y-%m-%d"),
            "amount": 0.0
        })
        curr = chunk_end + timedelta(days=1)
    return buckets


def get_monthly_buckets(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """Создает помесячные корзины для длинных интервалов (> 6 месяцев)."""
    buckets = []
    y = start_date.year
    m = start_date.month

    while (y < end_date.year) or (y == end_date.year and m <= end_date.month):
        month_start = date(y, m, 1)
        last_day = calendar.monthrange(y, m)[1]
        month_end = date(y, m, last_day)

        eff_start = max(start_date, month_start)
        eff_end = min(end_date, month_end)

        lbl = f"{RU_MONTHS_SHORT[m - 1]} {str(y)[2:]}"
        full_lbl = f"{RU_MONTHS_FULL[m - 1]} {y}"

        buckets.append({
            "label": lbl,
            "full_label": full_lbl,
            "start_date": eff_start.strftime("%Y-%m-%d"),
            "end_date": eff_end.strftime("%Y-%m-%d"),
            "amount": 0.0
        })

        if m == 12:
            y += 1
            m = 1
        else:
            m += 1

    return buckets


def calculate_room_analytics(
    conn: sqlite3.Connection,
    group_id: int,
    period_type: str = "current_month",
    date_from_str: Optional[str] = None,
    date_to_str: Optional[str] = None,
    current_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Основная функция расчёта аналитики для указанной группы и периода.
    Гарантирует:
    - Изоляцию по group_id
    - Отсутствие демо-данных
    - Корректный расчет среднего чека (без division by zero)
    - Реальные категории с процентами
    - Динамический таймлайн с нулевыми корзинами при отсутствии трат
    """
    today = current_date or date.today()

    # Получаем валюту группы
    group_row = conn.execute("SELECT currency, name FROM groups WHERE id = ?", (group_id,)).fetchone()
    currency = group_row["currency"] if group_row and "currency" in group_row.keys() and group_row["currency"] else "RUB"
    group_name = group_row["name"] if group_row and group_row["name"] else "Комната"

    # 1. Определение границ периода и корзин таймлайна
    period_label = "Текущий месяц"
    button_label = "Сентябрь"
    timeline_title = "Динамика по неделям"
    timeline_subtitle = "Распределение расходов"

    period_type = (period_type or "current_month").lower().strip()

    if period_type == "current_month":
        year = today.year
        month = today.month
        num_days = calendar.monthrange(year, month)[1]
        start_d = date(year, month, 1)
        end_d = date(year, month, num_days)

        period_label = f"{RU_MONTHS_FULL[month - 1]} {year}"
        button_label = RU_MONTHS_FULL[month - 1]
        timeline_title = "Динамика по неделям"
        timeline_subtitle = f"Календарные недели месяца ({period_label})"
        buckets = get_month_calendar_weeks(year, month)

    elif period_type == "prev_month":
        if today.month == 1:
            prev_year = today.year - 1
            prev_month = 12
        else:
            prev_year = today.year
            prev_month = today.month - 1

        num_days = calendar.monthrange(prev_year, prev_month)[1]
        start_d = date(prev_year, prev_month, 1)
        end_d = date(prev_year, prev_month, num_days)

        period_label = f"{RU_MONTHS_FULL[prev_month - 1]} {prev_year}"
        button_label = RU_MONTHS_FULL[prev_month - 1]
        timeline_title = "Динамика по неделям"
        timeline_subtitle = f"Календарные недели месяца ({period_label})"
        buckets = get_month_calendar_weeks(prev_year, prev_month)

    elif period_type == "7_days":
        start_d = today - timedelta(days=6)
        end_d = today
        period_label = f"{format_short_date(start_d)} — {format_short_date(end_d)} {today.year}"
        button_label = "7 дней"
        timeline_title = "Динамика по дням"
        timeline_subtitle = "Посуточное распределение за 7 дней"
        buckets = get_daily_buckets(start_d, end_d)

    elif period_type == "30_days":
        start_d = today - timedelta(days=29)
        end_d = today
        period_label = f"{format_short_date(start_d)} — {format_short_date(end_d)} {today.year}"
        button_label = "30 дней"
        timeline_title = "Динамика по неделям"
        timeline_subtitle = "Распределение за последние 30 дней"
        buckets = get_interval_buckets(start_d, end_d, interval_days=7)

    elif period_type == "all_time":
        # Находим минимальную дату расходов в комнате
        min_date_row = conn.execute("""
            SELECT MIN(substr(COALESCE(NULLIF(expense_date, ''), created_at), 1, 10))
            FROM expenses
            WHERE group_id = ?
        """, (group_id,)).fetchone()

        earliest_str = min_date_row[0] if min_date_row and min_date_row[0] else None
        if earliest_str:
            try:
                start_d = datetime.strptime(earliest_str[:10], "%Y-%m-%d").date()
            except Exception:
                start_d = today - timedelta(days=30)
        else:
            start_d = today - timedelta(days=30)

        end_d = today
        if start_d > end_d:
            start_d = end_d

        period_label = "За всё время"
        button_label = "Всё время"
        timeline_title = "Динамика расходов"
        timeline_subtitle = f"Вся история расходов ({format_short_date(start_d)} — {format_short_date(end_d)})"

        span_days = (end_d - start_d).days + 1
        if span_days <= 10:
            buckets = get_daily_buckets(start_d, end_d)
        elif span_days <= 180:
            buckets = get_interval_buckets(start_d, end_d, interval_days=7)
        else:
            buckets = get_monthly_buckets(start_d, end_d)

    elif period_type == "custom":
        try:
            start_d = datetime.strptime(date_from_str[:10], "%Y-%m-%d").date() if date_from_str else today - timedelta(days=7)
        except Exception:
            start_d = today - timedelta(days=7)

        try:
            end_d = datetime.strptime(date_to_str[:10], "%Y-%m-%d").date() if date_to_str else today
        except Exception:
            end_d = today

        if start_d > end_d:
            start_d, end_d = end_d, start_d

        period_label = f"{start_d.strftime('%d.%m.%Y')} — {end_d.strftime('%d.%m.%Y')}"
        button_label = f"{format_short_date(start_d)} — {format_short_date(end_d)}"
        timeline_title = "Динамика расходов"
        timeline_subtitle = f"Диапазон: {period_label}"

        span_days = (end_d - start_d).days + 1
        if span_days <= 14:
            buckets = get_daily_buckets(start_d, end_d)
        elif span_days <= 180:
            buckets = get_interval_buckets(start_d, end_d, interval_days=7)
        else:
            buckets = get_monthly_buckets(start_d, end_d)

    else:
        # Fallback to current month
        year = today.year
        month = today.month
        num_days = calendar.monthrange(year, month)[1]
        start_d = date(year, month, 1)
        end_d = date(year, month, num_days)
        period_label = f"{RU_MONTHS_FULL[month - 1]} {year}"
        button_label = RU_MONTHS_FULL[month - 1]
        buckets = get_month_calendar_weeks(year, month)

    start_date_str = start_d.strftime("%Y-%m-%d")
    end_date_str = end_d.strftime("%Y-%m-%d")

    # 2. Извлечение реальных расходов комнаты за период
    query = """
        SELECT
            id,
            amount,
            COALESCE(NULLIF(category, ''), 'Другое') AS category,
            substr(COALESCE(NULLIF(expense_date, ''), created_at), 1, 10) AS exp_date
        FROM expenses
        WHERE group_id = ?
          AND substr(COALESCE(NULLIF(expense_date, ''), created_at), 1, 10) BETWEEN ? AND ?
        ORDER BY exp_date ASC
    """
    rows = conn.execute(query, (group_id, start_date_str, end_date_str)).fetchall()

    expenses = [dict(r) for r in rows]
    total_amount = 0.0
    category_map: Dict[str, float] = {}

    # 3. Агрегация по корзинам таймлайна и категориям
    for exp in expenses:
        amt = float(exp["amount"] or 0.0)
        total_amount += amt
        cat = exp["category"]
        category_map[cat] = category_map.get(cat, 0.0) + amt

        exp_d = exp["exp_date"]
        # Сопоставляем расход с соответствующей корзиной
        for b in buckets:
            if b["start_date"] <= exp_d <= b["end_date"]:
                b["amount"] += amt
                break

    total_amount = round(total_amount, 2)
    tx_count = len(expenses)
    average_check = round(total_amount / tx_count, 2) if tx_count > 0 else 0.0

    # Округляем суммы в корзинах
    for b in buckets:
        b["amount"] = round(b["amount"], 2)

    # 4. Формирование списка категорий с процентами (сортировка по убыванию суммы)
    categories_list = []
    for cat_name, cat_amt in sorted(category_map.items(), key=lambda x: x[1], reverse=True):
        cat_amt_round = round(cat_amt, 2)
        pct = round((cat_amt / total_amount) * 100, 1) if total_amount > 0 else 0.0
        categories_list.append({
            "category": cat_name,
            "amount": cat_amt_round,
            "percent": pct
        })

    return {
        "group_id": group_id,
        "group_name": group_name,
        "currency": currency,
        "period": {
            "type": period_type,
            "label": period_label,
            "button_label": button_label,
            "from": start_date_str,
            "to": end_date_str
        },
        "total": total_amount,
        "average": average_check,
        "count": tx_count,
        "timeline_meta": {
            "title": timeline_title,
            "subtitle": timeline_subtitle
        },
        "timeline": buckets,
        "categories": categories_list
    }
