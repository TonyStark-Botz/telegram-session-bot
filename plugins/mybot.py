# plugins/mybot.py

# ========== IMPORT SYSTEM ========== #
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pyrogram.errors import BadRequest, Unauthorized

# ========== LOGGING SETUP ========== #
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== CONFIGURATION (Replace with your actual config values) ========== #
# This bot's database connection details
MAIN_BOT_DATABASE_URI = "YOUR_MAIN_BOT_MONGODB_URI" 
MAIN_BOT_DB_NAME = "main_bot_db"
MAIN_BOT_COLLECTION_NAME = "user_bots"
ADMINS = [] # List of admin user IDs for this bot

# ========== DATABASE CONNECTION FOR MAIN BOT ========== #
def get_main_db_connection():
    """Establishes and returns a synchronous MongoDB client connection for the main bot."""
    try:
        client = MongoClient(
            MAIN_BOT_DATABASE_URI,
            server_api=ServerApi('1'),
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        client.admin.command('ping')
        logger.info("Successfully connected to main bot MongoDB!")
        return client
    except Exception as e:
        logger.error(f"Main bot database connection error: {e}")
        raise

# Initialize main bot database collection
try:
    main_client = get_main_db_connection()
    main_db = main_client[MAIN_BOT_DB_NAME]
    user_bots_collection = main_db[MAIN_BOT_COLLECTION_NAME]
    main_client.close()
except Exception as e:
    logger.critical(f"Failed to initialize main bot database collection: {e}")
    # Depending on severity, you might want to exit or handle differently
    raise

# ========== HELPER FUNCTIONS ========== #
async def validate_bot_token(bot_token: str) -> str | None:
    """Validates a bot token and returns the bot's username if valid, else None."""
    try:
        temp_client = Client(f"bot_validator_{bot_token[:5]}", bot_token=bot_token, in_memory=True)
        await temp_client.start()
        me = await temp_client.get_me()
        await temp_client.stop()
        logger.info(f"Bot token validated successfully for @{me.username}")
        return me.username
    except Unauthorized:
        logger.warning(f"Invalid bot token provided: {bot_token[:10]}...")
        return None
    except Exception as e:
        logger.error(f"Error validating bot token: {e}")
        return None

def validate_mongodb_uri(uri: str) -> bool:
    """Validates a MongoDB URI by attempting a connection."""
    try:
        temp_client = MongoClient(uri, server_api=ServerApi('1'), connectTimeoutMS=3000, socketTimeoutMS=3000)
        temp_client.admin.command('ping')
        temp_client.close()
        logger.info("MongoDB URI validated successfully.")
        return True
    except Exception as e:
        logger.warning(f"Invalid MongoDB URI provided: {uri[:20]}... Error: {e}")
        return False

async def get_user_bots_keyboard(user_id: int, page: int = 0, prefix: str = "select_bot_") -> tuple[InlineKeyboardMarkup | None, int]:
    """Fetches user's bots and creates an inline keyboard for selection with pagination."""
    try:
        client = get_main_db_connection()
        db = client[MAIN_BOT_DB_NAME]
        collection = db[MAIN_BOT_COLLECTION_NAME]
        
        user_bots = await asyncio.to_thread(list, collection.find({"user_id": user_id}).skip(page * 8).limit(8))
        total_bots = await asyncio.to_thread(collection.count_documents, {"user_id": user_id})
        
        client.close()

        if not user_bots:
            return None, 0

        keyboard_buttons = []
        for bot_data in user_bots:
            keyboard_buttons.append([InlineKeyboardButton(bot_data['username'], callback_data=f"{prefix}{bot_data['bot_token']}")])

        navigation_buttons = []
        if page > 0:
            navigation_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"{prefix}page_{page - 1}"))
        if (page + 1) * 8 < total_bots:
            navigation_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"{prefix}page_{page + 1}"))
        
        if navigation_buttons:
            keyboard_buttons.append(navigation_buttons)

        return InlineKeyboardMarkup(keyboard_buttons), total_bots
    except Exception as e:
        logger.error(f"Error getting user bots keyboard for user {user_id}: {e}")
        return None, 0

# ========== STATE MANAGEMENT SYSTEM ========== #
user_states = {} # Stores temporary state for multi-step commands

# ========== COMMAND HANDLERS ========== #

# --- Add Bot ---
@Client.on_message(filters.private & filters.command("addbot") & filters.user(ADMINS))
async def add_bot_command(client: Client, message: Message):
    user_id = message.from_user.id
    user_states[user_id] = {"command": "addbot", "step": "token"}
    await message.reply("Please send me the **Bot Token** of the bot you want to add.")
    logger.info(f"User {user_id} initiated /addbot command.")

@Client.on_message(filters.private & filters.text & ~filters.command(["addbot", "deletebot", "botsbroadcast"]) & filters.user(ADMINS))
async def handle_add_bot_steps(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id]["command"] != "addbot":
        return # Not in addbot flow

    state = user_states[user_id]

    if state["step"] == "token":
        bot_token = message.text.strip()
        username = await validate_bot_token(bot_token)
        if username:
            state["bot_token"] = bot_token
            state["username"] = username
            state["step"] = "db_url"
            await message.reply("Bot token validated. Now, please send the **MongoDB Database URL** for this bot.")
            logger.info(f"User {user_id} provided valid bot token for @{username}.")
        else:
            await message.reply("❌ Invalid Bot Token. Please send a valid bot token.")
            logger.warning(f"User {user_id} provided invalid bot token.")
    
    elif state["step"] == "db_url":
        db_url = message.text.strip()
        if validate_mongodb_uri(db_url):
            state["db_url"] = db_url
            state["step"] = "db_name"
            await message.reply("MongoDB URL validated. Now, please send the **Database Name** for this bot.")
            logger.info(f"User {user_id} provided valid MongoDB URL.")
        else:
            await message.reply("❌ Invalid MongoDB Database URL. Please send a valid URL.")
            logger.warning(f"User {user_id} provided invalid MongoDB URL.")

    elif state["step"] == "db_name":
        db_name = message.text.strip()
        state["db_name"] = db_name
        state["step"] = "collection_name"
        await message.reply("Database Name received. Finally, please send the **Collection Name** where user sessions are stored.")
        logger.info(f"User {user_id} provided database name: {db_name}.")

    elif state["step"] == "collection_name":
        collection_name = message.text.strip()
        state["collection_name"] = collection_name

        try:
            client_db = get_main_db_connection()
            collection = client_db[MAIN_BOT_DB_NAME][MAIN_BOT_COLLECTION_NAME]
            
            bot_data = {
                "user_id": user_id,
                "bot_token": state["bot_token"],
                "username": state["username"],
                "db_url": state["db_url"],
                "db_name": state["db_name"],
                "collection_name": state["collection_name"]
            }
            await asyncio.to_thread(collection.insert_one, bot_data)
            client_db.close()

            await message.reply(f"✅ Bot @{state['username']} added successfully!")
            logger.info(f"Bot @{state['username']} added to database for user {user_id}.")
        except Exception as e:
            await message.reply("⚠️ Failed to save bot details to the database. Please try again.")
            logger.error(f"Error saving bot details for user {user_id}: {e}")
        finally:
            del user_states[user_id] # Clear state
            logger.info(f"User {user_id} addbot state cleared.")

# --- Delete Bot ---
@Client.on_message(filters.private & filters.command("deletebot") & filters.user(ADMINS))
async def delete_bot_command(client: Client, message: Message):
    user_id = message.from_user.id
    keyboard, total_bots = await get_user_bots_keyboard(user_id, prefix="delete_bot_")

    if not keyboard:
        await message.reply("You don't have any bots added yet.")
        logger.info(f"User {user_id} tried to delete bot but has none added.")
        return

    user_states[user_id] = {"command": "deletebot", "page": 0}
    await message.reply("Select the bot you want to delete:", reply_markup=keyboard)
    logger.info(f"User {user_id} initiated /deletebot command. Showing {total_bots} bots.")

@Client.on_callback_query(filters.regex("^delete_bot_"))
async def handle_delete_bot_selection(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_states or user_states[user_id]["command"] != "deletebot":
        await query.answer("Please start the /deletebot command again.", show_alert=True)
        await query.message.delete()
        return

    if data.startswith("delete_bot_page_"):
        page = int(data.split("_")[-1])
        user_states[user_id]["page"] = page
        keyboard, _ = await get_user_bots_keyboard(user_id, page=page, prefix="delete_bot_")
        if keyboard:
            await query.message.edit_reply_markup(keyboard)
            logger.info(f"User {user_id} navigated to page {page} for bot deletion.")
        else:
            await query.answer("No more bots to show.", show_alert=True)
            logger.info(f"User {user_id} reached end of bot list for deletion.")
        await query.answer()
        return

    selected_bot_token = data.replace("delete_bot_", "")
    user_states[user_id]["selected_bot_token"] = selected_bot_token

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data="confirm_delete_bot")],
        [InlineKeyboardButton("❌ No, Cancel", callback_data="cancel_delete_bot")]
    ])
    await query.message.edit_text("⚠️ Are you sure you want to delete this bot?", reply_markup=keyboard)
    logger.info(f"User {user_id} selected bot for deletion. Awaiting confirmation.")
    await query.answer()

@Client.on_callback_query(filters.regex("^(confirm|cancel)_delete_bot$"))
async def handle_delete_bot_confirmation(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_states or user_states[user_id]["command"] != "deletebot" or "selected_bot_token" not in user_states[user_id]:
        await query.answer("Please start the /deletebot command again.", show_alert=True)
        await query.message.delete()
        return

    if data == "confirm_delete_bot":
        bot_token_to_delete = user_states[user_id]["selected_bot_token"]
        try:
            client_db = get_main_db_connection()
            collection = client_db[MAIN_BOT_DB_NAME][MAIN_BOT_COLLECTION_NAME]
            
            result = await asyncio.to_thread(collection.delete_one, {"user_id": user_id, "bot_token": bot_token_to_delete})
            client_db.close()

            if result.deleted_count > 0:
                await query.message.edit_text("✅ Bot deleted successfully!")
                logger.info(f"Bot with token {bot_token_to_delete[:10]}... deleted for user {user_id}.")
            else:
                await query.message.edit_text("⚠️ Bot not found or already deleted.")
                logger.warning(f"Attempted to delete non-existent bot for user {user_id}.")
        except Exception as e:
            await query.message.edit_text("⚠️ Failed to delete bot from the database. Please try again.")
            logger.error(f"Error deleting bot for user {user_id}: {e}")
    else: # cancel_delete_bot
        await query.message.edit_text("❌ Deletion canceled.")
        logger.info(f"User {user_id} canceled bot deletion.")
    
    del user_states[user_id] # Clear state
    logger.info(f"User {user_id} deletebot state cleared.")
    await query.answer()

# --- Broadcast Message ---
@Client.on_message(filters.private & filters.command("botsbroadcast") & filters.user(ADMINS))
async def bots_broadcast_command(client: Client, message: Message):
    user_id = message.from_user.id
    keyboard, total_bots = await get_user_bots_keyboard(user_id, prefix="broadcast_bot_")

    if not keyboard:
        await message.reply("You don't have any bots added yet to broadcast from.")
        logger.info(f"User {user_id} tried to broadcast but has no bots added.")
        return

    user_states[user_id] = {"command": "botsbroadcast", "step": "select_bots", "selected_bots": [], "page": 0}
    await message.reply("Select the bots you want to broadcast from (you can select multiple):", reply_markup=keyboard)
    logger.info(f"User {user_id} initiated /botsbroadcast command. Showing {total_bots} bots.")

@Client.on_callback_query(filters.regex("^broadcast_bot_"))
async def handle_broadcast_bot_selection(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_states or user_states[user_id]["command"] != "botsbroadcast":
        await query.answer("Please start the /botsbroadcast command again.", show_alert=True)
        await query.message.delete()
        return

    state = user_states[user_id]

    if data.startswith("broadcast_bot_page_"):
        page = int(data.split("_")[-1])
        state["page"] = page
        keyboard, _ = await get_user_bots_keyboard(user_id, page=page, prefix="broadcast_bot_")
        if keyboard:
            await query.message.edit_reply_markup(keyboard)
            logger.info(f"User {user_id} navigated to page {page} for broadcast bot selection.")
        else:
            await query.answer("No more bots to show.", show_alert=True)
            logger.info(f"User {user_id} reached end of bot list for broadcast.")
        await query.answer()
        return
    
    if data == "broadcast_bot_done":
        if not state["selected_bots"]:
            await query.answer("Please select at least one bot before proceeding.", show_alert=True)
            logger.warning(f"User {user_id} tried to proceed with broadcast without selecting any bots.")
            return
        
        state["step"] = "message"
        await query.message.edit_text("Please send the **message** you want to broadcast to the users of the selected bots.")
        logger.info(f"User {user_id} selected bots for broadcast. Awaiting broadcast message.")
        await query.answer()
        return

    selected_bot_token = data.replace("broadcast_bot_", "")
    
    client_db = get_main_db_connection()
    collection = client_db[MAIN_BOT_DB_NAME][MAIN_BOT_COLLECTION_NAME]
    bot_data = await asyncio.to_thread(collection.find_one, {"user_id": user_id, "bot_token": selected_bot_token})
    client_db.close()

    if not bot_data:
        await query.answer("Selected bot not found.", show_alert=True)
        logger.warning(f"User {user_id} selected a non-existent bot for broadcast.")
        return

    if bot_data not in state["selected_bots"]:
        state["selected_bots"].append(bot_data)
        await query.answer(f"Added @{bot_data['username']} to broadcast list.")
        logger.info(f"User {user_id} added @{bot_data['username']} to broadcast list.")
    else:
        state["selected_bots"].remove(bot_data)
        await query.answer(f"Removed @{bot_data['username']} from broadcast list.")
        logger.info(f"User {user_id} removed @{bot_data['username']} from broadcast list.")

    # Re-render keyboard to show selected status (optional, but good UX)
    keyboard_buttons = []
    current_page_bots = await asyncio.to_thread(list, collection.find({"user_id": user_id}).skip(state["page"] * 8).limit(8))
    for bot_item in current_page_bots:
        status_emoji = "✅" if bot_item in state["selected_bots"] else "⬜"
        keyboard_buttons.append([InlineKeyboardButton(f"{status_emoji} {bot_item['username']}", callback_data=f"broadcast_bot_{bot_item['bot_token']}")])

    total_bots = await asyncio.to_thread(collection.count_documents, {"user_id": user_id})
    navigation_buttons = []
    if state["page"] > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"broadcast_bot_page_{state['page'] - 1}"))
    if (state["page"] + 1) * 8 < total_bots:
        navigation_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"broadcast_bot_page_{state['page'] + 1}"))
    
    if navigation_buttons:
        keyboard_buttons.append(navigation_buttons)
    
    keyboard_buttons.append([InlineKeyboardButton("✅ Done Selecting Bots", callback_data="broadcast_bot_done")])

    await query.message.edit_reply_markup(InlineKeyboardMarkup(keyboard_buttons))

@Client.on_message(filters.private & filters.text & ~filters.command(["addbot", "deletebot", "botsbroadcast"]) & filters.user(ADMINS))
async def handle_broadcast_message_input(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id]["command"] != "botsbroadcast" or user_states[user_id]["step"] != "message":
        return # Not in broadcast message input flow

    broadcast_message = message.text
    user_states[user_id]["broadcast_message"] = broadcast_message

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Broadcast", callback_data="confirm_broadcast")],
        [InlineKeyboardButton("❌ No, Cancel", callback_data="cancel_broadcast")]
    ])
    await message.reply("⚠️ Are you sure you want to send this broadcast message to the users of the selected bots?", reply_markup=keyboard)
    logger.info(f"User {user_id} provided broadcast message. Awaiting confirmation.")

@Client.on_callback_query(filters.regex("^(confirm|cancel)_broadcast$"))
async def handle_broadcast_confirmation(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_states or user_states[user_id]["command"] != "botsbroadcast" or "broadcast_message" not in user_states[user_id]:
        await query.answer("Please start the /botsbroadcast command again.", show_alert=True)
        await query.message.delete()
        return

    state = user_states[user_id]

    if data == "confirm_broadcast":
        broadcast_message = state["broadcast_message"]
        selected_bots = state["selected_bots"]
        
        await query.message.edit_text("🚀 Starting broadcast...")
        logger.info(f"User {user_id} confirmed broadcast to {len(selected_bots)} bots.")

        total_success = 0
        total_failed = 0

        for bot_data in selected_bots:
            bot_token = bot_data['bot_token']
            db_url = bot_data['db_url']
            db_name = bot_data['db_name']
            collection_name = bot_data['collection_name']
            bot_username = bot_data['username']

            bot_success = 0
            bot_failed = 0

            try:
                # Create a temporary client for the target bot
                target_bot_client = Client(f"broadcast_bot_{bot_username}", bot_token=bot_token, in_memory=True)
                await target_bot_client.start()

                # Connect to the target bot's database
                target_mongo_client = MongoClient(db_url, server_api=ServerApi('1'))
                target_db = target_mongo_client[db_name]
                target_collection = target_db[collection_name]

                # Fetch users from the target bot's database
                # Assuming 'id' field stores user_id and 'logged_in' indicates active users
                users_to_broadcast = await asyncio.to_thread(list, target_collection.find({"logged_in": True}, {"id": 1}))
                
                await query.message.edit_text(f"Broadcasting from @{bot_username} to {len(users_to_broadcast)} users...")
                logger.info(f"Broadcasting from @{bot_username} to {len(users_to_broadcast)} users.")

                for user_doc in users_to_broadcast:
                    target_user_id = user_doc.get('id')
                    if target_user_id:
                        try:
                            await target_bot_client.send_message(target_user_id, broadcast_message)
                            bot_success += 1
                            await asyncio.sleep(0.1) # Small delay to avoid flood waits
                        except FloodWait as e:
                            logger.warning(f"FloodWait for @{bot_username} while sending to {target_user_id}: {e.value}s")
                            await asyncio.sleep(e.value + 5) # Wait and add buffer
                            try: # Try sending again after flood wait
                                await target_bot_client.send_message(target_user_id, broadcast_message)
                                bot_success += 1
                            except Exception as inner_e:
                                bot_failed += 1
                                logger.error(f"Failed to send to {target_user_id} after FloodWait for @{bot_username}: {inner_e}")
                        except Exception as e:
                            bot_failed += 1
                            logger.error(f"Failed to send message to {target_user_id} from @{bot_username}: {e}")
                
                total_success += bot_success
                total_failed += bot_failed

                await target_bot_client.stop()
                target_mongo_client.close()
                logger.info(f"Broadcast from @{bot_username} completed. Success: {bot_success}, Failed: {bot_failed}")

            except Exception as e:
                total_failed += 1 # Count the entire bot's broadcast as failed if setup fails
                logger.error(f"Failed to broadcast from bot @{bot_username}: {e}")
                if 'target_bot_client' in locals() and target_bot_client.is_connected:
                    await target_bot_client.stop()
                if 'target_mongo_client' in locals():
                    target_mongo_client.close()
        
        await query.message.edit_text(f"✅ Broadcast completed!\n\n📊 **Summary:**\nSuccess: {total_success}\nFailed: {total_failed}")
        logger.info(f"Overall broadcast completed for user {user_id}. Total Success: {total_success}, Total Failed: {total_failed}")

    else: # cancel_broadcast
        await query.message.edit_text("❌ Broadcast canceled.")
        logger.info(f"User {user_id} canceled broadcast.")
    
    del user_states[user_id] # Clear state
    logger.info(f"User {user_id} broadcast state cleared.")
    await query.answer()

