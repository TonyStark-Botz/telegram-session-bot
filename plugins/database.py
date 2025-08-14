# ========== IMPORT SYSTEM ========== #
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
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

# ========== GET DATABASE STATS ========== #
async def get_database_stats():
    try:
        client = get_db_connection()
        db = client['Cluster0']
        sessions_col = db['sessions']

        total_users = sessions_col.count_documents({})
        active_logins = sessions_col.count_documents({"logged_in": True})
        active_promotions = sessions_col.count_documents({"promotion": True})

        db_stats = db.command("dbstats")
        used_storage = round(db_stats['dataSize'] / (1024 * 1024), 2)
        free_storage = round((512 - used_storage), 2)
        total_storage = 512

        stats_text = (
            "📊 𝗗𝗔𝗧𝗔𝗕𝗔𝗦𝗘 𝗦𝗧𝗔𝗧𝗨𝗦 📊\n\n"
            "𝗨𝘀𝗲𝗿𝘀  ➪\n"
            f"★ Tᴏᴛᴀʟ Usᴇʀs: {total_users}\n"
            f"★ Aᴄᴛɪᴠᴇ Lᴏɢɪɴs: {active_logins}\n"
            f"★ Aᴄᴛɪᴠᴇ Pʀᴏᴍᴏᴛɪᴏɴs: {active_promotions}\n\n"
            "𝗦𝘁𝗼𝗿𝗮𝗴𝗲  ➪\n"
            f"★ Usᴇᴅ Sᴛᴏʀᴀ𝗴𝗲: {used_storage} MB\n"
            f"★ Fʀᴇᴇ Sᴛ𝗼𝗿𝗮𝗴𝗲: {free_storage} MB\n"
            f"★ Tᴏᴛᴀʟ Sᴛ𝗼𝗿𝗮𝗴𝗲: {total_storage} MB"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔧 𝗗𝗕 𝗨𝗽𝗱𝗮𝘁𝗲 🔧", callback_data="db_update_menu")],
            [InlineKeyboardButton("🔄 𝗥𝗲𝗳𝗿𝗲𝘀𝗵 🔄", callback_data="refresh_db_stats")]
        ])

        return stats_text, keyboard

    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return "⚠️ Failed to fetch database stats.", None
    finally:
        if 'client' in locals():
            client.close()

# ========== MAIN COMMAND HANDLER ========== #
@Client.on_message(filters.command("database") & filters.user(ADMINS))
async def handle_database_command(client: Client, message: Message):
    stats_text, reply_markup = await get_database_stats()
    await message.reply_text(stats_text, reply_markup=reply_markup)

# ========== REFRESH HANDLER ========== #
@Client.on_callback_query(filters.regex("^refresh_db_stats$"))
async def handle_refresh_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer("Refreshing...")
    stats_text, reply_markup = await get_database_stats()
    await callback_query.message.edit_text(stats_text, reply_markup=reply_markup)

# ========== DB UPDATE MENU HANDLER ========== #
@Client.on_callback_query(filters.regex("^db_update_menu$"))
async def handle_db_update_menu(client: Client, callback_query: CallbackQuery):
    menu_text = "🔧 𝗗𝗔𝗧𝗔𝗕𝗔𝗦𝗘 𝗨𝗣𝗗𝗔𝗧𝗘 𝗠𝗘𝗡𝗨 🔧"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 𝗘𝗻𝗮𝗯𝗹𝗲 𝗣𝗿𝗼𝗺𝗼𝘁𝗶𝗼𝗻", callback_data="confirm_enable_promo")],
        [InlineKeyboardButton("❌ 𝗗𝗶𝘀𝗮𝗯𝗹𝗲 𝗣𝗿𝗼𝗺𝗼𝘁𝗶𝗼𝗻", callback_data="confirm_disable_promo")],
        [InlineKeyboardButton("✅ 𝗘𝗻𝗮𝗯𝗹𝗲 𝗟𝗼𝗴𝗶𝗻", callback_data="confirm_enable_login")],
        [InlineKeyboardButton("❌ 𝗗𝗶𝘀𝗮𝗯𝗹𝗲 𝗟𝗼𝗴𝗶𝗻", callback_data="confirm_disable_login")],
        [InlineKeyboardButton("🔙 𝗕𝗮𝗰𝗸", callback_data="back_to_status")]
    ])
    await callback_query.message.edit_text(menu_text, reply_markup=keyboard)

# ========== CONFIRMATION HANDLER ========== #
@Client.on_callback_query(filters.regex("^confirm_(enable|disable)_(promo|login)$"))
async def handle_confirm_menu(client: Client, callback_query: CallbackQuery):
    action, target = callback_query.data.replace("confirm_", "").split("_", 1)
    action_text = "enable" if action == "enable" else "disable"
    target_text = "promotion" if target == "promo" else "login"

    confirm_text = f"⚠️ ᴀʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ {action_text.upper()} {target_text.upper()} ғᴏʀ ALL ᴜsᴇʀs?"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 𝗖𝗼𝗻𝗳𝗶𝗿𝗺", callback_data=f"do_{action}_{target}")],
        [InlineKeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹", callback_data="db_update_menu")]
    ])
    await callback_query.message.edit_text(confirm_text, reply_markup=keyboard)

# ========== ACTION EXECUTION HANDLER ========== #
@Client.on_callback_query(filters.regex("^do_(enable|disable)_(promo|login)$"))
async def handle_db_action(client: Client, callback_query: CallbackQuery):
    action, target = callback_query.data.replace("do_", "").split("_", 1)
    field = "promotion" if target == "promo" else "logged_in"
    value = True if action == "enable" else False

    await callback_query.message.edit_text(f"🔄 {action.upper()}ING {field.upper()} ғᴏʀ ᴀʟʟ ᴜsᴇʀs...")

    try:
        client_db = get_db_connection()
        db = client_db['Cluster0']
        result = db['sessions'].update_many({}, {"$set": {field: value}})
        await callback_query.message.edit_text(f"✅ sᴜᴄᴄᴇssғᴜʟʟʏ {action.upper()}ᴅ {field.upper()} ғᴏʀ {result.modified_count} ᴜsᴇʀs!")
        await asyncio.sleep(3)
    except Exception as e:
        logger.error(f"Error updating {field}: {e}")
        await callback_query.message.edit_text("⚠️ Failed to update database.")
    finally:
        if 'client_db' in locals():
            client_db.close()

    # Return to main status screen
    stats_text, reply_markup = await get_database_stats()
    await callback_query.message.edit_text(stats_text, reply_markup=reply_markup)

# ========== BACK BUTTON HANDLER ========== #
@Client.on_callback_query(filters.regex("^back_to_status$"))
async def handle_back_to_status(client: Client, callback_query: CallbackQuery):
    stats_text, reply_markup = await get_database_stats()
    await callback_query.message.edit_text(stats_text, reply_markup=reply_markup)
