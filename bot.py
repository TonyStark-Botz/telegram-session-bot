import os
import shutil
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN

# Clear previous sessions
if os.path.exists("sessions"):
    shutil.rmtree("sessions")
os.makedirs("sessions", exist_ok=True)

bot = Client(
    "session_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins={"root": "login"},
    in_memory=True,
    workers=2  # Reduce worker count
)

if __name__ == "__main__":
    print("Starting bot with memory optimization...")
    bot.run()
