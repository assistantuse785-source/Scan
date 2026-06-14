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
L = instaloader.Instaloader(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1")
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
    keyboard = [[InlineKeyboardButton("🔐 Login / Re-connect", callback_data='start_login')]]
    await update.message.reply_text(
        f"🔥 *ULTIMATE INSTAGRAM TRACKER (OP)* 🔥\n\n"
        f"📡 *Status:* {status}\n\n"
        "👉 *Instructions:* \n"
        "1. Login first to enable scanning.\n"
        "2. Send any Profile Link or Username.\n"
        "3. Confirm and generate Takedown Prompts.",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_logged_in
    state = context.user_data.get('state')
    text = update.message.text.strip()

    if state == WAITING_USER:
        context.user_data['insta_user'] = text
        context.user_data['state'] = WAITING_PASS
        await update.message.reply_text(f"🔑 Enter **Password** for `@{text}`.")
        return

    if state == WAITING_PASS:
        context.user_data['insta_pass'] = text
        await attempt_login(update, context, context.user_data['insta_user'], text)
        return

    if state == WAITING_CODE:
        status_msg = await update.message.reply_text("📡 Verifying OTP...")
        try:
            L.two_factor_login(text)
            is_logged_in, context.user_data['state'] = True, None
            await status_msg.edit_text("✅ *OTP Verified!* Bot is now Online.")
        except Exception as e:
            await status_msg.edit_text(f"❌ *OTP Error:* {str(e)}")
        return

    # --- STEP 1: BASIC INFO (FAST) ---
    username = extract_username(text)
    if not username: return
    status_msg = await update.message.reply_text(f"🔍 Fetching @{username}...")
    try:
        # We can fetch basic info even without full login sometimes, or use the session
        profile = instaloader.Profile.from_username(L.context, username)
        info = (f"👤 *Profile:* @{username}\n"
                f"📈 *Followers:* {profile.followers:,}\n"
                f"👥 *Following:* {profile.followees:,}\n"
                f"🖼️ *Posts:* {profile.mediacount}\n\n"
                f"👉 *Confirm to start AI Policy Scan.*")
        keyboard = [[InlineKeyboardButton("✅ Confirm & Scan", callback_data=f'scan_{username}')]]
        await status_msg.edit_text(info, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        await status_msg.edit_text(f"❌ *Error:* {str(e)}\nTry `/start` to login first.")

async def attempt_login(update, context, user, pw):
    global is_logged_in
    status_msg = await update.message.reply_text("📡 *Logging in...*")
    try:
        L.login(user, pw)
        is_logged_in, context.user_data['state'] = True, None
        await status_msg.edit_text(f"✅ *Success!* Connected as `@{user}`.")
    except instaloader.exceptions.CheckpointException:
        keyboard = [[InlineKeyboardButton("🔄 Retry After Approval", callback_data='retry_login')]]
        await status_msg.edit_text(
            "⚠️ *Checkpoint Required!*\n\n"
            "1. Open Instagram App on your phone.\n"
            "2. Click **'This was me'** on the notification.\n"
            "3. After clicking, press the button below.",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        context.user_data['state'] = WAITING_CODE
        await status_msg.edit_text("🔐 *OTP Required:* Enter the 6-digit code.")
    except Exception as e:
        await status_msg.edit_text(f"❌ *Failed:* {str(e)}")
        context.user_data['state'] = None

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'start_login':
        context.user_data['state'] = WAITING_USER
        await query.edit_message_text("👤 Enter Instagram **Username**.")
    
    elif query.data == 'retry_login':
        user = context.user_data.get('insta_user')
        pw = context.user_data.get('insta_pass')
        if user and pw:
            await attempt_login(query, context, user, pw)
        else:
            await query.edit_message_text("❌ Session lost. Use `/start` again.")

    elif query.data.startswith('scan_'):
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
            
            context.user_data['v'], context.user_data['c'] = list(set(violations)), max_chance
            res = (f"📊 *Results for @{username}*\n"
                   f"━━━━━━━━━━━━━━━━━━━━\n"
                   f"🚫 Violations: {len(context.user_data['v'])}\n"
                   f"💀 Risk: {max_chance}%\n\n"
                   f"👉 Click below for the Takedown Prompt.")
            keyboard = [[InlineKeyboardButton("🤖 Get Takedown Prompt", callback_data=f'prompt_{username}')]]
            await query.edit_message_text(res, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Scan Error: {str(e)}")

    elif query.data.startswith('prompt_'):
        username = query.data.replace('prompt_', '')
        v = ", ".join(context.user_data.get('v', ['Spam']))
        c = context.user_data.get('c', 0)
        prompt = (f"💀 *ULTIMATE TAKEDOWN PROMPT*\n\n"
                  f"Paste in 'Something Else' box:\n\n"
                  f"`[CRITICAL] Account @{username} violates safety protocols: {v}. Match: {c}%. Immediate termination required.`")
        await query.message.reply_text(prompt, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
        
