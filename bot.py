import logging
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

plugins = dict(
    root="plugins"
)

def main():
    # Create the Client
    app = Client(
        "session-bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=plugins
    )

    # Run the bot
    logger.info("Starting Telegram Session Bot...")
    app.run()

if __name__ == "__main__":
    main()
