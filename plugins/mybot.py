# plugins/mybot.py
import asyncio
import re
import math
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)
from pymongo import MongoClient
from bson import ObjectId

from config import (
    API_ID,
    API_HASH,
    ADMINS,
    DATABASE_URI_SESSIONS_F,      # main DB for storing all bots info
    LOG_CHANNEL_SESSIONS_FILES,    # log channel id (int)
)

# ---------------------------
# Mongo Setup (Main Database)
# ---------------------------
_main_mongo = MongoClient(DATABASE_URI_SESSIONS_F)
_main_db = _main_mongo["main_bot_db"]  # yaha DB naam specify karo
BOTS_COL = _main_db["clone_bots"]

# ------------
# UI Constants
# ------------
PER_PAGE = 8
EMOJI_OK = "✅"
EMOJI_NO = "❌"
EMOJI_WARN = "⚠️"
EMOJI_BROAD = "📣"
EMOJI_BOT = "🤖"
EMOJI_DELETE = "🗑️"
EMOJI_ADD = "➕"
EMOJI_NEXT = "▶️"
EMOJI_PREV = "◀️"
EMOJI_DONE = "✅"
EMOJI_CANCEL = "🚫"

# --------------------------------
# In-memory State for Guided Flows
# --------------------------------
# NOTE: Simple in-process state. Survives while process runs.
# Keys are admin user_id.
states: Dict[int, Dict] = {}

def reset_state(user_id: int):
    if user_id in states:
        del states[user_id]

# ------------------------
# Helpers: Validation/DB
# ------------------------
async def validate_bot_token_and_get_me(token: str) -> Tuple[bool, Optional[int], Optional[str], Optional[str]]:
    """
    Returns (ok, bot_id, bot_username, error_str)
    """
    try:
        # Minimal sanity check via regex
        if not re.match(r"^\d+:[A-Za-z0-9_-]{20,}$", token.strip()):
            return (False, None, None, "Invalid token format.")

        temp = Client(
            name=f"__temp_{token.split(':', 1)[0]}__",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=token,
            no_updates=True,
            in_memory=True,
        )
        await temp.start()
        me = await temp.get_me()
        username = me.username or ""
        bot_id = me.id
        await temp.stop()
        if not username:
            return (False, None, None, "Could not fetch bot username.")
        return (True, bot_id, username, None)
    except Exception as e:
        return (False, None, None, f"{e}")

def validate_mongo_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Returns (ok, error_str)
    """
    try:
        cli = MongoClient(url, serverSelectionTimeoutMS=4000)
        # Ping
        cli.admin.command("ping")
        cli.close()
        return (True, None)
    except Exception as e:
        return (False, str(e))

def get_user_bots(user_id: int) -> List[dict]:
    return list(BOTS_COL.find({"user_id": int(user_id)}).sort("_id", 1))

def build_pages(items: List[dict], page: int, per_page: int = PER_PAGE) -> Tuple[List[dict], int]:
    total = len(items)
    pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], page

def pick_id_keys_from_user_doc(doc: dict) -> Optional[int]:
    """
    Try to extract a Telegram user/chat id from generic user docs.
    Tries common keys: 'user_id', 'id', 'chat_id'
    Returns int or None.
    """
    for k in ("user_id", "id", "chat_id"):
        if k in doc:
            try:
                return int(doc[k])
            except Exception:
                continue
    return None

# ------------------------
# Inline Keyboards Builders
# ------------------------
def pagination_row(cb_prev: str, cb_next: str, page: int, pages: int) -> List[InlineKeyboardButton]:
    row = []
    if page > 1:
        row.append(InlineKeyboardButton(f"{EMOJI_PREV} Prev", callback_data=cb_prev))
    row.append(InlineKeyboardButton(f"{page}/{pages}", callback_data="noop"))
    if page < pages:
        row.append(InlineKeyboardButton(f"Next {EMOJI_NEXT}", callback_data=cb_next))
    return row

def del_list_kb(user_id: int, items: List[dict], page: int, pages: int) -> InlineKeyboardMarkup:
    rows = []
    for b in items:
        uname = b.get("username", "unknown")
        bid = str(b["_id"])
        rows.append([InlineKeyboardButton(f"{EMOJI_BOT} @{uname}", callback_data=f"del_choose:{bid}:{page}")])
    nav = pagination_row(f"del_page:{user_id}:{page-1}", f"del_page:{user_id}:{page+1}", page, pages)
    rows.append(nav)
    rows.append([InlineKeyboardButton(f"{EMOJI_CANCEL} Cancel", callback_data="del_cancel")])
    return InlineKeyboardMarkup(rows)

def del_confirm_kb(bot_oid: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{EMOJI_DELETE} Yes, delete", callback_data=f"del_yes:{bot_oid}:{page}")],
        [InlineKeyboardButton(f"{EMOJI_CANCEL} No, cancel", callback_data=f"del_no:{page}")]
    ])

def bb_list_kb(user_id: int, items: List[dict], page: int, pages: int, selected: List[str]) -> InlineKeyboardMarkup:
    rows = []
    for b in items:
        oid = str(b["_id"])
        uname = b.get("username", "unknown")
        mark = "☑️" if oid in selected else "▫️"
        rows.append([InlineKeyboardButton(f"{mark} @{uname}", callback_data=f"bb_toggle:{oid}:{page}")])
    nav = pagination_row(f"bb_page:{user_id}:{page-1}", f"bb_page:{user_id}:{page+1}", page, pages)
    rows.append(nav)
    rows.append([
        InlineKeyboardButton(f"{EMOJI_DONE} Done", callback_data="bb_done"),
        InlineKeyboardButton(f"{EMOJI_CANCEL} Cancel", callback_data="bb_cancel")
    ])
    return InlineKeyboardMarkup(rows)

def bb_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{EMOJI_OK} Confirm Broadcast", callback_data="bb_confirm")],
        [InlineKeyboardButton(f"{EMOJI_CANCEL} Cancel", callback_data="bb_cancel")]
    ])

# ------------------------
# /addbot Flow
# ------------------------
@Client.on_message(filters.command(["addbot"]) & filters.user(ADMINS))
async def addbot_entry(c: Client, m: Message):
    user_id = m.from_user.id
    reset_state(user_id)
    states[user_id] = {"flow": "addbot", "step": "token"}
    await m.reply_text(
        f"{EMOJI_ADD} <b>Step 1/4:</b> Send the <b>Bot Token</b> (forward from @BotFather or paste token).\n\n"
        f"Send <code>/cancel</code> to stop.",
        quote=True
    )

@Client.on_message(filters.user(ADMINS) & ~filters.command(["addbot", "deletebot", "botsbroadcast"]))
async def addbot_collector(c: Client, m: Message):
    user_id = m.from_user.id
    st = states.get(user_id)
    if not st or st.get("flow") != "addbot":
        return

    # Cancel
    if m.text and m.text.strip().lower() == "/cancel":
        reset_state(user_id)
        await m.reply_text(f"{EMOJI_CANCEL} Cancelled.")
        return

    step = st.get("step")

    # Step: Token
    if step == "token":
        token: Optional[str] = None
        if m.forward_from and m.forward_from.id == 93372553:  # BotFather
            try:
                token = re.findall(r"\b(\d+:[A-Za-z0-9_-]+)\b", m.text or "")[0]
            except Exception:
                token = None
        else:
            token = (m.text or "").strip()

        if not token:
            await m.reply_text(f"{EMOJI_WARN} Invalid input. Please send a valid bot token.")
            return

        await m.reply_text("Validating bot token, please wait…")
        ok, bot_id, username, err = await validate_bot_token_and_get_me(token)
        if not ok:
            await m.reply_text(f"{EMOJI_WARN} Bot token validation failed:\n<code>{err}</code>")
            return

        st["token"] = token
        st["bot_id"] = bot_id
        st["username"] = username
        st["step"] = "db_url"
        await m.reply_text(
            f"{EMOJI_OK} Bot detected: <b>@{username}</b>\n\n"
            f"<b>Step 2/4:</b> Send the <b>Database URL</b> (Mongo URI) for this bot’s users.\n"
            f"Example: <code>mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority</code>"
        )
        return

    # Step: DB URL
    if step == "db_url":
        db_url = (m.text or "").strip()
        if not db_url:
            await m.reply_text(f"{EMOJI_WARN} Please send a valid MongoDB connection string.")
            return

        ok, err = validate_mongo_url(db_url)
        if not ok:
            await m.reply_text(f"{EMOJI_WARN} Database URL validation failed:\n<code>{err}</code>\n\n"
                               f"Send another URL or /cancel.")
            return

        st["db_url"] = db_url
        st["step"] = "db_name"
        await m.reply_text(
            f"{EMOJI_OK} DB URL looks good.\n\n<b>Step 3/4:</b> Send the <b>Database Name</b> (where users are stored)."
        )
        return

    # Step: DB Name
    if step == "db_name":
        db_name = (m.text or "").strip()
        if not db_name:
            await m.reply_text(f"{EMOJI_WARN} Please send a valid database name.")
            return
        st["db_name"] = db_name
        st["step"] = "coll_name"
        await m.reply_text(
            f"<b>Step 4/4:</b> Send the <b>Collection Name</b> that contains user IDs."
        )
        return

    # Step: Collection Name -> Save
    if step == "coll_name":
        coll_name = (m.text or "").strip()
        if not coll_name:
            await m.reply_text(f"{EMOJI_WARN} Please send a valid collection name.")
            return

        # Save in main DB
        token = st["token"]
        bot_id = st["bot_id"]
        username = st["username"]
        db_url = st["db_url"]
        db_name = st["db_name"]

        BOTS_COL.insert_one({
            "user_id": int(user_id),
            "bot_id": int(bot_id),
            "username": username,
            "bot_token": token,
            "db_url": db_url,
            "db_name": coll_name and db_name,       # db name
            "collection_name": coll_name,           # collection
            "created_at": datetime.utcnow(),
        })

        reset_state(user_id)
        await m.reply_text(f"{EMOJI_OK} Bot added successfully! <b>@{username}</b>")
        try:
            await c.send_message(
                LOG_CHANNEL_SESSIONS_FILES,
                f"{EMOJI_ADD} <b>BOT ADDED</b>\n"
                f"Admin: <code>{user_id}</code>\n"
                f"Bot: @{username} (<code>{bot_id}</code>)"
            )
        except Exception:
            pass
        return

# ------------------------
# /deletebot Flow
# ------------------------
@Client.on_message(filters.command(["deletebot"]) & filters.user(ADMINS))
async def deletebot_entry(c: Client, m: Message):
    user_id = m.from_user.id
    bots = get_user_bots(user_id)
    if not bots:
        await m.reply_text("No bots found. Add one with /addbot")
        return
    page = 1
    total = len(bots)
    pages = max(1, math.ceil(total / PER_PAGE))
    view, page = build_pages(bots, page)
    kb = del_list_kb(user_id, view, page, pages)
    await m.reply_text(
        f"{EMOJI_DELETE} Select a bot to delete:",
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex(r"^del_page:(\d+):(\d+)$") & filters.user(ADMINS))
async def cb_del_page(c: Client, q: CallbackQuery):
    user_id = int(q.matches[0].group(1))
    page = int(q.matches[0].group(2))
    if q.from_user.id != user_id:
        return await q.answer("Not for you.", show_alert=True)

    bots = get_user_bots(user_id)
    total = len(bots)
    pages = max(1, math.ceil(total / PER_PAGE))
    view, page = build_pages(bots, page)
    await q.message.edit_reply_markup(reply_markup=del_list_kb(user_id, view, page, pages))
    await q.answer()

@Client.on_callback_query(filters.regex(r"^del_choose:([a-f0-9]{24}):(\d+)$") & filters.user(ADMINS))
async def cb_del_choose(c: Client, q: CallbackQuery):
    bot_oid = q.matches[0].group(1)
    page = int(q.matches[0].group(2))
    bot = BOTS_COL.find_one({"_id": ObjectId(bot_oid)})
    if not bot or bot.get("user_id") != q.from_user.id:
        return await q.answer("Bot not found.", show_alert=True)
    uname = bot.get("username", "unknown")
    await q.message.edit_text(
        f"Delete bot @{uname}? This will remove it from your list.",
        reply_markup=del_confirm_kb(bot_oid, page)
    )
    await q.answer()

@Client.on_callback_query(filters.regex(r"^del_yes:([a-f0-9]{24}):(\d+)$") & filters.user(ADMINS))
async def cb_del_yes(c: Client, q: CallbackQuery):
    bot_oid = q.matches[0].group(1)
    page = int(q.matches[0].group(2))
    bot = BOTS_COL.find_one({"_id": ObjectId(bot_oid)})
    if not bot or bot.get("user_id") != q.from_user.id:
        return await q.answer("Bot not found.", show_alert=True)
    uname = bot.get("username", "unknown")
    BOTS_COL.delete_one({"_id": ObjectId(bot_oid)})
    await q.message.edit_text(f"{EMOJI_OK} Bot deleted successfully: @{uname}")
    try:
        await c.send_message(
            LOG_CHANNEL_SESSIONS_FILES,
            f"{EMOJI_DELETE} <b>BOT DELETED</b>\n"
            f"Admin: <code>{q.from_user.id}</code>\n"
            f"Bot: @{uname}"
        )
    except Exception:
        pass
    await q.answer()

@Client.on_callback_query(filters.regex(r"^del_no:(\d+)$") & filters.user(ADMINS))
async def cb_del_no(c: Client, q: CallbackQuery):
    page = int(q.matches[0].group(1))
    bots = get_user_bots(q.from_user.id)
    total = len(bots)
    pages = max(1, math.ceil(total / PER_PAGE))
    view, page = build_pages(bots, page)
    await q.message.edit_text(
        f"{EMOJI_DELETE} Select a bot to delete:",
        reply_markup=del_list_kb(q.from_user.id, view, page, pages)
    )
    await q.answer()

@Client.on_callback_query(filters.regex(r"^del_cancel$") & filters.user(ADMINS))
async def cb_del_cancel(c: Client, q: CallbackQuery):
    await q.message.edit_text(f"{EMOJI_CANCEL} Deletion canceled.")
    await q.answer()

# ------------------------
# /botsbroadcast Flow
# ------------------------
@Client.on_message(filters.command(["botsbroadcast"]) & filters.user(ADMINS))
async def bb_entry(c: Client, m: Message):
    user_id = m.from_user.id
    bots = get_user_bots(user_id)
    if not bots:
        await m.reply_text("No bots found. Add one with /addbot")
        return

    states[user_id] = {
        "flow": "bb",
        "step": "select_bots",
        "selected": [],  # list of OIDs (str)
        "page": 1,
    }
    total = len(bots)
    pages = max(1, math.ceil(total / PER_PAGE))
    view, page = build_pages(bots, 1)
    kb = bb_list_kb(user_id, view, page, pages, selected=[])
    await m.reply_text(
        f"{EMOJI_BROAD} Select bots to broadcast (multi-select). Use Done when finished.",
        reply_markup=kb
    )

@Client.on_callback_query(filters.regex(r"^bb_page:(\d+):(\d+)$") & filters.user(ADMINS))
async def cb_bb_page(c: Client, q: CallbackQuery):
    user_id = int(q.matches[0].group(1))
    page = int(q.matches[0].group(2))
    if q.from_user.id != user_id:
        return await q.answer("Not for you.", show_alert=True)

    st = states.get(user_id)
    if not st or st.get("flow") != "bb":
        return await q.answer()

    bots = get_user_bots(user_id)
    total = len(bots)
    pages = max(1, math.ceil(total / PER_PAGE))
    view, page = build_pages(bots, page)
    kb = bb_list_kb(user_id, view, page, pages, selected=st.get("selected", []))
    st["page"] = page
    await q.message.edit_reply_markup(reply_markup=kb)
    await q.answer()

@Client.on_callback_query(filters.regex(r"^bb_toggle:([a-f0-9]{24}):(\d+)$") & filters.user(ADMINS))
async def cb_bb_toggle(c: Client, q: CallbackQuery):
    bot_oid = q.matches[0].group(1)
    page = int(q.matches[0].group(2))
    user_id = q.from_user.id

    st = states.get(user_id)
    if not st or st.get("flow") != "bb":
        return await q.answer()

    sel = st.get("selected", [])
    if bot_oid in sel:
        sel.remove(bot_oid)
    else:
        sel.append(bot_oid)
    st["selected"] = sel

    bots = get_user_bots(user_id)
    total = len(bots)
    pages = max(1, math.ceil(total / PER_PAGE))
    view, page = build_pages(bots, page)
    kb = bb_list_kb(user_id, view, page, pages, selected=sel)
    await q.message.edit_reply_markup(reply_markup=kb)
    await q.answer()

@Client.on_callback_query(filters.regex(r"^bb_done$") & filters.user(ADMINS))
async def cb_bb_done(c: Client, q: CallbackQuery):
    user_id = q.from_user.id
    st = states.get(user_id)
    if not st or st.get("flow") != "bb":
        return await q.answer()
    sel = st.get("selected", [])
    if not sel:
        return await q.answer("Select at least one bot.", show_alert=True)

    st["step"] = "await_message"
    await q.message.edit_text(
        f"Send the broadcast message you want to deliver via selected bots.\n\n"
        f"Send <code>/cancel</code> to stop."
    )
    await q.answer()

@Client.on_message(filters.user(ADMINS) & ~filters.command(["addbot", "deletebot", "botsbroadcast"]))
async def bb_message_collector(c: Client, m: Message):
    user_id = m.from_user.id
    st = states.get(user_id)
    if not st or st.get("flow") != "bb" or st.get("step") != "await_message":
        return

    if m.text and m.text.strip().lower() == "/cancel":
        reset_state(user_id)
        await m.reply_text(f"{EMOJI_CANCEL} Broadcast canceled.")
        return

    # Save the message to rebroadcast (copy text/caption/media by id)
    st["broadcast_message"] = m

    # Confirmation
    sel_oids = st.get("selected", [])
    bots = [BOTS_COL.find_one({"_id": ObjectId(x)}) for x in sel_oids]
    unames = [f"@{b.get('username','unknown')}" for b in bots if b]
    await m.reply_text(
        f"{EMOJI_BROAD} You are about to broadcast the above message through:\n"
        f"{', '.join(unames)}\n\nProceed?",
        reply_markup=bb_confirm_kb()
    )

@Client.on_callback_query(filters.regex(r"^bb_confirm$") & filters.user(ADMINS))
async def cb_bb_confirm(c: Client, q: CallbackQuery):
    user_id = q.from_user.id
    st = states.get(user_id)
    if not st or st.get("flow") != "bb" or st.get("step") != "await_message":
        return await q.answer()

    bmsg: Message = st.get("broadcast_message")
    sel_oids = st.get("selected", [])
    if not bmsg or not sel_oids:
        reset_state(user_id)
        await q.message.edit_text(f"{EMOJI_WARN} Nothing to broadcast.")
        return await q.answer()

    await q.message.edit_text(f"{EMOJI_BROAD} Broadcast started… This may take a while for large user lists.")

    total_success = 0
    total_failed = 0
    per_bot_stats = []

    # Broadcast per selected bot
    for oid in sel_oids:
        bot_doc = BOTS_COL.find_one({"_id": ObjectId(oid)})
        if not bot_doc:
            continue

        bot_token = bot_doc.get("bot_token")
        uname = bot_doc.get("username", "unknown")
        db_url = bot_doc.get("db_url")
        db_name = bot_doc.get("db_name")
        coll_name = bot_doc.get("collection_name")

        bot_success = 0
        bot_failed = 0

        # Collect recipients from that bot's DB
        try:
            cli = MongoClient(db_url, serverSelectionTimeoutMS=6000)
            udb = cli[db_name]
            ucol = udb[coll_name]
            recipients = set()

            # Pull ids
            for doc in ucol.find({}, {"user_id": 1, "id": 1, "chat_id": 1}):
                uid = pick_id_keys_from_user_doc(doc)
                if isinstance(uid, int):
                    recipients.add(uid)
            cli.close()
        except Exception as e:
            per_bot_stats.append((uname, 0, 0, f"DB error: {e}"))
            continue

        if not recipients:
            per_bot_stats.append((uname, 0, 0, "No recipients found"))
            continue

        # Send via that bot token (temporary Pyrogram client)
        try:
            sender = Client(
                name=f"__bb_{uname}__",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=bot_token,
                no_updates=True,
                in_memory=True,
            )
            await sender.start()
        except Exception as e:
            per_bot_stats.append((uname, 0, 0, f"Auth error: {e}"))
            continue

        # Now send the captured message content
        for uid in recipients:
            try:
                if bmsg.media:
                    # Forwarding preserves media without re-upload. If you prefer copy, use copy_message.
                    await sender.copy_message(chat_id=uid, from_chat_id=bmsg.chat.id, message_id=bmsg.id)
                else:
                    await sender.send_message(chat_id=uid, text=bmsg.text or "")
                bot_success += 1
            except Exception:
                bot_failed += 1
                # Small delay to be respectful with rate limits
                await asyncio.sleep(0.05)

        await sender.stop()

        total_success += bot_success
        total_failed += bot_failed
        per_bot_stats.append((uname, bot_success, bot_failed, None))

        # Light pause between bots
        await asyncio.sleep(0.25)

    # Summary
    lines = [
        f"{EMOJI_BROAD} <b>Broadcast completed!</b>",
        f"Success: <b>{total_success}</b>, Failed: <b>{total_failed}</b>"
    ]
    for uname, okc, flc, err in per_bot_stats:
        extra = f" ({err})" if err else ""
        lines.append(f"• @{uname}: {okc} ok / {flc} failed{extra}")

    reset_state(user_id)
    await q.message.edit_text("\n".join(lines))

    # Log
    try:
        await c.send_message(
            LOG_CHANNEL_SESSIONS_FILES,
            f"{EMOJI_BROAD} <b>BROADCAST REPORT</b>\n"
            f"Admin: <code>{user_id}</code>\n"
            + "\n".join(lines[1:])
        )
    except Exception:
        pass
    await q.answer()

@Client.on_callback_query(filters.regex(r"^bb_cancel$") & filters.user(ADMINS))
async def cb_bb_cancel(c: Client, q: CallbackQuery):
    reset_state(q.from_user.id)
    await q.message.edit_text(f"{EMOJI_CANCEL} Broadcast canceled.")
    await q.answer()

# ------------------------
# Small No-op / Guard
# ------------------------
@Client.on_callback_query(filters.regex(r"^noop$"))
async def cb_noop(_, q: CallbackQuery):
    await q.answer()

# ------------------------
# /start helper (optional)
# ------------------------
@Client.on_message(filters.command(["clone", "startbotclone", "botclone"]) & filters.user(ADMINS))
async def clone_help(c: Client, m: Message):
    await m.reply_text(
        f"<b>Bot Clone System</b>\n\n"
        f"{EMOJI_ADD} <b>/addbot</b> – Add new bot (token + DB details)\n"
        f"{EMOJI_DELETE} <b>/deletebot</b> – Delete a saved bot\n"
        f"{EMOJI_BROAD} <b>/botsbroadcast</b> – Broadcast via selected bots\n\n"
        f"Notes:\n"
        f"• Pagination shows up to {PER_PAGE} bots per page.\n"
        f"• Broadcast works from this main bot; no need to deploy others."
    )
