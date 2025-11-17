FROM python:3.12-slim

# Рабочая директория внутри контейнера
WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Переменные окружения по умолчанию (можно переопределить из compose)
ENV DB_USER=alabuga_app
ENV DB_PASSWORD=alabuga_password
ENV DB_NAME=alabuga_chat
ENV DB_HOST=db
ENV DB_PORT=5432

# Команда запуска — uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8015"]
