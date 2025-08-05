import logging
import asyncio
from pyrogram import Client
from info import API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_SESSIONS_FILES

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

async def main():
    # Create the Client
    app = Client(
        "session-bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=plugins
    )

    # Start the client
    await app.start()
    
    # Send startup message
    await send_startup_message(app)
    
    logger.info("Bot successfully started!")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
