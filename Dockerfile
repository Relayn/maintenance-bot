# Этап 1: Установка зависимостей
FROM python:3.13-slim AS builder

# Устанавливаем Poetry
RUN pip install poetry

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы для установки зависимостей
COPY poetry.lock pyproject.toml ./

# Настраиваем Poetry, чтобы он создавал .venv в папке проекта
RUN poetry config virtualenvs.in-project true

# Устанавливаем зависимости, не включая dev-зависимости
RUN poetry install --no-root --without dev

# Этап 2: Сборка финального образа
FROM python:3.13-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем виртуальное окружение с зависимостями из первого этапа
COPY --from=builder /app/.venv ./.venv

# Копируем исходный код приложения
COPY app/ ./app

# Копируем файл с учетными данными Google
COPY credentials.json .

# Указываем Python, чтобы он использовал наше виртуальное окружение
ENV PATH="/app/.venv/bin:$PATH"

# Команда для запуска приложения как модуля
CMD ["python", "-m", "app.main"]
