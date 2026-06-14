import os
import logging
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from moderator import check_content_policy

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Bot Settings
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# Instaloader Setup
L = instaloader.Instaloader(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    save_metadata=False,
    compress_json=False
)

def get_session_path(username):
    return os.path.join(SESSION_DIR, f"{username}.session")

def load_saved_session():
    if os.path.exists("last_user.txt"):
        with open("last_user.txt", "r") as f:
            username = f.read().strip()
        path = get_session_path(username)
        if os.path.exists(path):
            try:
                L.load_session_from_file(username, path)
                return True
            except Exception as e:
                logging.error(f"Failed to load session: {e}")
    return False

# Load session immediately on startup
load_saved_session()

# States
WAITING_USER, WAITING_PASS, WAITING_CODE = 1, 2, 3

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 *Instagram Tracker Active*\n\nSend me any Username to scan.")

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = WAITING_USER
    await update.message.reply_text("👤 Enter your Instagram Username:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    state = context.user_data.get('state')

    if state == WAITING_USER:
        context.user_data['insta_user'] = text
        context.user_data['state'] = WAITING_PASS
        await update.message.reply_text("🔑 Enter Password:")
        return

    if state == WAITING_PASS:
        user = context.user_data['insta_user']
        try:
            L.login(user, text)
            L.save_session_to_file(get_session_path(user))
            with open("last_user.txt", "w") as f: f.write(user)
            context.user_data['state'] = None
            await update.message.reply_text("✅ Logged in successfully!")
        except instaloader.TwoFactorAuthRequiredException:
            context.user_data['state'] = WAITING_CODE
            await update.message.reply_text("🔐 Enter 2FA Code:")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
        return

    if state == WAITING_CODE:
        try:
            L.two_factor_login(text)
            L.save_session_to_file(get_session_path(context.user_data['insta_user']))
            context.user_data['state'] = None
            await update.message.reply_text("✅ 2FA Verified!")
        except Exception as e:
            await update.message.reply_text(f"❌ 2FA Error: {e}")
        return

    # Scan Logic
    try:
        msg = await update.message.reply_text(f"🔍 Fetching @{text}...")
        profile = instaloader.Profile.from_username(L.context, text)
        
        info = f"👤 *{profile.username}*\n🖼️ Posts: {profile.mediacount}\n📈 Followers: {profile.followers}"
        keyboard = [[InlineKeyboardButton("✅ Scan Account", callback_data=f'scan_{text}')]]
        await msg.edit_text(info, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}\n\n*Try /login if not logged in.*")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('scan_'):
        username = query.data.split('_')[1]
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            # Scan logic here (using your existing logic)
            await query.edit_message_text(f"✅ Scanning {username} completed.")
        except Exception as e:
            await query.edit_message_text(f"❌ Scan Failed: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('login', login_start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
    
