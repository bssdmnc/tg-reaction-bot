import asyncio
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import sqlite3
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Загрузка переменных окружения
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

def post_link(message_id):
    cid = str(CHANNEL_ID).lstrip('-').removeprefix('100')
    return f"https://t.me/c/{cid}/{message_id}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    with sqlite3.connect('reactions.db') as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                message_id INTEGER,
                user_id INTEGER,
                username TEXT,
                emoji TEXT,
                PRIMARY KEY (message_id, user_id)
            )
        ''')
    logging.info("База данных готова.")

EMOJIS = ["⚡", "❤️", "👌", "🥲", "💩", "🐳"]

def get_counts(message_id):
    with sqlite3.connect('reactions.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT emoji, COUNT(*) FROM reactions WHERE message_id = ? GROUP BY emoji',
            (message_id,)
        )
        counts = dict(cursor.fetchall())
    # Получаем id последнего поста с реакциями
    with sqlite3.connect('reactions.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(message_id) FROM reactions')
        last_id = cursor.fetchone()[0]
    # Визуально подменяем количество сердечек для последнего поста
    if last_id and message_id == last_id:
        counts['❤️'] = 88
        counts['⚡'] = 881
    return counts

def get_keyboard(message_id, counts=None):
    builder = InlineKeyboardBuilder()
    for emoji in EMOJIS:
        count = counts.get(emoji, 0) if counts else 0
        text = f"{emoji} {count}" if count > 0 else emoji
        
        builder.button(text=text, callback_data=f"react:{emoji}:{message_id}")
    # Растягиваем кнопки на весь ряд
    builder.adjust(len(EMOJIS))
    return builder.as_markup()

# --- СЛУШАЕМ НОВЫЕ ПОСТЫ В КАНАЛЕ ---
@dp.channel_post()
async def on_channel_post(message: types.Message):
    if message.chat.id == CHANNEL_ID:
        try:
            await bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=get_keyboard(message.message_id)
            )
            logging.info(f"Добавлены кнопки к посту №{message.message_id}")
        except Exception as e:
            logging.error(f"Не удалось добавить кнопки: {e}")

# --- СТАТИСТИКА ДЛЯ АДМИНА ---
@dp.message(F.text == "/stats")
async def cmd_stats(message: types.Message):
    with sqlite3.connect('reactions.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT message_id FROM reactions ORDER BY message_id DESC LIMIT 20')
        message_ids = [row[0] for row in cursor.fetchall()]

    if not message_ids:
        await message.answer("Реакций пока нет.")
        return

    lines = []
    for msg_id in message_ids:
        lines.append(f'📌 <b><a href="{post_link(msg_id)}">Пост #{msg_id}</a></b>')
        with sqlite3.connect('reactions.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT emoji, username, user_id FROM reactions WHERE message_id = ? ORDER BY emoji',
                (msg_id,)
            )
            rows = cursor.fetchall()
        by_emoji = {}
        for emoji, username, user_id in rows:
            link = f'<a href="tg://user?id={user_id}">{username}</a>'
            by_emoji.setdefault(emoji, []).append(link)
        for emoji, users in by_emoji.items():
            lines.append(f"  {emoji} — {', '.join(users)}")
        lines.append("")

    await message.answer("\n".join(lines), parse_mode="HTML")

# --- ОБРАБОТКА НАЖАТИЙ ---
@dp.callback_query(F.data.startswith("react:"))
async def handle_reaction(callback: types.CallbackQuery):
    try:
        _, emoji, msg_id = callback.data.split(":")
        user_id = callback.from_user.id
        username = callback.from_user.username
        display_name = f"@{username}" if username else callback.from_user.full_name or "Без имени"

        # Проверяем, есть ли уже такая реакция у пользователя
        with sqlite3.connect('reactions.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT emoji FROM reactions WHERE message_id = ? AND user_id = ?', (msg_id, user_id))
            row = cursor.fetchone()
            if row and row[0] == emoji:
                await callback.answer("Ты уже выбрал эту реакцию", show_alert=True)
                return
            # Обновляем реакцию
            cursor.execute('''
                INSERT OR REPLACE INTO reactions (message_id, user_id, username, emoji)
                VALUES (?, ?, ?, ?)
            ''', (msg_id, user_id, display_name, emoji))
            conn.commit()

        logging.info(f"Юзер {display_name} выбрал {emoji} на посте {msg_id}")
        await callback.answer(f"Спасибо за реакцию {emoji}!", show_alert=True)

        counts = get_counts(int(msg_id))
        await bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=int(msg_id),
            reply_markup=get_keyboard(int(msg_id), counts)
        )

    except Exception as e:
        logging.error(f"Ошибка при обработке клика: {e}")
        await callback.answer("Что-то пошло не так...")


# --- WEBHOOK MAIN ---
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Укажите полный URL для webhook

async def on_startup(dispatcher):
    init_db()
    await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
    logging.info("Webhook установлен.")

async def on_shutdown(dispatcher):
    await bot.delete_webhook()
    logging.info("Webhook удалён.")

def setup_webhook_app():
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    app.on_startup.append(lambda app: on_startup(dp))
    app.on_shutdown.append(lambda app: on_shutdown(dp))
    return app

# Делаем app доступным для WSGI
app = setup_webhook_app()

if __name__ == '__main__':
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
