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
L = instaloader.Instaloader(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1")
is_logged_in = False

# States for Login Flow
WAITING_USER, WAITING_PASS, WAITING_CODE = 1, 2, 3

def extract_username(text):
    """Robust username extraction."""
    text = text.strip().rstrip('/')
    if "instagram.com" in text:
        parts = [p for p in text.split('/') if p]
        return parts[-1].split('?')[0]
    return text.replace("@", "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Connected" if is_logged_in else "❌ Not Connected"
    keyboard = [[InlineKeyboardButton("🔐 Login to Instagram", callback_data='start_login')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🔥 *ULTIMATE INSTAGRAM TRACKER (FINAL)* 🔥\n\n"
        f"📡 *Status:* {status}\n\n"
        "👉 *Send any Profile Link or Username to start!*",
        reply_markup=reply_markup, parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_logged_in
    state = context.user_data.get('state')
    text = update.message.text.strip()

    # --- ORIGINAL WORKING LOGIN LOGIC ---
    if state == WAITING_USER:
        context.user_data['insta_user'] = text
        context.user_data['state'] = WAITING_PASS
        await update.message.reply_text(f"🔑 Enter **Password** for `@{text}`.")
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
            await status_msg.edit_text("⚠️ *Checkpoint:* Open Instagram App, click 'This was me', then try again.")
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

    # --- STEP 1: FETCH BASIC DETAILS (STABLE FLOW) ---
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
        await status_msg.edit_text(f"❌ *Error:* {str(e)}\nMake sure you are logged in using `/start`.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'start_login':
        context.user_data['state'] = WAITING_USER
        await query.edit_message_text("👤 Enter Instagram **Username**.")
        return

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
                time.sleep(1) # Delay for stability

            context.user_data['violations'] = list(set(violations)) if violations else ["Spam"]
            context.user_data['max_chance'] = max_chance
            
            report = (
                f"📊 *Scan Results for @{username}*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🚫 *Violations Found:* {len(context.user_data['violations'])}\n"
                f"💀 *Highest Risk:* {max_chance}%\n\n"
                f"👉 *Click below to generate the Full Takedown Prompt.*"
            )
            keyboard = [[InlineKeyboardButton("🤖 Generate Full Prompt", callback_data=f'prompt_{username}')]]
            await query.edit_message_text(report, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ *Scan Error:* {str(e)}")

    elif query.data.startswith('prompt_'):
        username = query.data.replace('prompt_', '')
        v = ", ".join(context.user_data.get('violations', ['Spam']))
        chance = context.user_data.get('max_chance', 0)
        prompt = (
            f"💀 *ULTIMATE TAKEDOWN PROMPT* 💀\n\n"
            f"Copy and paste this in 'Something Else' report box:\n\n"
            f"`[CRITICAL AUDIT] Account @{username} is violating Meta's community standards regarding {v}. AI Confidence: {chance}%. Immediate termination required.`"
        )
        await query.message.reply_text(prompt, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
