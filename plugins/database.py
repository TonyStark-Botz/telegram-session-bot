# ========== IMPORT SYSTEM ========== #
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from config import DATABASE_URI_SESSIONS_F, ADMINS

# ========== LOGGING SETUP ========== #
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== DATABASE CONNECTION ========== #
def get_db_connection():
    try:
        client = MongoClient(
            DATABASE_URI_SESSIONS_F,
            server_api=ServerApi('1'),
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        client.admin.command('ping')
        return client
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

# ========== DATABASE STATS ========== #
async def get_database_stats():
    try:
        client = get_db_connection()
        db = client['Cluster0']
        
        # Collection stats
        sessions_col = db['sessions']
        total_sessions = sessions_col.count_documents({})
        active_sessions = sessions_col.count_documents({"logged_in": True})
        promo_sessions = sessions_col.count_documents({"promotion": True})
        
        # Database stats
        db_stats = db.command("dbstats")
        
        stats_text = (
            f"📊 <b>Database Status</b> 📊\n\n"
            f"<b>Collections:</b>\n"
            f"• Total Sessions: {total_sessions}\n"
            f"• Active Sessions: {active_sessions}\n"
            f"• Promotion Enabled: {promo_sessions}\n\n"
            f"<b>Storage:</b>\n"
            f"• Data Size: {round(db_stats['dataSize'] / (1024 * 1024), 2)} MB\n"
            f"• Storage Size: {round(db_stats['storageSize'] / (1024 * 1024), 2)} MB\n"
            f"• Index Size: {round(db_stats['indexSize'] / (1024 * 1024), 2)} MB\n\n"
            f"<i>Last updated: Now</i>"
        )
        
        return stats_text, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔄 Refresh 🔄", callback_data="refresh_db_stats")]]
        )
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        error_text = "⚠️ Failed to fetch database stats. Please try again later."
        return error_text, None
    finally:
        if 'client' in locals():
            client.close()

# ========== COMMAND HANDLER ========== #
@Client.on_message(filters.private & filters.command("start"))
async def handle_database_command(client: Client, message: Message):
    try:
        stats_text, reply_markup = await get_database_stats()
        await message.reply_text(
            stats_text,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Command handler error: {e}")
        await message.reply_text("⚠️ An error occurred while processing your request.")

# ========== CALLBACK HANDLER ========== #
@Client.on_callback_query(filters.regex("^refresh_db_stats$"))
async def handle_refresh_callback(client: Client, callback_query):
    try:
        stats_text, reply_markup = await get_database_stats()
        await callback_query.message.edit_text(
            stats_text,
            reply_markup=reply_markup
        )
        await callback_query.answer("Database stats refreshed!")
    except Exception as e:
        logger.error(f"Callback handler error: {e}")
        await callback_query.answer("Failed to refresh stats", show_alert=True)
