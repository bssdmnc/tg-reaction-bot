# tg-reaction-bot

Telegram-бот для сбора реакций через инлайн-клавиатуру и анализа статистики.

## Запуск локально

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Создайте файл `.env` с переменными:
   - `API_TOKEN` — токен Telegram-бота
   - `CHANNEL_ID` — ID канала
   - `WEBHOOK_URL` — ваш публичный URL (например, https://yourusername.pythonanywhere.com)
   - `PORT` — порт (по умолчанию 8080)

3. Запустите бота:
   ```bash
   python bot.py
   ```

## Деплой на PythonAnywhere

1. Загрузите проект на GitHub и клонируйте его на PythonAnywhere.
2. Установите зависимости:
   ```bash
   pip3.10 install --user -r requirements.txt
   ```
3. Настройте WSGI (укажите путь к `bot.py`).
4. В `.env` пропишите все переменные.
5. Укажите webhook-URL в настройках Telegram-бота.

## Важно
- Для webhook-режима нужен публичный HTTPS-адрес.
- Для теста локально используйте ngrok или аналог.
