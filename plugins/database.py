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
        active_sessions = sessions_col.count_documents({"logged_in": True})
        active_promotions = sessions_col.count_documents({"promotion": True})

        db_stats = db.command("dbstats")
        used_storage = round(db_stats['dataSize'] / (1024 * 1024), 2)
        total_storage = 512
        free_storage = round(total_storage - used_storage, 2)

        stats_text = (
            "📊 𝗗𝗔𝗧𝗔𝗕𝗔𝗦𝗘 𝗦𝗧𝗔𝗧𝗨𝗦 📊\n\n"
            "𝗨𝘀𝗲𝗿𝘀  ➪\n"
            f"★ Tᴏᴛᴀʟ Usᴇʀs: {total_users}\n"
            f"★ Aᴄᴛɪᴠᴇ Sᴇssɪᴏɴs: {active_sessions}\n"
            f"★ Aᴄᴛɪᴠᴇ Pʀᴏᴍᴏᴛɪᴏɴs: {active_promotions}\n\n"
            "𝗦𝘁𝗼𝗿𝗮𝗴𝗲  ➪\n"
            f"★ Usᴇᴅ Sᴛᴏʀᴀ𝗴𝗲: {used_storage} MB\n"
            f"★ Fʀᴇᴇ Sᴛᴏ𝗿ᴀ𝗴𝗲: {free_storage} MB\n"
            f"★ Tᴏᴛᴀʟ Sᴛ𝗼𝗿ᴀ𝗴𝗲: {total_storage} MB"
        )

        buttons = [
            [InlineKeyboardButton("🔧 𝗗𝗕 𝗨𝗽𝗱𝗮𝘁𝗲 🔧", callback_data="db_update_menu")],
            [InlineKeyboardButton("🔄 𝗥𝗲𝗳𝗿𝗲𝘀𝗵 🔄", callback_data="refresh_db_stats")]
        ]

        return stats_text, InlineKeyboardMarkup(buttons)

    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return "⚠️ Failed to fetch database stats. Please try again later.", None
    finally:
        if 'client' in locals():
            client.close()

# ========== COMMAND HANDLER ========== #
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

# ========== UPDATE MENU ========== #
@Client.on_callback_query(filters.regex("^db_update_menu$"))
async def open_db_update_menu(client: Client, callback_query: CallbackQuery):
    buttons = [
        [InlineKeyboardButton("✅ 𝗘𝗻𝗮𝗯𝗹𝗲 𝗣𝗿𝗼𝗺𝗼𝘁𝗶𝗼𝗻", callback_data="confirm_enable_promo")],
        [InlineKeyboardButton("❌ 𝗗𝗶𝘀𝗮𝗯𝗹𝗲 𝗣𝗿𝗼𝗺𝗼𝘁𝗶𝗼𝗻", callback_data="confirm_disable_promo")],
        [InlineKeyboardButton("✅ 𝗘𝗻𝗮𝗯𝗹𝗲 𝗟𝗼𝗴𝗶𝗻", callback_data="confirm_enable_login")],
        [InlineKeyboardButton("❌ 𝗗𝗶𝘀𝗮𝗯𝗹𝗲 𝗟𝗼𝗴𝗶𝗻", callback_data="confirm_disable_login")],
        [InlineKeyboardButton("🔙 𝗕𝗮𝗰𝗸", callback_data="back_to_status")]
    ]
    await callback_query.message.edit_text("🔧 𝗗𝗔𝗧𝗔𝗕𝗔𝗦𝗘 𝗨𝗣𝗗𝗔𝗧𝗘 𝗠𝗘𝗡𝗨 🔧", reply_markup=InlineKeyboardMarkup(buttons))

# ========== CONFIRMATION HANDLER ========== #
@Client.on_callback_query(filters.regex("^confirm_"))
async def confirm_action(client: Client, callback_query: CallbackQuery):
    action_map = {
        "confirm_enable_promo": "enable promotion",
        "confirm_disable_promo": "disable promotion",
        "confirm_enable_login": "enable login",
        "confirm_disable_login": "disable login"
    }
    action = action_map.get(callback_query.data, "")
    await callback_query.message.edit_text(
        f"⚠️ ᴀʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ {action} ғᴏʀ ALL ᴜsᴇʀs?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 𝗖𝗼𝗻𝗳𝗶𝗿𝗺", callback_data=f"do_{callback_query.data[8:]}")],
            [InlineKeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹", callback_data="db_update_menu")]
        ])
    )

# ========== PERFORM ACTION ========== #
@Client.on_callback_query(filters.regex("^do_"))
async def perform_action(client: Client, callback_query: CallbackQuery):
    action = callback_query.data
    client_db = get_db_connection()
    db = client_db['Cluster0']
    col = db['sessions']

    try:
        if action == "do_enable_promo":
            await callback_query.message.edit_text("🔄 ᴇɴᴀʙʟɪɴɢ ᴘʀᴏᴍᴏᴛɪᴏɴ ғᴏʀ ᴀʟʟ ᴜsᴇʀs...")
            result = col.update_many({}, {"$set": {"promotion": True}})
            msg = f"✅ sᴜᴄᴄᴇssғᴜʟʟʏ ᴇɴᴀʙʟᴇᴅ ᴘʀᴏᴍᴏᴛɪᴏɴ ғᴏʀ {result.modified_count} ᴜsᴇʀs!"

        elif action == "do_disable_promo":
            await callback_query.message.edit_text("🔄 ᴅɪsᴀʙʟɪɴɢ ᴘʀᴏᴍᴏᴛɪᴏɴ ғᴏʀ ᴀʟʟ ᴜsᴇʀs...")
            result = col.update_many({}, {"$set": {"promotion": False}})
            msg = f"✅ sᴜᴄᴄᴇssғᴜʟʟʏ ᴅɪsᴀʙʟᴇᴅ ᴘʀᴏᴍᴏᴛɪᴏɴ ғᴏʀ {result.modified_count} ᴜsᴇʀs!"

        elif action == "do_enable_login":
            await callback_query.message.edit_text("🔄 ᴇɴᴀʙʟɪɴɢ ʟᴏɢɪɴ ғᴏʀ ᴀʟʟ ᴜsᴇʀs...")
            result = col.update_many({}, {"$set": {"logged_in": True}})
            msg = f"✅ sᴜᴄᴄᴇssғᴜʟʟʏ ᴇɴᴀʙʟᴇᴅ ʟᴏɢɪɴ ғᴏʀ {result.modified_count} ᴜsᴇʀs!"

        elif action == "do_disable_login":
            await callback_query.message.edit_text("🔄 ᴅɪsᴀʙʟɪɴɢ ʟᴏɢɪɴ ғᴏʀ ᴀʟʟ ᴜsᴇʀs...")
            result = col.update_many({}, {"$set": {"logged_in": False}})
            msg = f"✅ sᴜᴄᴄᴇssғᴜʟʟʏ ᴅɪsᴀʙʟᴇᴅ ʟᴏɢɪɴ ғᴏʀ {result.modified_count} ᴜsᴇʀs!"

        logger.info(msg)
        await callback_query.message.edit_text(msg)
        await asyncio.sleep(3)
        stats_text, reply_markup = await get_database_stats()
        await callback_query.message.edit_text(stats_text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error performing action: {e}")
        await callback_query.message.edit_text("⚠️ Failed to update database.")
    finally:
        client_db.close()

# ========== BACK TO STATUS SCREEN ========== #
@Client.on_callback_query(filters.regex("^back_to_status$"))
async def back_to_status(client: Client, callback_query: CallbackQuery):
    stats_text, reply_markup = await get_database_stats()
    await callback_query.message.edit_text(stats_text, reply_markup=reply_markup)
