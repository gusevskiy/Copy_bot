# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install -r requirements.txt

# Копируем код бота в контейнер
COPY . .

# Указываем команду запуска
CMD ["python", "bot/main.py"]
