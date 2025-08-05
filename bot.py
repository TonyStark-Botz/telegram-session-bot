import os
import logging
from pyrogram import Client, idle
from pyromod import listen  # type: ignore
from pyrogram.errors import ApiIdInvalid, ApiIdPublishedFlood, AccessTokenInvalid
from config import API_ID, API_HASH, BOT_TOKEN

# Configure logging with colors
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - \033[32m%(pathname)s:\033[0m \033[31m\033[1m%(message)s\033[0m"
)

# Cleanup previous sessions
if os.path.exists("sessions"):
    for file in os.listdir("sessions"):
        os.remove(f"sessions/{file}")
else:
    os.makedirs("sessions", exist_ok=True)

app = Client(
    "Session_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    plugins={'root': 'login'},  # Changed to match your plugin directory
    workers=4,  # Optimal worker count for Render
    sleep_threshold=60  # Helps prevent FloodWaits
)

if __name__ == "__main__":
    logging.info("🚀 Starting Telegram Session Bot")
    try:
        # Validate credentials before starting
        app.connect()
        if not app.storage.user_id:
            raise AccessTokenInvalid("Invalid BOT_TOKEN")
        
        app.disconnect()
        
        # Start the bot properly
        app.start()
        
        # Get bot info
        bot_me = app.get_me()
        logging.info(f"🤖 Bot @{bot_me.username} is now running!")
        logging.info("⚡️ Ready to handle user sessions")
        
        # Keep the bot running
        idle()
        
    except (ApiIdInvalid, ApiIdPublishedFlood):
        logging.error("❌ Invalid API_ID/API_HASH combination")
    except AccessTokenInvalid:
        logging.error("❌ Invalid BOT_TOKEN provided")
    except Exception as e:
        logging.error(f"⚠️ Unexpected error: {str(e)}")
    finally:
        if 'app' in locals():
            app.stop()
            logging.info("🛑 Bot stopped successfully")
