import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URI_SESSIONS_F = os.getenv("DATABASE_URI_SESSIONS_F", "")
LOG_CHANNEL_SESSIONS_FILES = int(os.getenv("LOG_CHANNEL_SESSIONS_FILES", 0))
