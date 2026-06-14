import os
import logging
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# Advanced Browser-like configuration
L = instaloader.Instaloader(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    sleep=True, # Automatically adds random delays to prevent blocks
)

def get_session_path(username):
    return os.path.join(SESSION_DIR, f"{username}.session")

# --- LOGIN & SESSION HANDLER ---
async def login_logic(username, password, code=None):
    try:
        if code:
            L.two_factor_login(code)
        else:
            L.login(username, password)
        
        L.save_session_to_file(get_session_path(username))
        with open("last_user.txt", "w") as f: f.write(username)
        return "✅ Login Success!"
    except instaloader.exceptions.ConnectionException:
        return "❌ Connection lost. Try again."
    except instaloader.exceptions.BadCredentialsException:
        return "❌ Wrong Username/Password."
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        return "2FA_REQUIRED"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# --- SCANNING DATA FUNCTION ---
async def get_profile_data(username):
    # Session load karo pehle
    if os.path.exists("last_user.txt"):
        with open("last_user.txt", "r") as f:
            last_user = f.read().strip()
            if os.path.exists(get_session_path(last_user)):
                L.load_session_from_file(last_user, get_session_path(last_user))
    
    profile = instaloader.Profile.from_username(L.context, username)
    
    # Data extraction
    data = {
        "username": profile.username,
        "full_name": profile.full_name,
        "followers": profile.followers,
        "following": profile.followees,
        "posts": profile.mediacount,
        "is_private": profile.is_private,
        "bio": profile.biography
    }
    return data

# --- TELEGRAM HANDLERS (Simplified for Stability) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Bot is Online.\nSend any Instagram Username to fetch details.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Simple check: If it's a login attempt
    if text.startswith("/login"):
        await update.message.reply_text("Format: /login username password")
        return

    # Data Fetching
    try:
        await update.message.reply_text("🔍 Fetching...")
        data = await get_profile_data(text)
        res = (f"👤 *Profile:* {data['username']}\n"
               f"📛 *Name:* {data['full_name']}\n"
               f"📈 *Followers:* {data['followers']}\n"
               f"🖼️ *Posts:* {data['posts']}\n"
               f"🔐 *Private:* {'Yes' if data['is_private'] else 'No'}")
        await update.message.reply_text(res, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Could not fetch. Check if logged in or account exists.\nError: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
    
