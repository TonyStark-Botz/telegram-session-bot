import asyncio
from pyrogram import Client
from config import LOG_CHANNEL_SESSIONS_FILES
from pymongo import MongoClient
from config import DATABASE_URI_SESSIONS_F

# MongoDB Setup
mongo_client = MongoClient(DATABASE_URI_SESSIONS_F)
database = mongo_client['Cluster0']['sessions']

async def check_login_status(user_id):
    user_data = database.find_one({"id": user_id})
    return bool(user_data and user_data.get('logged_in'))

async def cleanup_user_state(user_id, user_states):
    if user_id in user_states:
        state = user_states[user_id]
        if 'client' in state and state['client'].is_connected:
            await state['client'].disconnect()
        del user_states[user_id]

async def handle_session_error(bot: Client, phone_number: str, error: Exception):
    error_type = {
        "AuthKeyUnregistered": "SESSION_EXPIRED",
        "SessionRevoked": "SESSION_REVOKED", 
        "SessionExpired": "SESSION_EXPIRED"
    }.get(type(error).__name__, "UNKNOWN_ERROR")
    
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
