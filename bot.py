import os
import logging
from pyrogram import Client, idle, filters
from pyromod import listen  # type: ignore
from pyrogram.errors import ApiIdInvalid, ApiIdPublishedFlood, AccessTokenInvalid
from config import API_ID, API_HASH, BOT_TOKEN
from fastapi import FastAPI
from threading import Thread
import uvicorn

# Configure logging with colors
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - \033[32m%(pathname)s:\033[0m \033[31m\033[1m%(message)s\033[0m"
)

# Import handlers directly from login.py
from login import (
    start_login,
    handle_logout,
    handle_contact,
    handle_otp_buttons,
    handle_2fa_password,
    register_handlers
)

# Cleanup previous sessions
if os.path.exists("sessions"):
    for file in os.listdir("sessions"):
        os.remove(f"sessions/{file}")
else:
    os.makedirs("sessions", exist_ok=True)

# FastAPI app for health checks
web_app = FastAPI()

@web_app.get("/health")
def health_check():
    return {"status": "active", "bot": "running"}

def run_web_server():
    uvicorn.run(web_app, host="0.0.0.0", port=8080)

app = Client(
    "Session_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    workers=4,
    sleep_threshold=60
)

# Register handlers directly instead of using plugins
register_handlers(app)

if __name__ == "__main__":
    # Start web server in a separate thread
    web_thread = Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()

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
