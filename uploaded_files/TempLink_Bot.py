import telebot
import time
import uuid
import sqlite3
from telebot import types

# ---------------- CONFIG ----------------
TOKEN = "8244218581:AAE0FnkA2Osj_UyDuaCNXoQw-Yu7rTNrClM"   # Replace with your bot token
OWNER_ID = 7977515080       # Replace with your Telegram ID
bot = telebot.TeleBot(TOKEN)

# ---------------- DATABASE ----------------
DB_NAME = "tempbot.db"

def setup_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
    cur.execute("CREATE TABLE IF NOT EXISTS force_channels (chat_link TEXT PRIMARY KEY)")
    cur.execute("CREATE TABLE IF NOT EXISTS master_links (code TEXT PRIMARY KEY, url TEXT)")
    conn.commit()
    conn.close()
    add_admin(OWNER_ID)

def add_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def remove_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_admins():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM admins")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows

def add_force_channel(link):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO force_channels (chat_link) VALUES (?)", (link,))
    conn.commit()
    conn.close()

def remove_force_channel(link):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM force_channels WHERE chat_link = ?", (link,))
    conn.commit()
    conn.close()

def get_force_channels():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT chat_link FROM force_channels")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows

def add_master_link(code, url):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO master_links (code, url) VALUES (?, ?)", (code, url))
    conn.commit()
    conn.close()

def get_master_link(code):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT url FROM master_links WHERE code = ?", (code,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

# ---------------- HELPERS ----------------
def is_admin(user_id):
    return user_id in get_admins()

def is_subscribed(user_id):
    try:
        for ch_link in get_force_channels():
            username = ch_link.split("/")[-1]
            member = bot.get_chat_member(username, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        return True
    except:
        return False

# ---------------- STORAGE ----------------
personal_codes = {}

# ---------------- COMMANDS ----------------
@bot.message_handler(commands=["start"])
def handle_start(message):
    parts = message.text.split()
    user_id = message.from_user.id

    if len(parts) == 2:  # user clicked master link
        code = parts[1]
        url = get_master_link(code)
        if url:
            if is_subscribed(user_id):
                pcode = str(uuid.uuid4())[:8]
                personal_codes[pcode] = {"url": url, "expire": time.time() + 20, "user": user_id}
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("⚡ Tap to Unlock (20s)", callback_data=f"unlock:{pcode}"))
                bot.send_message(
                    message.chat.id,
                    "✅ *You are subscribed!* 🎉\n\nClick below to unlock your **personal temporary link**.",
                    parse_mode="Markdown",
                    reply_markup=markup
                )
            else:
                markup = types.InlineKeyboardMarkup()
                for link in get_force_channels():
                    markup.add(types.InlineKeyboardButton("📌 Join Channel", url=link))
                markup.add(types.InlineKeyboardButton("🔄 Try Again", callback_data=f"tryagain:{code}"))
                bot.send_message(
                    message.chat.id,
                    "⚠️ *You must join all required channels first!*\n\nJoin the channels below and then tap *Try Again*.",
                    parse_mode="Markdown",
                    reply_markup=markup
                )
        else:
            bot.send_message(message.chat.id, "❌ *Invalid or expired master link.*", parse_mode="Markdown")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📌 Request Master Link", url=f"https://t.me/{bot.get_me().username}?start=request"))
        bot.send_message(
            message.chat.id,
            "👋 *Welcome to Temp Link Bot!* 🎉\n\n"
            "This bot generates *temporary personal links* for users.\n\n"
            "1️⃣ Join all required channels.\n"
            "2️⃣ Ask the admin to generate a master link for you.\n\n"
            "💡 Click the button below to request access from admin!",
            parse_mode="Markdown",
            reply_markup=markup
        )

# ---------------- CALLBACK HANDLERS ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("unlock:"))
def unlock_link(call):
    user_id = call.from_user.id
    pcode = call.data.split(":")[1]
    if pcode in personal_codes:
        data = personal_codes[pcode]
        if data["user"] != user_id:
            bot.answer_callback_query(call.id, "❌ Not your link!", show_alert=True)
            return
        if time.time() > data["expire"]:
            bot.answer_callback_query(call.id, "⏰ Link expired!", show_alert=True)
            return
        bot.answer_callback_query(call.id, "✅ Link unlocked!", show_alert=True)
        bot.send_message(
            user_id, 
            f"🎉 *Here is your temporary link:* 🔗\n\n{data['url']}",
            parse_mode="Markdown"
        )
        del personal_codes[pcode]
    else:
        bot.answer_callback_query(call.id, "❌ Invalid or expired link.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("tryagain:"))
def tryagain_link(call):
    user_id = call.from_user.id
    code = call.data.split(":")[1]
    url = get_master_link(code)

    if not url:
        bot.answer_callback_query(call.id, "❌ Invalid or expired master link.", show_alert=True)
        return

    if is_subscribed(user_id):
        pcode = str(uuid.uuid4())[:8]
        personal_codes[pcode] = {"url": url, "expire": time.time() + 20, "user": user_id}
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⚡ Tap to Unlock (20s)", callback_data=f"unlock:{pcode}"))
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ *You are now subscribed!* 🎉\n\nClick below to unlock your **personal temporary link**.",
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        bot.answer_callback_query(call.id, "⚠️ You still need to join all channels.", show_alert=True)

# ---------------- ADMIN COMMANDS ----------------
@bot.message_handler(commands=["addadmin"])
def cmd_addadmin(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "❌ Only owner can add admins.")
    try:
        uid = int(message.text.split()[1])
        add_admin(uid)
        bot.reply_to(message, f"✅ Added admin: `{uid}`", parse_mode="Markdown")
    except:
        bot.reply_to(message, "Usage: /addadmin <user_id>")

@bot.message_handler(commands=["removeadmin"])
def cmd_removeadmin(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "❌ Only owner can remove admins.")
    try:
        uid = int(message.text.split()[1])
        remove_admin(uid)
        bot.reply_to(message, f"✅ Removed admin: `{uid}`", parse_mode="Markdown")
    except:
        bot.reply_to(message, "Usage: /removeadmin <user_id>")

@bot.message_handler(commands=["addforce"])
def cmd_addforce(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ Admins only.")
    try:
        link = message.text.split()[1]  # full channel link
        add_force_channel(link)
        bot.reply_to(message, f"✅ Added force-sub link: {link}")
    except:
        bot.reply_to(message, "Usage: /addforce <channel_link>")

@bot.message_handler(commands=["removeforce"])
def cmd_removeforce(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ Admins only.")
    try:
        link = message.text.split()[1]
        remove_force_channel(link)
        bot.reply_to(message, f"✅ Removed force-sub link: {link}")
    except:
        bot.reply_to(message, "Usage: /removeforce <channel_link>")

@bot.message_handler(commands=["help"])
def cmd_help(message):
    user_id = message.from_user.id
    text = "📖 *Bot Commands Help*\n\n"

    # User commands
    text += "👤 *User Commands:*\n"
    text += "/start - Start the bot and see instructions\n"
    text += "/help - Show this help message\n\n"

    # Admin commands
    if is_admin(user_id):
        text += "⚙ *Admin Commands:*\n"
        text += "/addadmin <user_id> - Add a new admin\n"
        text += "/removeadmin <user_id> - Remove an admin\n"
        text += "/addforce <channel_link> - Add a force-sub channel\n"
        text += "/removeforce <channel_link> - Remove a force-sub channel\n"
        text += "/newlink <URL> - Generate a new master link\n"
        text += "/status - Show admins and force-sub links\n"

    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["newlink"])
def cmd_newlink(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ Admins only.")

    args = message.text.split(None, 1)
    if len(args) < 2:
        return bot.reply_to(message, "Usage: /newlink <URL>")

    url = args[1].strip()
    if not url.startswith("http"):
        return bot.reply_to(message, "❌ Invalid URL! Must start with http or https.")

    code = str(uuid.uuid4())[:8]
    add_master_link(code, url)
    bot_username = bot.get_me().username
    share_url = f"https://t.me/{bot_username}?start={code}"

    # Escape Markdown special characters (for MarkdownV2)
    safe_text = (
        f"✅ Master link generated successfully!\n\n"
        f"🔗 {share_url}\n\n"
        "Users clicking this link will receive a personal 20s temp link."
    )

    bot.reply_to(message, safe_text)
    
# ---------------- RUN ----------------
setup_db()
print("🚀 Bot is running...")
bot.polling()