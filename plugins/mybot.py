# ========== IMPORT SYSTEM ========== #
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove
)
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from config import DATABASE_URI_SESSIONS_F, ADMINS
from tenacity import retry, stop_after_attempt, wait_exponential

# ========== LOGGING SETUP ========== #
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== DATABASE CONNECTION ========== #
def get_main_db():
    try:
        client = MongoClient(
            DATABASE_URI_SESSIONS_F,
            server_api=ServerApi('1'),
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        client.admin.command('ping')
        return client['mybot_db']['bots']
    except Exception as e:
        logger.error(f"Main database connection error: {e}")
        raise

# ========== UTILITY FUNCTIONS ========== #
async def validate_bot_token(token: str) -> str:
    """Validate bot token and return username if valid"""
    try:
        test_client = Client(":memory:", bot_token=token)
        await test_client.start()
        me = await test_client.get_me()
        await test_client.stop()
        return me.username
    except Exception as e:
        logger.error(f"Bot token validation failed: {e}")
        return None

async def validate_mongodb_url(url: str) -> bool:
    try:
        client = MongoClient(
            url,
            server_api=ServerApi('1'),
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        client.admin.command('ping')
        client.close()
        return True
    except Exception as e:
        logger.error(f"MongoDB URL validation failed: {e}")
        return False

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def safe_db_operation(operation, *args, **kwargs):
    try:
        return await operation(*args, **kwargs)
    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        raise

# ========== CANCEL KEYBOARD ========== #
CANCEL_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]
])

# ========== BOT MANAGEMENT HANDLERS ========== #
@Client.on_message(filters.command("addbot") & filters.user(ADMINS))
async def start_add_bot_workflow(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in user_states:
        await message.reply("You already have an operation in progress. Please complete or cancel it first.")
        return
    
    user_states[user_id] = {
        "workflow": "add_bot",
        "step": "awaiting_token"
    }
    
    await message.reply(
        "🚀 <b>Bot Addition Workflow</b>\n\n"
        "Please send your <b>Bot Token</b> now:\n\n"
        "<code>1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ</code>",
        reply_markup=CANCEL_KEYBOARD,
        parse_mode="HTML"
    )

@Client.on_message(filters.private & ~filters.command(["start", "addbot", "deletebot", "botsbroadcast"]))
async def handle_workflow_messages(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get("workflow") != "add_bot":
        return
    
    current_state = user_states[user_id]
    
    try:
        if current_state["step"] == "awaiting_token":
            # Validate bot token
            bot_token = message.text.strip()
            bot_username = await validate_bot_token(bot_token)
            
            if not bot_username:
                await message.reply(
                    "❌ Invalid bot token. Please send a valid token:",
                    reply_markup=CANCEL_KEYBOARD
                )
                return
            
            current_state["step"] = "awaiting_db_url"
            current_state["bot_token"] = bot_token
            current_state["bot_username"] = bot_username
            
            await message.reply(
                "✅ <b>Bot Token Verified!</b>\n\n"
                f"Bot Username: @{bot_username}\n\n"
                "Now please send your <b>MongoDB Database URL</b>:\n\n"
                "<code>mongodb+srv://username:password@cluster.example.mongodb.net/?retryWrites=true&w=majority</code>",
                reply_markup=CANCEL_KEYBOARD,
                parse_mode="HTML"
            )
        
        elif current_state["step"] == "awaiting_db_url":
            # Validate MongoDB URL
            db_url = message.text.strip()
            if not await validate_mongodb_url(db_url):
                await message.reply(
                    "❌ Invalid MongoDB URL. Please send a valid URL:",
                    reply_markup=CANCEL_KEYBOARD
                )
                return
            
            current_state["step"] = "awaiting_db_details"
            current_state["db_url"] = db_url
            
            await message.reply(
                "✅ <b>MongoDB URL Verified!</b>\n\n"
                "Now please send your <b>Database Name</b> and <b>Collection Name</b> in this format:\n\n"
                "<code>database_name collection_name</code>\n\n"
                "Example:\n"
                "<code>mybotdb users</code>",
                reply_markup=CANCEL_KEYBOARD,
                parse_mode="HTML"
            )
        
        elif current_state["step"] == "awaiting_db_details":
            # Validate database and collection names
            try:
                db_name, collection_name = message.text.strip().split()
            except ValueError:
                await message.reply(
                    "❌ Invalid format. Please send both names separated by space:",
                    reply_markup=CANCEL_KEYBOARD
                )
                return
            
            # Save all details to database
            bot_data = {
                "user_id": user_id,
                "bot_token": current_state["bot_token"],
                "username": current_state["bot_username"],
                "db_url": current_state["db_url"],
                "db_name": db_name,
                "collection_name": collection_name
            }
            
            db = get_main_db()
            await safe_db_operation(db.insert_one, bot_data)
            
            await message.reply(
                f"🎉 <b>Bot Added Successfully!</b>\n\n"
                f"• Bot: @{current_state['bot_username']}\n"
                f"• Database: {db_name}\n"
                f"• Collection: {collection_name}\n\n"
                "You can now manage this bot using /deletebot or /botsbroadcast",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML"
            )
            logger.info(f"New bot added by {user_id}: @{current_state['bot_username']}")
            
            # Clean up state
            del user_states[user_id]
    
    except Exception as e:
        logger.error(f"Add bot workflow error: {e}", exc_info=True)
        await message.reply(
            "⚠️ An error occurred. The workflow has been canceled.",
            reply_markup=ReplyKeyboardRemove()
        )
        if user_id in user_states:
            del user_states[user_id]

@Client.on_callback_query(filters.regex("^cancel_operation$"))
async def cancel_workflow(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    
    await callback_query.message.edit_text(
        "❌ Operation canceled.",
        reply_markup=ReplyKeyboardRemove()
    )
    await callback_query.answer()

# ========== USER STATE MANAGEMENT ========== #
user_states = {}

# ========== MAIN FUNCTION ========== #
if __name__ == "__main__":
    logger.info("Starting mybot module...")
    # This module is meant to be imported, not run directly
    pass
