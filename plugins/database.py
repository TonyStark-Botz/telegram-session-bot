# ========== IMPORT SYSTEM ========== #
import logging
import time
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
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
        sessions_col = db['sessions']
        
        # Collection stats
        total_users = sessions_col.count_documents({})
        active_sessions = sessions_col.count_documents({"logged_in": True})
        active_promotions = sessions_col.count_documents({"promotion": True})
        
        stats_text = (
            f"📊 <b>Database Status</b> 📊\n\n"
            f"• Total Users: <code>{total_users}</code>\n"
            f"• Active Sessions: <code>{active_sessions}</code>\n"
            f"• Active Promotions: <code>{active_promotions}</code>\n\n"
            f"<i>Last updated: {time.strftime('%H:%M:%S')}</i>"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔧 DB Update 🔧", callback_data="db_update_menu"),
                InlineKeyboardButton("🔄 Refresh 🔄", callback_data="refresh_db_stats")
            ]
        ])
        
        return stats_text, keyboard
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        error_text = "⚠️ Failed to fetch database stats. Please try again later."
        return error_text, None
    finally:
        if 'client' in locals():
            client.close()

# ========== DATABASE UPDATE FUNCTIONS ========== #
async def update_all_users(field: str, value: bool):
    try:
        client = get_db_connection()
        db = client['Cluster0']
        sessions_col = db['sessions']
        
        result = sessions_col.update_many(
            {},
            {"$set": {field: value}}
        )
        
        return result.modified_count
        
    except Exception as e:
        logger.error(f"Error updating users: {e}")
        raise
    finally:
        if 'client' in locals():
            client.close()

# ========== COMMAND HANDLER ========== #
@Client.on_message(filters.command("database") & filters.user(ADMINS))
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

# ========== CALLBACK HANDLERS ========== #
@Client.on_callback_query(filters.regex("^refresh_db_stats$"))
async def handle_refresh_callback(client: Client, callback_query: CallbackQuery):
    try:
        await callback_query.answer("Refreshing...")
        stats_text, reply_markup = await get_database_stats()
        await callback_query.message.edit_text(
            stats_text,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Refresh callback error: {e}")
        await callback_query.answer("Failed to refresh stats", show_alert=True)

@Client.on_callback_query(filters.regex("^db_update_menu$"))
async def handle_update_menu(client: Client, callback_query: CallbackQuery):
    try:
        menu_text = "🔧 <b>Database Update Menu</b> 🔧\n\nSelect what you want to update:"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Enable Promotion", callback_data="confirm_enable_promo"),
                InlineKeyboardButton("❌ Disable Promotion", callback_data="confirm_disable_promo")
            ],
            [
                InlineKeyboardButton("✅ Enable Login", callback_data="confirm_enable_login"),
                InlineKeyboardButton("❌ Disable Login", callback_data="confirm_disable_login")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_status")
            ]
        ])
        
        await callback_query.message.edit_text(
            menu_text,
            reply_markup=keyboard
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Update menu error: {e}")
        await callback_query.answer("Failed to open menu", show_alert=True)

@Client.on_callback_query(filters.regex("^confirm_(enable|disable)_(promo|login)$"))
async def handle_confirmation(client: Client, callback_query: CallbackQuery):
    try:
        action = callback_query.data.split('_')[1]
        field = "promotion" if "promo" in callback_query.data else "logged_in"
        value = True if action == "enable" else False
        
        action_text = f"{action} {field.replace('_', ' ')}"
        
        confirm_text = (
            f"⚠️ <b>Are you sure you want to {action_text} for ALL users?</b>"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Confirm", callback_data=f"execute_{field}_{value}"),
                InlineKeyboardButton("❌ Cancel", callback_data="db_update_menu")
            ]
        ])
        
        await callback_query.message.edit_text(
            confirm_text,
            reply_markup=keyboard
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Confirmation error: {e}")
        await callback_query.answer("Failed to process confirmation", show_alert=True)

@Client.on_callback_query(filters.regex("^execute_(promotion|logged_in)_(true|false)$"))
async def handle_execute_update(client: Client, callback_query: CallbackQuery):
    try:
        field = callback_query.data.split('_')[1]
        value = True if callback_query.data.split('_')[2] == "true" else False
        
        processing_msg = await callback_query.message.edit_text(
            f"🔄 {'Enabling' if value else 'Disabling'} {field.replace('_', ' ')} for all users..."
        )
        
        updated_count = await update_all_users(field, value)
        
        await processing_msg.edit_text(
            f"✅ Successfully {'enabled' if value else 'disabled'} {field.replace('_', ' ')} "
            f"for <code>{updated_count}</code> users!"
        )
        
        # Return to status screen after 3 seconds
        await asyncio.sleep(3)
        stats_text, reply_markup = await get_database_stats()
        await callback_query.message.edit_text(
            stats_text,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Execute update error: {e}")
        await callback_query.message.edit_text(
            "⚠️ Failed to update database. Please try again later."
        )

@Client.on_callback_query(filters.regex("^back_to_status$"))
async def handle_back_to_status(client: Client, callback_query: CallbackQuery):
    try:
        stats_text, reply_markup = await get_database_stats()
        await callback_query.message.edit_text(
            stats_text,
            reply_markup=reply_markup
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Back to status error: {e}")
        await callback_query.answer("Failed to return to status", show_alert=True)
