import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import ADMINS, DATABASE_URI_SESSIONS_F
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

# Database connection
mongo_client = AsyncIOMotorClient(
    DATABASE_URI_SESSIONS_F,
    server_api=ServerApi('1'),
    maxPoolSize=100,
    minPoolSize=10
)
database = mongo_client['Cluster0']['sessions']

# ========== UTILITY FUNCTIONS ========== #
async def get_db_stats():
    """Get database statistics"""
    return {
        "total_users": await database.count_documents({}),
        "active_users": await database.count_documents({"logged_in": True}),
        "promo_users": await database.count_documents({"promotion": True})
    }

async def update_all_users(status_type: str, value: bool):
    """Update all users' status"""
    return await database.update_many(
        {},
        {"$set": {status_type: value}}
    )

# ========== COMMAND HANDLERS ========== #
@Client.on_message(filters.command("database") & filters.user(ADMINS))
async def db_command_handler(bot: Client, message: Message):
    """Handle /db command - show database status"""
    await show_db_status(bot, message)

async def show_db_status(bot: Client, message: Message, edit=False):
    """Show database status with buttons"""
    stats = await get_db_stats()
    
    text = (
        "📊 **Database Status** 📊\n\n"
        f"• Total Users: `{stats['total_users']}`\n"
        f"• Active Sessions: `{stats['active_users']}`\n"
        f"• Active Promotions: `{stats['promo_users']}`"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔧 DB Update 🔧", callback_data="db_update_menu"),
            InlineKeyboardButton("🔄 Refresh 🔄", callback_data="refresh_db_status")
        ]
    ])
    
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.reply(text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex("^refresh_db_status$"))
async def refresh_db_status(bot: Client, query: CallbackQuery):
    """Refresh database status"""
    await query.answer("Refreshing...")
    await show_db_status(bot, query.message, edit=True)

@Client.on_callback_query(filters.regex("^db_update_menu$"))
async def db_update_menu(bot: Client, query: CallbackQuery):
    """Show DB update menu"""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Enable Promotion", callback_data="enable_promo"),
            InlineKeyboardButton("❌ Disable Promotion", callback_data="disable_promo")
        ],
        [
            InlineKeyboardButton("✅ Enable Login", callback_data="enable_login"),
            InlineKeyboardButton("❌ Disable Login", callback_data="disable_login")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_to_status")
        ]
    ])
    
    await query.message.edit_text(
        "🔧 **Database Update Menu** 🔧\n\n"
        "Select what you want to update:",
        reply_markup=keyboard
    )
    await query.answer()

@Client.on_callback_query(filters.regex("^(enable|disable)_(promo|login)$"))
async def handle_update_action(bot: Client, query: CallbackQuery):
    """Handle enable/disable actions"""
    action, status_type = query.data.split("_")
    value = True if action == "enable" else False
    status_field = "promotion" if status_type == "promo" else "logged_in"
    
    # Confirm action
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{action}_{status_type}"),
            InlineKeyboardButton("❌ Cancel", callback_data="db_update_menu")
        ]
    ])
    
    await query.message.edit_text(
        f"⚠️ Are you sure you want to {action} {status_type.replace('promo', 'promotion').replace('login', 'login status')} for ALL users?",
        reply_markup=keyboard
    )
    await query.answer()

@Client.on_callback_query(filters.regex("^confirm_(enable|disable)_(promo|login)$"))
async def confirm_update_action(bot: Client, query: CallbackQuery):
    """Confirm and execute update action"""
    action, status_type = query.data.split("_")[1:]
    value = True if action == "enable" else False
    status_field = "promotion" if status_type == "promo" else "logged_in"
    
    processing_msg = await query.message.edit_text(
        f"🔄 {action.capitalize()}ing {status_type.replace('promo', 'promotion')} for all users..."
    )
    
    try:
        result = await update_all_users(status_field, value)
        await processing_msg.edit_text(
            f"✅ Successfully {action}d {status_type.replace('promo', 'promotion')} for {result.modified_count} users!"
        )
        # Show the status again after 3 seconds
        await asyncio.sleep(3)
        await show_db_status(bot, query.message, edit=True)
    except Exception as e:
        await processing_msg.edit_text(
            f"❌ Failed to update: {str(e)}"
        )

@Client.on_callback_query(filters.regex("^back_to_status$"))
async def back_to_status(bot: Client, query: CallbackQuery):
    """Return to status view"""
    await show_db_status(bot, query.message, edit=True)
    await query.answer()
