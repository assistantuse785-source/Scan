import os
import re
import logging
import instaloader
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from moderator import check_content_policy

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SESSION_DIR = "sessions"
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

L = instaloader.Instaloader(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1")
is_logged_in = False

# --- SESSION HANDLING (FIXED) ---
def get_session_path(username):
    return os.path.join(SESSION_DIR, f"session_{username}")

def save_session(username):
    L.save_session_to_file(get_session_path(username))
    with open("last_user.txt", "w") as f:
        f.write(username)

def load_session():
    global is_logged_in
    if os.path.exists("last_user.txt"):
        try:
            with open("last_user.txt", "r") as f:
                username = f.read().strip()
            session_path = get_session_path(username)
            if os.path.exists(session_path):
                L.load_session_from_file(username, session_path)
                L.test_login()
                is_logged_in = True
                return True
        except Exception as e:
            logging.error(f"Session load failed: {e}")
            is_logged_in = False
    return False

# Load session on startup
load_session()

# States
WAITING_USER, WAITING_PASS, WAITING_CODE = 1, 2, 3

def extract_username(text):
    text = text.strip().rstrip('/')
    if "instagram.com" in text:
        parts = [p for p in text.split('/') if p]
        return parts[-1].split('?')[0]
    return text.replace("@", "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    load_session()
    status = "✅ Connected (Session Saved)" if is_logged_in else "❌ Not Connected"
    await update.message.reply_text(
        f"🔥 *ULTIMATE INSTAGRAM TRACKER (GOD MODE)* 🔥\n\n"
        f"📡 *Status:* {status}\n\n"
        "👉 *Instructions:* \n"
        "1. If 'Not Connected', use `/login` once.\n"
        "2. After that, just send any Link/Username to scan.\n"
        "3. I will stay logged in even if I restart!",
        parse_mode="Markdown"
    )

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = WAITING_USER
    await update.message.reply_text("👤 *Step 1:* Enter Instagram **Username**.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_logged_in
    state = context.user_data.get('state')
    text = update.message.text.strip()

    if state == WAITING_USER:
        context.user_data['insta_user'] = text
        context.user_data['state'] = WAITING_PASS
        await update.message.reply_text(f"🔑 *Step 2:* Enter **Password** for `@{text}`.")
        return

    if state == WAITING_PASS:
        insta_user = context.user_data['insta_user']
        status_msg = await update.message.reply_text("📡 *Logging in...*")
        try:
            L.login(insta_user, text)
            save_session(insta_user)
            is_logged_in = True
            context.user_data['state'] = None
            await status_msg.edit_text(f"✅ *Success!* Session saved. You won't need to login again.")
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            context.user_data['state'] = WAITING_CODE
            await status_msg.edit_text("🔐 *OTP Required:* Enter the 6-digit code.")
        except Exception as e:
            await status_msg.edit_text(f"❌ *Failed:* {str(e)}")
            context.user_data['state'] = None
        return

    if state == WAITING_CODE:
        insta_user = context.user_data['insta_user']
        try:
            L.two_factor_login(text)
            save_session(insta_user)
            is_logged_in, context.user_data['state'] = True, None
            await update.message.reply_text("✅ *OTP Verified & Session Saved!*")
        except Exception as e:
            await update.message.reply_text(f"❌ *Error:* {str(e)}")
        return

    # --- SCAN LOGIC ---
    username = extract_username(text)
    if not username: return
    if not is_logged_in: load_session()
    
    status_msg = await update.message.reply_text(f"🔍 Fetching details for @{username}...")
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        info_text = (
            f"👤 *Profile:* @{username}\n"
            f"📈 *Followers:* {profile.followers:,}\n"
            f"🖼️ *Total Posts:* {profile.mediacount}\n\n"
            f"👉 *Confirm this account to start scanning.*"
        )
        keyboard = [[InlineKeyboardButton("✅ Confirm & Scan", callback_data=f'scan_{username}')]]
        await status_msg.edit_text(info_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        await status_msg.edit_text(f"❌ *Error:* {str(e)}\n\n*Tip:* Use `/login` if your session expired.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('scan_'):
        username = query.data.replace('scan_', '')
        await query.edit_message_text(f"⚡ *Scanning @{username}...*", parse_mode="Markdown")
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            violations, max_chance = [], 0
            for i, post in enumerate(profile.get_posts()):
                if i >= 10: break
                check = check_content_policy(post.caption)
                if not check["is_safe"]:
                    max_chance = max(max_chance, check["top_risks"][0]['chance'])
                    violations.extend(check["suggested_reports"])
                time.sleep(1)

            context.user_data['v'], context.user_data['c'] = list(set(violations)) if violations else ["Spam"], max_chance
            res = (f"📊 *Results for @{username}*\n"
                   f"━━━━━━━━━━━━━━━━━━━━\n"
                   f"🚫 Violations: {len(context.user_data['v'])}\n"
                   f"💀 Risk: {max_chance}%\n\n"
                   f"👉 Click below for the Takedown Prompt.")
            keyboard = [[InlineKeyboardButton("🤖 Get Takedown Prompt", callback_data=f'prompt_{username}')]]
            await query.edit_message_text(res, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ *Scan Error:* {str(e)}")

    elif query.data.startswith('prompt_'):
        username = query.data.replace('prompt_', '')
        v, c = ", ".join(context.user_data.get('v', ['Spam'])), context.user_data.get('c', 0)
        prompt = (f"💀 *ULTIMATE TAKEDOWN PROMPT*\n\n"
                  f"`[CRITICAL] Account @{username} violates safety protocols: {v}. Match: {c}%. Termination required.`")
        await query.message.reply_text(prompt, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('login', login_start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
        
