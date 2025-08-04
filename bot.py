from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN
from login import register_handlers

bot = Client(
    "session_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins={"root": "login"}
)

if __name__ == "__main__":
    register_handlers(bot)
    print("Bot started!")
    bot.run()
