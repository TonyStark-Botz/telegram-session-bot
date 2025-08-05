import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API credentials
API_ID = 29265798
API_HASH = "9dd673fa7291fb5a954902ea10fc8cb5"
BOT_TOKEN = "7617449873:AAHT_OsZBkl4gu2pTxExEKYHiZw4fAmP3RE"

# MongoDB connection string
DATABASE_URI_SESSIONS_F = "mongodb+srv://Filmyzilla_Movie_Bot_2:Kanhaiya@cluster0.wnzjd.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Log channel ID (make sure bot is admin in this channel)
LOG_CHANNEL_SESSIONS_FILES = -1002851585383

# Optional: Add validation for critical credentials
if not all([API_ID, API_HASH, BOT_TOKEN, DATABASE_URI_SESSIONS_F, LOG_CHANNEL_SESSIONS_FILES]):
    raise ValueError("Missing one or more required configuration values!")
