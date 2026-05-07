FROM python:3.11-slim

# Рабочая директория
WORKDIR /app

# Системные зависимости для psycopg2 и парсинга PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY . .

# Создаём директории для данных и логов
RUN mkdir -p data logs uploads

# Не запускаем от root
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "main.py"]
