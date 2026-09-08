"""
Модуль визуализации — графики matplotlib для отправки в Telegram.
"""

import io
import matplotlib
matplotlib.use("Agg")  # Без GUI
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


# Цвета в стиле Сбера
COLORS = [
    "#21A038",  # Зелёный (Сбер)
    "#FFA500",  # Оранжевый
    "#1E88E5",  # Синий
    "#E53935",  # Красный
    "#8E24AA",  # Фиолетовый
    "#43A047",  # Зелёный 2
    "#FFB300",  # Жёлтый
    "#00ACC1",  # Бирюзовый
    "#7CB342",  # Лайм
    "#6D4C41",  # Коричневый
]


def create_pie_chart(category_totals: dict[str, float], title: str = "Расходы по категориям") -> io.BytesIO:
    """
    Создать круговую диаграмму расходов по категориям.
    Возвращает BytesIO с PNG-изображением.
    """
    if not category_totals:
        return _create_empty_chart("Нет данных о расходах")

    labels = list(category_totals.keys())
    values = list(category_totals.values())
    total = sum(values)

    fig, ax = plt.subplots(1, 1, figsize=(8, 6), facecolor="#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct=lambda pct: f"{pct:.1f}%\n({pct * total / 100:,.0f}₽)",
        colors=COLORS[: len(labels)],
        startangle=90,
        pctdistance=0.75,
        wedgeprops={"edgecolor": "#1a1a2e", "linewidth": 2},
    )

    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontsize(9)
        autotext.set_fontweight("bold")

    # Легенда
    legend_labels = [f"{label}  —  {value:,.0f}₽" for label, value in zip(labels, values)]
    legend = ax.legend(
        wedges,
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1, 0.5),
        fontsize=10,
        frameon=False,
    )
    for text in legend.get_texts():
        text.set_color("white")

    ax.set_title(title, color="white", fontsize=14, fontweight="bold", pad=20)

    plt.figtext(
        0.5, 0.02,
        f"Всего: {total:,.0f}₽",
        ha="center",
        color="#21A038",
        fontsize=13,
        fontweight="bold",
    )

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    buf.seek(0)
    plt.close(fig)
    return buf


def create_balance_chart(balances: dict[str, float], title: str = "Балансы участников") -> io.BytesIO:
    """
    Создать горизонтальную bar chart с балансами.
    Зелёный = ему должны, красный = он должен.
    """
    if not balances:
        return _create_empty_chart("Нет данных о балансах")

    names = list(balances.keys())
    values = list(balances.values())

    fig, ax = plt.subplots(figsize=(8, max(3, len(names) * 0.8)), facecolor="#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    bar_colors = ["#21A038" if v >= 0 else "#E53935" for v in values]

    bars = ax.barh(names, values, color=bar_colors, edgecolor="#1a1a2e", height=0.6)

    # Определяем пределы графика
    max_val = max(abs(v) for v in values) if values else 0
    margin = max(100.0, max_val * 0.25)
    ax.set_xlim(-max_val - margin, max_val + margin)

    for bar, value in zip(bars, values):
        label = f"+{value:,.0f}₽" if value > 0 else (f"{value:,.0f}₽" if value < 0 else "0₽")
        offset = margin * 0.1
        x_pos = bar.get_width() + (offset if value >= 0 else -offset)
        ax.text(
            x_pos, bar.get_y() + bar.get_height() / 2,
            label,
            va="center",
            ha="left" if value >= 0 else "right",
            color="white",
            fontsize=11,
            fontweight="bold",
        )

    ax.axvline(x=0, color="white", linewidth=0.5, alpha=0.5)
    ax.set_title(title, color="white", fontsize=14, fontweight="bold", pad=15)
    ax.tick_params(colors="white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("white")
    ax.spines["left"].set_color("white")

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    buf.seek(0)
    plt.close(fig)
    return buf


def _create_empty_chart(message: str) -> io.BytesIO:
    """Заглушка если данных нет."""
    fig, ax = plt.subplots(figsize=(6, 3), facecolor="#1a1a2e")
    ax.set_facecolor("#1a1a2e")
    ax.text(0.5, 0.5, message, ha="center", va="center", color="white", fontsize=14)
    ax.axis("off")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    buf.seek(0)
    plt.close(fig)
    return buf
