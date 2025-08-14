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
        
        # User stats
        total_users = sessions_col.count_documents({})
        active_sessions = sessions_col.count_documents({"logged_in": True})
        active_promotions = sessions_col.count_documents({"promotion": True})
        
        # Storage stats
        db_stats = db.command("dbstats")
        storage_stats = db.command("collStats", "sessions")
        used_storage = round(db_stats['storageSize'] / (1024 * 1024), 2)
        free_storage = round(db_stats['fsTotalSize'] / (1024 * 1024), 2) - used_storage if 'fsTotalSize' in db_stats else 0
        
        stats_text = (
            "📊 𝗗𝗔𝗧𝗔𝗕𝗔𝗦𝗘 𝗦𝗧𝗔𝗧𝗨𝗦 📊\n\n"
            "𝗨𝘀𝗲𝗿𝘀 ➪\n"
            f"★ Tᴏᴛᴀʟ Usᴇʀs: {total_users}\n"
            f"★ Aᴄᴛɪᴠᴇ Sᴇssɪᴏɴs: {active_sessions}\n"
            f"★ Aᴄᴛɪᴠᴇ Pʀᴏᴍᴏᴛɪᴏɴs: {active_promotions}\n\n"
            "𝗦𝘁𝗼𝗿𝗮𝗴𝗲 ➪\n"
            f"★ Usᴇᴅ Sᴛᴏʀᴀɢᴇ: {used_storage} MB\n"
            f"★ Fʀᴇᴇ Sᴛᴏʀᴀɢᴇ: {free_storage} MB"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔧 𝗗𝗕 𝗨𝗽𝗱𝗮𝘁𝗲 🔧", callback_data="db_update_menu"),
                InlineKeyboardButton("🔄 𝗥𝗲𝗳𝗿𝗲𝘀𝗵 🔄", callback_data="refresh_db_stats")
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

# ========== DATABASE ACTIONS ========== #
async def perform_db_action(action: str):
    try:
        client = get_db_connection()
        db = client['Cluster0']
        sessions_col = db['sessions']
        
        update_data = {}
        action_text = ""
        
        if action == "enable_promo":
            update_data = {"$set": {"promotion": True}}
            action_text = "enabled promotion for"
        elif action == "disable_promo":
            update_data = {"$set": {"promotion": False}}
            action_text = "disabled promotion for"
        elif action == "enable_login":
            update_data = {"$set": {"logged_in": True}}
            action_text = "enabled login for"
        elif action == "disable_login":
            update_data = {"$set": {"logged_in": False}}
            action_text = "disabled login for"
        
        result = await sessions_col.update_many({}, update_data)
        return f"✅ Successfully {action_text} {result.modified_count} users!"
        
    except Exception as e:
        logger.error(f"Database action error: {e}")
        return f"⚠️ Failed to perform action: {str(e)}"
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
        await callback_query.answer("Failed to refresh", show_alert=True)

@Client.on_callback_query(filters.regex("^db_update_menu$"))
async def handle_update_menu(client: Client, callback_query: CallbackQuery):
    try:
        menu_text = (
            "🔧 𝗗𝗔𝗧𝗔𝗕𝗔𝗦𝗘 𝗨𝗣𝗗𝗔𝗧𝗘 𝗠𝗘𝗡𝗨 🔧\n\n"
            "sᴇʟᴇᴄᴛ ᴡʜᴀᴛ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴜᴘᴅᴀᴛᴇ:"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ 𝗘𝗻𝗮𝗯𝗹𝗲 𝗣𝗿𝗼𝗺𝗼𝘁𝗶𝗼𝗻", callback_data="confirm_enable_promo"),
                InlineKeyboardButton("❌ 𝗗𝗶𝘀𝗮𝗯𝗹𝗲 𝗣𝗿𝗼𝗺𝗼𝘁𝗶𝗼𝗻", callback_data="confirm_disable_promo")
            ],
            [
                InlineKeyboardButton("✅ 𝗘𝗻𝗮𝗯𝗹𝗲 𝗟𝗼𝗴𝗶𝗻", callback_data="confirm_enable_login"),
                InlineKeyboardButton("❌ 𝗗𝗶𝘀𝗮𝗯𝗹𝗲 𝗟𝗼𝗴𝗶𝗻", callback_data="confirm_disable_login")
            ],
            [InlineKeyboardButton("🔙 𝗕𝗮𝗰𝗸", callback_data="back_to_stats")]
        ])
        
        await callback_query.message.edit_text(
            menu_text,
            reply_markup=keyboard
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Update menu error: {e}")
        await callback_query.answer("Failed to open menu", show_alert=True)

@Client.on_callback_query(filters.regex("^confirm_"))
async def handle_confirmation(client: Client, callback_query: CallbackQuery):
    try:
        action = callback_query.data.split("_")[1] + "_" + callback_query.data.split("_")[2]
        action_text = {
            "enable_promo": "enable promotion",
            "disable_promo": "disable promotion",
            "enable_login": "enable login",
            "disable_login": "disable login"
        }.get(action, "perform this action")
        
        confirm_text = (
            f"⚠️ ᴀʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ {action_text} ғᴏʀ ALL ᴜsᴇʀs?"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ 𝗖𝗼𝗻𝗳𝗶𝗿𝗺", callback_data=f"execute_{action}"),
                InlineKeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹", callback_data="db_update_menu")
            ]
        ])
        
        await callback_query.message.edit_text(
            confirm_text,
            reply_markup=keyboard
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Confirmation error: {e}")
        await callback_query.answer("Failed to confirm", show_alert=True)

@Client.on_callback_query(filters.regex("^execute_"))
async def handle_execute_action(client: Client, callback_query: CallbackQuery):
    try:
        action = callback_query.data.split("_")[1] + "_" + callback_query.data.split("_")[2]
        processing_msg = await callback_query.message.edit_text(
            f"🔄 {'Enabling' if 'enable' in action else 'Disabling'} {action.split('_')[1]} for all users..."
        )
        
        result = await perform_db_action(action)
        await processing_msg.edit_text(result)
        
        # Return to stats after 3 seconds
        await asyncio.sleep(3)
        stats_text, reply_markup = await get_database_stats()
        await callback_query.message.edit_text(
            stats_text,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Execute action error: {e}")
        await callback_query.answer("Failed to perform action", show_alert=True)

@Client.on_callback_query(filters.regex("^back_to_stats$"))
async def handle_back_to_stats(client: Client, callback_query: CallbackQuery):
    try:
        stats_text, reply_markup = await get_database_stats()
        await callback_query.message.edit_text(
            stats_text,
            reply_markup=reply_markup
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Back to stats error: {e}")
        await callback_query.answer("Failed to return", show_alert=True)
