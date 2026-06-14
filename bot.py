import os
import time
import logging
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from moderator import check_content_policy

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# L object ko yahan rakha hai
L = instaloader.Instaloader(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    sleep=True
)

def get_session_path(username):
    return os.path.join(SESSION_DIR, f"{username}.session")

def load_session():
    if os.path.exists("last_user.txt"):
        with open("last_user.txt", "r") as f:
            username = f.read().strip()
        path = get_session_path(username)
        if os.path.exists(path):
            try:
                L.load_session_from_file(username, path)
                return True
            except:
                return False
    return False

# Session Load on Startup
load_session()

# States
WAITING_USER, WAITING_PASS, WAITING_CODE = 1, 2, 3

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = WAITING_USER
    await update.message.reply_text("👤 Enter Instagram Username:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    text = update.message.text.strip()

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
            await update.message.reply_text("✅ Logged in & Session Saved!")
        except instaloader.TwoFactorAuthRequiredException:
            context.user_data['state'] = WAITING_CODE
            await update.message.reply_text("🔐 2FA Code required:")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
        return

    if state == WAITING_CODE:
        try:
            L.two_factor_login(text)
            L.save_session_to_file(get_session_path(context.user_data['insta_user']))
            context.user_data['state'] = None
            await update.message.reply_text("✅ Verified!")
        except Exception as e:
            await update.message.reply_text(f"❌ 2FA Error: {e}")
        return

    # Scan Logic (Original)
    username = text.replace("@", "").split('/')[0]
    status_msg = await update.message.reply_text(f"🔍 Fetching @{username}...")
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        info_text = f"👤 *Profile:* @{username}\n📈 *Followers:* {profile.followers}\n🖼️ *Posts:* {profile.mediacount}"
        keyboard = [[InlineKeyboardButton("✅ Confirm & Scan", callback_data=f'scan_{username}')]]
        await status_msg.edit_text(info_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('scan_'):
        username = query.data.split('_')[1]
        await query.edit_message_text(f"⚡ *Scanning {username}...* Please wait.")
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            violations, max_chance = [], 0
            
            # Aapka original violation loop
            for i, post in enumerate(profile.get_posts()):
                if i >= 10: break
                check = check_content_policy(post.caption or "")
                if not check.get("is_safe", True):
                    max_chance = max(max_chance, check.get("top_risks", [{}])[0].get('chance', 0))
                    violations.extend(check.get("suggested_reports", []))
                time.sleep(1.5) # Delay taaki block na ho

            context.user_data['v'], context.user_data['c'] = list(set(violations)), max_chance
            res = f"📊 *Results for @{username}*\n🚫 Violations: {len(violations)}\n💀 Risk: {max_chance}%\n\n👉 Get prompt below."
            keyboard = [[InlineKeyboardButton("🤖 Get Takedown Prompt", callback_data=f'prompt_{username}')]]
            await query.edit_message_text(res, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Scan Error: {e}")

    elif query.data.startswith('prompt_'):
        username = query.data.split('_')[1]
        v = ", ".join(context.user_data.get('v', ['Spam']))
        prompt = f"💀 *TAKEDOWN PROMPT*\n\n`Account @{username} violates safety: {v}. Match: {context.user_data.get('c', 0)}%.`"
        await query.message.reply_text(prompt, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('login', login_start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
        
