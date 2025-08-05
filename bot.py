import os
import logging
from pyrogram import Client
from config import API_ID, API_HASH

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load plugins
plugins = dict(root="plugins")

# Initialize Bot
app = Client(
    "SessionBot",
    api_id=API_ID,
    api_hash=API_HASH,
    plugins=plugins
)

if __name__ == "__main__":
    logger.info("Starting Telegram Session Bot...")
    app.run()
