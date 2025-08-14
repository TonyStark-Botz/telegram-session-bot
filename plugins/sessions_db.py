# plugins/sessions_db.py

import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# Import shared database & safe_db_operation from login.py
from plugins.login import database, safe_db_operation
from config import ADMINS

# ==================== LOGGING SYSTEM ==================== #
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ==================== KEYBOARDS ==================== #
def main_db_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔧 DB Update 🔧", callback_data="db_update")],
        [InlineKeyboardButton("🔄 Refresh 🔄", callback_data="db_refresh")]
    ])

def update_options_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Enable Promotion", callback_data="update_promo_true")],
        [InlineKeyboardButton("🚫 Disable Promotion", callback_data="update_promo_false")],
        [InlineKeyboardButton("✅ Enable Login", callback_data="update_login_true")],
        [InlineKeyboardButton("🚫 Disable Login", callback_data="update_login_false")],
        [InlineKeyboardButton("🔙 Back", callback_data="db_back")]
    ])

# ==================== COMMAND HANDLER ==================== #
@Client.on_message(filters.command("db") & filters.user(ADMINS))
async def show_database_status(bot: Client, message: Message):
    try:
        total_sessions = await safe_db_operation(database.count_documents, {})
        logged_in_count = await safe_db_operation(database.count_documents, {"logged_in": True})
        promo_enabled_count = await safe_db_operation(database.count_documents, {"promotion": True})

        text = (
            "📊 **Database Status** 📊\n\n"
            f"🔹 Total Sessions: `{total_sessions}`\n"
            f"🔹 Logged In: `{logged_in_count}`\n"
            f"🔹 Promotion Enabled: `{promo_enabled_count}`"
        )
        await message.reply(text, reply_markup=main_db_keyboard())
        log.info("📊 Database status displayed to admin.")
    except Exception as e:
        await message.reply("⚠️ Error while fetching database status.")
        log.error(f"❌ Error in /db command: {e}")

# ==================== CALLBACK QUERY HANDLER ==================== #
@Client.on_callback_query(filters.regex("^db_") & filters.user(ADMINS))
async def handle_db_buttons(bot: Client, query: CallbackQuery):
    try:
        action = query.data

        if action == "db_update":
            await query.message.edit_text("⚙ **DB Update Menu** ⚙", reply_markup=update_options_keyboard())
            log.info("🔧 Admin opened DB Update menu.")

        elif action == "db_refresh":
            total_sessions = await safe_db_operation(database.count_documents, {})
            logged_in_count = await safe_db_operation(database.count_documents, {"logged_in": True})
            promo_enabled_count = await safe_db_operation(database.count_documents, {"promotion": True})

            text = (
                "📊 **Database Status** 📊\n\n"
                f"🔹 Total Sessions: `{total_sessions}`\n"
                f"🔹 Logged In: `{logged_in_count}`\n"
                f"🔹 Promotion Enabled: `{promo_enabled_count}`"
            )
            await query.message.edit_text(text, reply_markup=main_db_keyboard())
            log.info("🔄 Database status refreshed.")

        elif action == "db_back":
            await query.message.edit_text("📊 **Database Status** 📊", reply_markup=main_db_keyboard())
            log.info("↩️ Admin returned to main DB menu.")

    except Exception as e:
        await query.answer("⚠️ Error processing request.", show_alert=True)
        log.error(f"❌ Error in handle_db_buttons: {e}")

# ==================== PROMOTION / LOGIN UPDATE HANDLER ==================== #
@Client.on_callback_query(filters.regex("^update_") & filters.user(ADMINS))
async def handle_update_buttons(bot: Client, query: CallbackQuery):
    try:
        _, field, value = query.data.split("_")
        value = True if value.lower() == "true" else False

        if field == "promo":
            await safe_db_operation(database.update_many, {}, {"$set": {"promotion": value}})
            await query.answer(f"Promotion set to {value}", show_alert=True)
            log.info(f"✅ Promotion status updated to {value} for all users.")

        elif field == "login":
            await safe_db_operation(database.update_many, {}, {"$set": {"logged_in": value}})
            await query.answer(f"Login set to {value}", show_alert=True)
            log.info(f"✅ Login status updated to {value} for all users.")

        await query.message.edit_text("⚙ **DB Update Menu** ⚙", reply_markup=update_options_keyboard())

    except Exception as e:
        await query.answer("⚠️ Error updating database.", show_alert=True)
        log.error(f"❌ Error in handle_update_buttons: {e}")
