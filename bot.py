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
L = instaloader.Instaloader()
is_logged_in = False

# States
WAITING_USER, WAITING_PASS, WAITING_CODE = 1, 2, 3

def extract_username(text):
    text = text.strip().rstrip('/')
    if "instagram.com" in text:
        parts = [p for p in text.split('/') if p]
        return parts[-1].split('?')[0]
    return text.replace("@", "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Connected" if is_logged_in else "❌ Not Connected"
    await update.message.reply_text(
        f"🔥 *ULTIMATE INSTAGRAM TRACKER (FINAL)* 🔥\n\n"
        f"📡 *Status:* {status}\n\n"
        "🛠 *Commands:* \n"
        "/login - Connect your account\n"
        "/start - Show Menu\n\n"
        "👉 *After login, just send any Username/Link to scan.*",
        parse_mode="Markdown"
    )

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = WAITING_USER
    await update.message.reply_text("👤 *Step 1:* Enter your Instagram **Username**.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_logged_in
    state = context.user_data.get('state')
    text = update.message.text.strip()

    # --- SIMPLE LOGIN LOGIC (BACK TO BASICS) ---
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
            is_logged_in = True
            context.user_data['state'] = None
            await status_msg.edit_text(f"✅ *Success!* Connected as `@{insta_user}`.")
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            context.user_data['state'] = WAITING_CODE
            await status_msg.edit_text("🔐 *OTP Required:* Enter the 6-digit code sent to your phone.")
        except instaloader.exceptions.CheckpointException:
            await status_msg.edit_text("⚠️ *Checkpoint:* Open Instagram App, click 'This was me', then try `/login` again.")
            context.user_data['state'] = None
        except Exception as e:
            await status_msg.edit_text(f"❌ *Failed:* {str(e)}")
            context.user_data['state'] = None
        return

    if state == WAITING_CODE:
        status_msg = await update.message.reply_text("📡 *Verifying Code...*")
        try:
            L.two_factor_login(text)
            is_logged_in, context.user_data['state'] = True, None
            await status_msg.edit_text("✅ *OTP Verified!* Connection Established.")
        except Exception as e:
            await status_msg.edit_text(f"❌ *Error:* {str(e)}")
        return

    # --- STEP-BY-STEP SCAN FLOW (OP MODE) ---
    username = extract_username(text)
    if not username: return
    
    status_msg = await update.message.reply_text(f"🔍 Fetching details for @{username}...")
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        info_text = (
            f"👤 *Profile:* @{username}\n"
            f"📈 *Followers:* {profile.followers:,}\n"
            f"👥 *Following:* {profile.followees:,}\n"
            f"🖼️ *Total Posts:* {profile.mediacount}\n\n"
            f"👉 *Confirm this account to start deep scanning.*"
        )
        keyboard = [[InlineKeyboardButton("✅ Confirm & Scan Posts", callback_data=f'scan_{username}')]]
        await status_msg.edit_text(info_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        await status_msg.edit_text(f"❌ *Error:* {str(e)}\n\n*Tip:* Use `/login` first.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('scan_'):
        username = query.data.replace('scan_', '')
        await query.edit_message_text(f"⚡ *Scanning posts for @{username}...*", parse_mode="Markdown")
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
            res = (f"📊 *Scan Results for @{username}*\n"
                   f"━━━━━━━━━━━━━━━━━━━━\n"
                   f"🚫 Violations Found: {len(context.user_data['v'])}\n"
                   f"💀 Highest Risk: {max_chance}%\n\n"
                   f"👉 Click below to generate the Full Takedown Prompt.")
            keyboard = [[InlineKeyboardButton("🤖 Generate Full Prompt", callback_data=f'prompt_{username}')]]
            await query.edit_message_text(res, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ *Scan Error:* {str(e)}")

    elif query.data.startswith('prompt_'):
        username = query.data.replace('prompt_', '')
        v, c = ", ".join(context.user_data.get('v', ['Spam'])), context.user_data.get('c', 0)
        prompt = (f"💀 *ULTIMATE TAKEDOWN PROMPT*\n\n"
                  f"Paste in 'Something Else' box:\n\n"
                  f"`[CRITICAL] Account @{username} violating safety protocols: {v}. Match: {c}%. Immediate termination required.`")
        await query.message.reply_text(prompt, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('login', login_start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
                                                    
