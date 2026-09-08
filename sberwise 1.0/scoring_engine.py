"""
Модуль «Альтернативный Скоринг (Telegram-аналитика) — Сбер».
Реализует скоринговую модель оценки финансовой дисциплины и кредитоспособности
физических лиц на основе их микрофинансового поведения в коллективных группах.

Шкала скоринга: 300 - 850 баллов (международный банковский стандарт FICO / Сбер).
"""

from datetime import datetime
import math


def calculate_comprehensive_score(
    user_id: int,
    user_display_name: str,
    expenses_paid_count: int,
    expenses_paid_total: float,
    user_share_total: float,
    current_balance: float,
    settlements_sent_count: int,
    settlements_sent_total: float,
    settlements_received_count: int,
    verified_receipts_count: int,
    avg_days_to_settle: float = 1.5,
) -> dict:
    """
    Рассчитывает детальный альтернативный кредитный профиль участника.
    
    Компоненты скоринга:
    1. Платёжная дисциплина (Payment Discipline, 35%)
    2. Скорость взаиморасчётов (Settlement Velocity, 25%)
    3. Вклад в общие расходы (Contribution Ratio, 25%)
    4. Прозрачность операций (Fiscal Transparency, 15%)
    """
    # 1. Платёжная дисциплина (0.0 - 1.0)
    # Если баланс положительный (ему должны) — дисциплина идеальная (1.0).
    # Если баланс отрицательный, но он регулярно гасит долги — высокая.
    if current_balance >= 0:
        discipline_factor = 1.0
    else:
        # Долг есть. Смотрим отношение долга к сумме, которую он уже тратил за всех
        debt_amount = abs(current_balance)
        if expenses_paid_total + settlements_sent_total > 0:
            coverage = (expenses_paid_total + settlements_sent_total) / (debt_amount + expenses_paid_total + settlements_sent_total)
            discipline_factor = max(0.2, min(0.9, coverage))
        else:
            discipline_factor = 0.4

    # Бонус за историю погашений
    if settlements_sent_count > 0:
        discipline_factor = min(1.0, discipline_factor + 0.1)

    # 2. Скорость взаиморасчётов (0.0 - 1.0)
    # Погашение быстрее 2 дней = 1.0, 7 дней = 0.5, >14 дней = 0.1
    if avg_days_to_settle <= 2.0:
        velocity_factor = 1.0
    elif avg_days_to_settle <= 7.0:
        velocity_factor = 1.0 - ((avg_days_to_settle - 2.0) / 10.0)
    else:
        velocity_factor = max(0.15, 0.5 - ((avg_days_to_settle - 7.0) / 14.0))

    # 3. Вклад в общие расходы (0.0 - 1.0)
    # Сколько платит за других участников
    if user_share_total > 0:
        contribution_ratio = expenses_paid_total / user_share_total
        contribution_factor = min(1.0, max(0.2, contribution_ratio * 0.7 + 0.3))
    else:
        contribution_factor = 0.5 if expenses_paid_count == 0 else 0.9

    # 4. Прозрачность операций (0.0 - 1.0)
    # Доля трат с прикрепленными банковскими PDF или QR-чеками
    if expenses_paid_count > 0:
        transparency_factor = min(1.0, 0.4 + (verified_receipts_count / expenses_paid_count) * 0.6)
    else:
        transparency_factor = 0.6

    # Итоговый взвешенный индекс (0.0 - 1.0)
    composite_index = (
        discipline_factor * 0.35 +
        velocity_factor * 0.25 +
        contribution_factor * 0.25 +
        transparency_factor * 0.15
    )
    composite_index = max(0.05, min(1.0, composite_index))

    # Перевод в банковскую шкалу 300 - 850
    score_points = int(300 + (composite_index * 550))

    # Категория кредитоспособности для Сбера
    if score_points >= 780:
        rating_grade = "AAA"
        badge = "💎 Платиновый плательщик"
        verdict = "Превосходная финансовая надёжность. Рекомендована выдача кредитной карты и премиальных продуктов без справок о доходах."
        color = "#10B981"  # Emerald Green
    elif score_points >= 700:
        rating_grade = "AA"
        badge = "🥇 Золотой партнёр"
        verdict = "Высокая платёжная дисциплина. Минимальный риск задержки расчётов."
        color = "#22C55E"  # Green
    elif score_points >= 620:
        rating_grade = "A"
        badge = "🥈 Надёжный плательщик"
        verdict = "Хороший уровень ответственности. Расчёты производятся стабильно."
        color = "#F59E0B"  # Amber
    elif score_points >= 500:
        rating_grade = "B"
        badge = "🥉 Умеренный риск"
        verdict = "Периодические задержки взаиморасчётов. Требуются мягкие напоминания."
        color = "#F97316"  # Orange
    else:
        rating_grade = "C"
        badge = "⚠️ Требует контроля"
        verdict = "Высокая долговая нагрузка в группе. Рекомендуется ограничить новые общие траты."
        color = "#EF4444"  # Red

    return {
        "user_id": user_id,
        "name": user_display_name,
        "score": score_points,
        "max_score": 850,
        "percentage": int(composite_index * 100),
        "grade": rating_grade,
        "badge": badge,
        "verdict": verdict,
        "color": color,
        "factors": {
            "discipline": {
                "name": "Платёжная дисциплина",
                "value": int(discipline_factor * 100),
                "weight": "35%",
                "status": "Отлично" if discipline_factor >= 0.8 else ("Хорошо" if discipline_factor >= 0.5 else "Внимание")
            },
            "velocity": {
                "name": "Скорость расчётов",
                "value": int(velocity_factor * 100),
                "weight": "25%",
                "status": f"~{avg_days_to_settle:.1f} дн."
            },
            "contribution": {
                "name": "Вклад в общий бюджет",
                "value": int(contribution_factor * 100),
                "weight": "25%",
                "status": f"{expenses_paid_total:,.0f}₽ оплачено"
            },
            "transparency": {
                "name": "Фискальная прозрачность",
                "value": int(transparency_factor * 100),
                "weight": "15%",
                "status": f"{verified_receipts_count} чеков"
            }
        },
        "stats": {
            "paid_total": expenses_paid_total,
            "share_total": user_share_total,
            "balance": current_balance,
            "expenses_count": expenses_paid_count,
            "settlements_count": settlements_sent_count,
        }
    }


def calculate_budget_forecast(
    total_spent_month: float,
    days_elapsed: int,
    days_in_month: int,
    target_budget: float = 60000.0,
) -> dict:
    """
    Предиктивная аналитика бюджета группы (AI-фича из кейса):
    «предсказывает, когда общий бюджет подойдёт к критической точке».
    Лимит фиксированный и настраиваемый (не раздувается автоматически).
    """
    days_elapsed = max(1, days_elapsed)
    daily_burn_rate = total_spent_month / days_elapsed

    target_budget = float(target_budget) if target_budget and target_budget > 0 else 60000.0
    projected_month_end = daily_burn_rate * days_in_month
    is_already_exceeded = total_spent_month >= target_budget
    remaining_budget = max(0.0, target_budget - total_spent_month)
    over_amount = max(0.0, total_spent_month - target_budget)

    percent_used = (total_spent_month / target_budget) * 100.0 if target_budget > 0 else 0.0

    if daily_burn_rate > 0 and not is_already_exceeded:
        days_until_exhausted = remaining_budget / daily_burn_rate
    else:
        days_until_exhausted = 0.0

    critical_day = min(days_in_month, days_elapsed + int(days_until_exhausted))
    is_overbudget = is_already_exceeded or (projected_month_end > target_budget)

    if is_already_exceeded:
        burn_speed_status = "🔴 Превышен"
        forecast_message = (
            f"🚨 Лимит {target_budget:,.0f}₽ превышен на {over_amount:,.0f}₽! "
            f"Израсходовано {round(percent_used, 1)}% бюджета. Рекомендуется оптимизировать траты."
        )
    elif percent_used > 85:
        burn_speed_status = "🔴 Критическая"
        forecast_message = (
            f"⚠️ Использовано {round(percent_used, 1)}% бюджета! При темпе {daily_burn_rate:,.0f}₽/день "
            f"лимит исчерпается через {int(days_until_exhausted)} дн. (к {critical_day}-му числу)."
        )
    elif is_overbudget:
        burn_speed_status = "🟠 Повышенная"
        forecast_message = (
            f"⚠️ При среднем расходе {daily_burn_rate:,.0f}₽/день лимит {target_budget:,.0f}₽ "
            f"исчерпается через {int(days_until_exhausted)} дн. (ориентировочно к {critical_day}-му числу)."
        )
    else:
        burn_speed_status = "🟢 В пределах нормы"
        forecast_message = (
            f"✅ Бюджет под контролем: текущий темп {daily_burn_rate:,.0f}₽/день позволит остаться в рамках лимита {target_budget:,.0f}₽."
        )

    return {
        "total_spent": total_spent_month,
        "target_budget": target_budget,
        "remaining_budget": remaining_budget,
        "over_amount": over_amount,
        "percent_used": round(percent_used, 1),
        "daily_burn_rate": round(daily_burn_rate, 1),
        "projected_month_end": round(projected_month_end, 0),
        "days_until_critical": max(0, int(days_until_exhausted)),
        "critical_day_of_month": critical_day,
        "status": burn_speed_status,
        "is_overbudget": is_overbudget,
        "is_already_exceeded": is_already_exceeded,
        "forecast_message": forecast_message,
    }
