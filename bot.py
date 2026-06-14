import os, asyncio, gc, instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from moderator import check_content_policy

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

L = instaloader.Instaloader(
    save_metadata=False, compress_json=False, sleep=True,
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# LOGIN LOAD HO RHA HAI YA NAHI?
def load_session():
    for filename in os.listdir(SESSION_DIR):
        if filename.endswith(".session"):
            username = filename.replace(".session", "")
            L.load_session_from_file(username, filename=os.path.join(SESSION_DIR, filename))
            return True
    return False

# HANDLER
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Log session status
    has_session = load_session()
    
    raw_text = update.message.text.strip()
    # URL Cleaning
    if "instagram.com" in raw_text:
        parts = [p for p in raw_text.split('/') if p]
        username = parts[-2] if "?" in parts[-1] else parts[-1]
    else:
        username = raw_text.replace("@", "").replace(" ", "")
        
    context.user_data['username'] = username
    
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        res = (f"👤 *Profile Details*\n🆔 @{profile.username}\n📛 Name: {profile.full_name}\n"
               f"📈 Followers: {profile.followers:,}\n🖼 Total Posts: {profile.mediacount}\n"
               f"✅ Verified: {'Yes' if profile.is_verified else 'No'}\n"
               f"📝 Bio: {profile.biography[:50]}...\n"
               f"🔑 Session Active: {has_session}")
        
        kb = [[InlineKeyboardButton("🛡️ Start Full Deep Scan", callback_data='start_scan')]]
        await update.message.reply_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}\n\n*Solution:* Ensure session file is in /sessions folder.")

# ... (baaki scan/prompt functions wahi purane wale hain)
