# ========== IMPORT SYSTEM ========== #
import logging
import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    CallbackQuery
)
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import PyMongoError, ConnectionFailure, OperationFailure
from motor.motor_asyncio import AsyncIOMotorClient
from config import DATABASE_URI_SESSIONS_F, ADMINS

# ========== LOGGING SETUP ========== #
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== DATABASE CONNECTION ========== #
MANAGEMENT_DB_NAME = "bot_management"
USER_BOTS_COLLECTION = "user_bots"

def get_management_db():
    try:
        client = MongoClient(
            DATABASE_URI_SESSIONS_F,
            server_api=ServerApi('1'),
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        db = client[MANAGEMENT_DB_NAME]
        db[USER_BOTS_COLLECTION].create_index([("user_id", 1), ("bot_token", 1)], unique=True)
        return db
    except ConnectionFailure as e:
        logger.error(f"Database connection failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected database error: {e}")
        return None

# ========== STATE MANAGEMENT ========== #
user_states = {}
BOTS_PER_PAGE = 8

# ========== HELPER FUNCTIONS ========== #
async def validate_bot_token(token: str) -> tuple:
    """Validate bot token and return username"""
    try:
        test_client = Client(":memory:", bot_token=token, in_memory=True)
        await test_client.start()
        bot_info = await test_client.get_me()
        username = bot_info.username
        await test_client.stop()
        return True, username
    except Exception as e:
        logger.error(f"Bot token validation failed: {e}")
        return False, str(e)

async def validate_mongodb_url(url: str) -> bool:
    """Validate MongoDB connection URL"""
    try:
        client = MongoClient(
            url,
            server_api=ServerApi('1'),
            connectTimeoutMS=3000,
            serverSelectionTimeoutMS=3000
        )
        client.admin.command('ping')
        client.close()
        return True
    except (ConnectionFailure, OperationFailure) as e:
        logger.error(f"MongoDB URL validation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected MongoDB validation error: {e}")
        return False

def get_user_bots(user_id: int, page: int = 0) -> tuple:
    """Get user's bots with pagination"""
    try:
        db = get_management_db()
        if not db:
            return [], 0
        
        collection = db[USER_BOTS_COLLECTION]
        skip = page * BOTS_PER_PAGE
        bots = list(collection.find({"user_id": user_id}).skip(skip).limit(BOTS_PER_PAGE))
        total = collection.count_documents({"user_id": user_id})
        return bots, total
    except PyMongoError as e:
        logger.error(f"Database error fetching user bots: {e}")
        return [], 0

def save_bot_details(user_id: int, bot_token: str, username: str, 
                    db_url: str, db_name: str, collection_name: str) -> bool:
    """Save bot details to database"""
    try:
        db = get_management_db()
        if not db:
            return False
        
        collection = db[USER_BOTS_COLLECTION]
        result = collection.insert_one({
            "user_id": user_id,
            "bot_token": bot_token,
            "username": username,
            "db_url": db_url,
            "db_name": db_name,
            "collection_name": collection_name
        })
        return result.inserted_id is not None
    except PyMongoError as e:
        logger.error(f"Database error saving bot details: {e}")
        return False

def delete_bot(user_id: int, bot_token: str) -> bool:
    """Delete bot from database"""
    try:
        db = get_management_db()
        if not db:
            return False
        
        collection = db[USER_BOTS_COLLECTION]
        result = collection.delete_one({"user_id": user_id, "bot_token": bot_token})
        return result.deleted_count > 0
    except PyMongoError as e:
        logger.error(f"Database error deleting bot: {e}")
        return False

# ========== ADD BOT HANDLER ========== #
@Client.on_message(filters.command("addbot") & filters.private)
async def add_bot_start(client: Client, message: Message):
    user_id = message.from_user.id
    user_states[user_id] = {
        "command": "addbot",
        "step": 1,
        "data": {}
    }
    await message.reply(
        "🔑 **Please send your bot token:**\n\n"
        "You can get it from @BotFather",
        reply_markup=ReplyKeyboardRemove()
    )

@Client.on_message(filters.private & filters.text & ~filters.command(["addbot", "deletebot", "botsbroadcast"]))
async def handle_addbot_steps(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get("command") != "addbot":
        return
    
    state = user_states[user_id]
    text = message.text.strip()
    
    try:
        if state["step"] == 1:  # Waiting for bot token
            is_valid, username = await validate_bot_token(text)
            if not is_valid:
                await message.reply(f"❌ Invalid bot token. Error: {username}\n\nPlease send a valid bot token:")
                return
            
            state["data"]["bot_token"] = text
            state["data"]["username"] = username
            state["step"] = 2
            await message.reply(
                "✅ Bot token validated successfully!\n\n"
                "📝 **Please send your MongoDB connection URL:**"
            )
        
        elif state["step"] == 2:  # Waiting for MongoDB URL
            if not await validate_mongodb_url(text):
                await message.reply("❌ Invalid MongoDB URL. Please check and send again:")
                return
            
            state["data"]["db_url"] = text
            state["step"] = 3
            await message.reply(
                "✅ MongoDB URL validated successfully!\n\n"
                "🗃️ **Please send your database name:**"
            )
        
        elif state["step"] == 3:  # Waiting for database name
            if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", text):
                await message.reply("❌ Invalid database name. Use only letters, numbers, underscores and hyphens:")
                return
            
            state["data"]["db_name"] = text
            state["step"] = 4
            await message.reply(
                "✅ Database name accepted!\n\n"
                "📚 **Please send your collection name:**"
            )
        
        elif state["step"] == 4:  # Waiting for collection name
            if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", text):
                await message.reply("❌ Invalid collection name. Use only letters, numbers, underscores and hyphens:")
                return
            
            state["data"]["collection_name"] = text
            bot_data = state["data"]
            
            if save_bot_details(
                user_id,
                bot_data["bot_token"],
                bot_data["username"],
                bot_data["db_url"],
                bot_data["db_name"],
                bot_data["collection_name"]
            ):
                await message.reply(
                    "🎉 **Bot added successfully!**\n\n"
                    f"🤖 Bot: @{bot_data['username']}\n"
                    f"🗃️ Database: {bot_data['db_name']}\n"
                    f"📚 Collection: {bot_data['collection_name']}"
                )
            else:
                await message.reply("❌ Failed to save bot details. Please try again later.")
            
            del user_states[user_id]
    
    except Exception as e:
        logger.error(f"Error in addbot flow: {e}")
        await message.reply("⚠️ An error occurred. Please try the /addbot command again.")
        if user_id in user_states:
            del user_states[user_id]

# ========== DELETE BOT HANDLER ========== #
@Client.on_message(filters.command("deletebot") & filters.private)
async def delete_bot_start(client: Client, message: Message):
    user_id = message.from_user.id
    bots, total = get_user_bots(user_id)
    
    if not bots:
        await message.reply("❌ You don't have any bots added yet.")
        return
    
    user_states[user_id] = {
        "command": "deletebot",
        "step": 1,
        "page": 0,
        "total_pages": (total + BOTS_PER_PAGE - 1) // BOTS_PER_PAGE,
        "selected_bot": None
    }
    await show_bots_page(client, message, user_id, 0)

async def show_bots_page(client: Client, message: Message, user_id: int, page: int):
    bots, total = get_user_bots(user_id, page)
    total_pages = (total + BOTS_PER_PAGE - 1) // BOTS_PER_PAGE
    
    if not bots:
        await message.reply("❌ No bots found.")
        if user_id in user_states:
            del user_states[user_id]
        return
    
    keyboard = []
    for bot in bots:
        keyboard.append([InlineKeyboardButton(
            f"🤖 @{bot['username']}", 
            callback_data=f"select_bot_{bot['bot_token']}"
        )])
    
    # Pagination controls
    pagination = []
    if page > 0:
        pagination.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        pagination.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    
    if pagination:
        keyboard.append(pagination)
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")])
    
    text = f"🔍 **Select a bot to delete (Page {page+1}/{total_pages}):**"
    await message.reply(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Client.on_callback_query(filters.regex(r"^page_(\d+)$"))
async def handle_bot_page(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_states or user_states[user_id].get("command") != "deletebot":
        await callback_query.answer("Invalid request")
        return
    
    page = int(callback_query.data.split("_")[1])
    user_states[user_id]["page"] = page
    await callback_query.message.delete()
    await show_bots_page(client, callback_query.message, user_id, page)

@Client.on_callback_query(filters.regex(r"^select_bot_(.+)$"))
async def handle_bot_selection(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_states or user_states[user_id].get("command") != "deletebot":
        await callback_query.answer("Invalid request")
        return
    
    bot_token = callback_query.data.split("_", 2)[2]
    user_states[user_id]["selected_bot"] = bot_token
    user_states[user_id]["step"] = 2
    
    # Find bot username for display
    bot_info = next((b for b in get_user_bots(user_id)[0] if b["bot_token"] == bot_token), None)
    if not bot_info:
        await callback_query.answer("Bot not found")
        return
    
    await callback_query.message.edit_text(
        f"⚠️ **Confirm Deletion**\n\n"
        f"Are you sure you want to delete bot @{bot_info['username']}?\n\n"
        "This action cannot be undone!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Delete", callback_data="confirm_delete")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")]
        ])
    )

@Client.on_callback_query(filters.regex("^confirm_delete$"))
async def handle_confirm_delete(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_states or user_states[user_id].get("command") != "deletebot":
        await callback_query.answer("Invalid request")
        return
    
    state = user_states[user_id]
    if not state.get("selected_bot"):
        await callback_query.answer("No bot selected")
        return
    
    bot_token = state["selected_bot"]
    bot_info = next((b for b in get_user_bots(user_id)[0] if b["bot_token"] == bot_token), None)
    
    if delete_bot(user_id, bot_token):
        await callback_query.message.edit_text(
            f"✅ **Bot @{bot_info['username']} deleted successfully!**"
        )
    else:
        await callback_query.message.edit_text(
            "❌ Failed to delete bot. Please try again later."
        )
    
    del user_states[user_id]

@Client.on_callback_query(filters.regex("^cancel_delete$"))
async def handle_cancel_delete(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    await callback_query.message.edit_text("❌ Deletion canceled.")
    if user_id in user_states:
        del user_states[user_id]

# ========== BROADCAST HANDLER ========== #
@Client.on_message(filters.command("botsbroadcast") & filters.private)
async def broadcast_start(client: Client, message: Message):
    user_id = message.from_user.id
    bots, total = get_user_bots(user_id)
    
    if not bots:
        await message.reply("❌ You don't have any bots added yet.")
        return
    
    user_states[user_id] = {
        "command": "broadcast",
        "step": 1,
        "page": 0,
        "total_pages": (total + BOTS_PER_PAGE - 1) // BOTS_PER_PAGE,
        "selected_bot": None,
        "broadcast_message": None
    }
    await show_broadcast_bots_page(client, message, user_id, 0)

async def show_broadcast_bots_page(client: Client, message: Message, user_id: int, page: int):
    bots, total = get_user_bots(user_id, page)
    total_pages = (total + BOTS_PER_PAGE - 1) // BOTS_PER_PAGE
    
    if not bots:
        await message.reply("❌ No bots found.")
        if user_id in user_states:
            del user_states[user_id]
        return
    
    keyboard = []
    for bot in bots:
        keyboard.append([InlineKeyboardButton(
            f"📢 @{bot['username']}", 
            callback_data=f"broadcast_select_{bot['bot_token']}"
        )])
    
    # Pagination controls
    pagination = []
    if page > 0:
        pagination.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"broadcast_page_{page-1}"))
    if page < total_pages - 1:
        pagination.append(InlineKeyboardButton("Next ➡️", callback_data=f"broadcast_page_{page+1}"))
    
    if pagination:
        keyboard.append(pagination)
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")])
    
    text = f"🔊 **Select a bot to broadcast with (Page {page+1}/{total_pages}):**"
    await message.reply(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Client.on_callback_query(filters.regex(r"^broadcast_page_(\d+)$"))
async def handle_broadcast_page(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_states or user_states[user_id].get("command") != "broadcast":
        await callback_query.answer("Invalid request")
        return
    
    page = int(callback_query.data.split("_")[2])
    user_states[user_id]["page"] = page
    await callback_query.message.delete()
    await show_broadcast_bots_page(client, callback_query.message, user_id, page)

@Client.on_callback_query(filters.regex(r"^broadcast_select_(.+)$"))
async def handle_broadcast_selection(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_states or user_states[user_id].get("command") != "broadcast":
        await callback_query.answer("Invalid request")
        return
    
    bot_token = callback_query.data.split("_", 2)[2]
    user_states[user_id]["selected_bot"] = bot_token
    user_states[user_id]["step"] = 2
    
    bot_info = next((b for b in get_user_bots(user_id)[0] if b["bot_token"] == bot_token), None)
    if not bot_info:
        await callback_query.answer("Bot not found")
        return
    
    await callback_query.message.edit_text(
        f"📢 **Broadcast with @{bot_info['username']}**\n\n"
        "Please send your broadcast message (text, photo, or document):"
    )

@Client.on_message(filters.private & (filters.text | filters.photo | filters.document) & ~filters.command(["addbot", "deletebot", "botsbroadcast"]))
async def handle_broadcast_message(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get("command") != "broadcast":
        return
    
    state = user_states[user_id]
    if state["step"] != 2 or not state.get("selected_bot"):
        return
    
    # Save message details
    state["broadcast_message"] = {
        "text": message.text or message.caption,
        "media": None
    }
    
    if message.photo:
        state["broadcast_message"]["media"] = {
            "type": "photo",
            "file_id": message.photo.file_id
        }
    elif message.document:
        state["broadcast_message"]["media"] = {
            "type": "document",
            "file_id": message.document.file_id
        }
    
    state["step"] = 3
    bot_info = next((b for b in get_user_bots(user_id)[0] if b["bot_token"] == state["selected_bot"]), None)
    
    await message.reply(
        f"📢 **Confirm Broadcast**\n\n"
        f"🤖 Bot: @{bot_info['username']}\n"
        f"✉️ Message: {state['broadcast_message']['text'][:50]}...\n\n"
        "Send /confirm to proceed or /cancel to abort:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("/confirm"), KeyboardButton("/cancel")]],
            resize_keyboard=True
        )
    )

@Client.on_message(filters.command("confirm") & filters.private)
async def handle_broadcast_confirm(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get("command") != "broadcast":
        return
    
    state = user_states[user_id]
    if state["step"] != 3 or not state.get("selected_bot") or not state.get("broadcast_message"):
        return
    
    bot_info = next((b for b in get_user_bots(user_id)[0] if b["bot_token"] == state["selected_bot"]), None)
    if not bot_info:
        await message.reply("❌ Bot not found in database")
        del user_states[user_id]
        return
    
    # Perform broadcast
    processing_msg = await message.reply("🚀 Starting broadcast...")
    
    success = 0
    failed = 0
    total = 0
    
    try:
        # Connect to user's MongoDB
        user_db_client = AsyncIOMotorClient(bot_info["db_url"])
        db = user_db_client[bot_info["db_name"]]
        collection = db[bot_info["collection_name"]]
        
        # Get all users
        users = await collection.find({"logged_in": True}).to_list(length=None)
        total = len(users)
        
        # Create broadcast bot client
        broadcast_bot = Client("broadcast_bot", bot_token=state["selected_bot"], in_memory=True)
        await broadcast_bot.start()
        
        for user in users:
            try:
                chat_id = user["id"]
                msg_data = state["broadcast_message"]
                
                if msg_data["media"]:
                    if msg_data["media"]["type"] == "photo":
                        await broadcast_bot.send_photo(
                            chat_id,
                            msg_data["media"]["file_id"],
                            caption=msg_data["text"]
                        )
                    elif msg_data["media"]["type"] == "document":
                        await broadcast_bot.send_document(
                            chat_id,
                            msg_data["media"]["file_id"],
                            caption=msg_data["text"]
                        )
                else:
                    await broadcast_bot.send_message(chat_id, msg_data["text"])
                
                success += 1
                if success % 10 == 0:  # Update progress every 10 messages
                    await processing_msg.edit_text(
                        f"📤 Broadcasting...\n\n"
                        f"✅ Success: {success}\n"
                        f"❌ Failed: {failed}\n"
                        f"⏳ Progress: {success+failed}/{total}"
                    )
                
                # Avoid flooding
                await asyncio.sleep(0.1)
            
            except Exception as e:
                failed += 1
                logger.warning(f"Broadcast failed for {chat_id}: {str(e)}")
        
        await broadcast_bot.stop()
        await user_db_client.close()
        
        await processing_msg.edit_text(
            f"🎉 **Broadcast Completed!**\n\n"
            f"🤖 Bot: @{bot_info['username']}\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}\n"
            f"📊 Total: {total}"
        )
    
    except Exception as e:
        logger.error(f"Broadcast failed: {e}")
        await message.reply(f"❌ Broadcast failed: {str(e)}")
    
    del user_states[user_id]

@Client.on_message(filters.command("cancel") & filters.private)
async def handle_broadcast_cancel(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in user_states and user_states[user_id].get("command") == "broadcast":
        await message.reply("❌ Broadcast canceled.")
        del user_states[user_id]
