import logging
import asyncio
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_SESSIONS_FILES
from aiohttp import web

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

plugins = dict(
    root="plugins"
)

async def health_check(request):
    return web.Response(text="OK", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Health check server running on port 8080")

async def send_startup_message(client: Client):
    try:
        await client.send_message(
            LOG_CHANNEL_SESSIONS_FILES,
            "**Bᴏᴛ Rᴇsᴛᴀʀᴛᴇᴅ !** ✅\n\n"
            "🔹 All systems operational\n"
            "🔹 Ready to handle requests\n"
            f"🔹 Health check: http://0.0.0.0:8080/health"
        )
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")

async def main():
    # Start health check server
    await start_web_server()

    # Create and start Pyrogram Client
    app = Client(
        "session-bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=plugins
    )

    await app.start()
    await send_startup_message(app)
    
    logger.info("""
    ====================================
    ✅ Bot FULLY STARTED AND READY TO USE!
    ====================================
    """)

    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
