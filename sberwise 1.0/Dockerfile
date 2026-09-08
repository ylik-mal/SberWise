# ===================================================
# SberSplit Telegram Mini App & Bot — Production Dockerfile
# ===================================================
FROM python:3.11-slim

# Системные зависимости: curl для healthcheck, libzbar0 для декодирования QR-кодов чеков
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libzbar0 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода приложения
COPY . .

# Создание директории для персистентного тома базы данных SQLite
RUN mkdir -p /data

# Переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1 \
    PORT=8899 \
    DATABASE_PATH=/data/expenses.db

# Экспорт рабочего порта
EXPOSE 8899

# Проверка работоспособности контейнера
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT}/health || exit 1

# Запуск бота и веб-сервера
CMD ["python", "bot.py"]
