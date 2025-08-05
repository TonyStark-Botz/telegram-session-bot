import logging
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_SESSIONS_FILES

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

plugins = dict(
    root="plugins"
)

async def send_startup_message(client: Client):
    try:
        await client.send_message(
            LOG_CHANNEL_SESSIONS_FILES,
            "**Bᴏᴛ Rᴇsᴛᴀʀᴛᴇᴅ !** ✅\n\n"
            "🔹 All systems operational\n"
            "🔹 Ready to handle requests"
        )
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")

def main():
    # Create the Client
    app = Client(
        "session-bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=plugins
    )

    # Add startup handler
    app.on_startup(send_startup_message)

    # Run the bot
    logger.info("Starting Telegram Session Bot...")
    app.run()

if __name__ == "__main__":
    main()
