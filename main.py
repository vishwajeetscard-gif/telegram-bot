import asyncio
import os
import sqlite3
from contextlib import closing

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatMemberStatus
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_1 = os.getenv("CHANNEL_1", "@channel1")
CHANNEL_2 = os.getenv("CHANNEL_2", "@channel2")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
SUCCESS_MESSAGE = os.getenv("SUCCESS_MESSAGE", "✅ Access granted!")

DB_PATH = "users.db"

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                joined_ok INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def add_or_update_user(user_id, ok=False):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        exists = c.fetchone()
        if exists:
            c.execute("UPDATE users SET joined_ok=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                      (1 if ok else 0, user_id))
        else:
            c.execute("INSERT INTO users (user_id, joined_ok) VALUES (?,?)", (user_id, 1 if ok else 0))
        conn.commit()

def all_users():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        return [row[0] for row in c.fetchall()]

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

def join_keyboard():
    kb = [
        [InlineKeyboardButton(text="Join Channel 1", url=f"https://t.me/{CHANNEL_1.lstrip('@')}")],
        [InlineKeyboardButton(text="Join Channel 2", url=f"https://t.me/{CHANNEL_2.lstrip('@')}")],
        [InlineKeyboardButton(text="✅ Check", callback_data="check")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def is_member(bot, user_id, chat_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        }
    except:
        return False

async def joined_both(bot, user_id):
    return (await is_member(bot, user_id, CHANNEL_1)) and (await is_member(bot, user_id, CHANNEL_2))

@dp.message(Command("start"))
async def start(message: Message):
    add_or_update_user(message.from_user.id, ok=False)
    text = (
        "Welcome!\n"
        "Join both channels:\n"
        f"{CHANNEL_1}\n"
        f"{CHANNEL_2}\n"
        "Tap ✅ Check after joining."
    )
    await message.answer(text, reply_markup=join_keyboard())

@dp.callback_query(F.data == "check")
async def check_member(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await joined_both(bot, user_id):
        add_or_update_user(user_id, ok=True)
        await callback.message.edit_text(SUCCESS_MESSAGE)
    else:
        await callback.answer("You haven't joined both channels.", show_alert=True)

@dp.message(Command("broadcast"))
async def broadcast(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Not allowed.")
        return

    text = (command.args or "").strip()
    if not text:
        await message.answer("Usage: /broadcast Your message")
        return

    users = all_users()
    sent, failed = 0, 0

    for uid in users:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except:
            failed += 1

    await message.answer(f"✅ Sent: {sent} | ❌ Failed: {failed}")

async def main():
    init_db()
    print("Bot running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
