import os
import re
import logging
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from moderator import check_content_policy

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
L = instaloader.Instaloader(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1")
is_logged_in = False

# States
WAITING_USER, WAITING_PASS, WAITING_CODE = 1, 2, 3

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Connected" if is_logged_in else "❌ Not Connected"
    keyboard = [[InlineKeyboardButton("🔐 Start Pro Login", callback_data='start_login')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"💀 *ULTIMATE BYPASS SYSTEM* 💀\n\n"
        f"📡 *Status:* {status}\n\n"
        "👉 *Click the button to login. If you get a 'Checkpoint' error, I will tell you how to fix it!*",
        reply_markup=reply_markup, parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'start_login':
        context.user_data['state'] = WAITING_USER
        await query.edit_message_text("👤 *Step 1:* Enter Instagram **Username**.")

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
        status_msg = await update.message.reply_text("📡 *Bypassing security...*")
        try:
            L.login(insta_user, text)
            is_logged_in, context.user_data['state'] = True, None
            await status_msg.edit_text(f"✅ *Success!* Connected as `@{insta_user}`.")
        except instaloader.exceptions.CheckpointException:
            await status_msg.edit_text(
                "⚠️ *CHECKPOINT ERROR!* ⚠️\n\n"
                "Instagram is blocking the server. Follow these steps to fix it:\n\n"
                "1️⃣ Open Instagram App on your phone.\n"
                "2️⃣ Look for a notification: *'Was this you?'*\n"
                "3️⃣ Click **'This was me'** or **'Allow'**.\n"
                "4️⃣ Now, come back here and try `/login` again.\n\n"
                "*Note:* If it still fails, login to `instagram.com` on your phone browser first.",
                parse_mode="Markdown"
            )
            context.user_data['state'] = None
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            context.user_data['state'] = WAITING_CODE
            await status_msg.edit_text("🔐 *OTP Required:* Enter the 6-digit code.")
        except Exception as e:
            await status_msg.edit_text(f"❌ *Failed:* {str(e)}")
            context.user_data['state'] = None
        return

    if state == WAITING_CODE:
        try:
            L.two_factor_login(text)
            is_logged_in, context.user_data['state'] = True, None
            await update.message.reply_text("✅ *OTP Verified!*")
        except Exception as e:
            await update.message.reply_text(f"❌ *Error:* {str(e)}")
        return

    # Scan Logic
    username = text.split('/')[-1].split('?')[0].replace("@", "")
    scan_msg = await update.message.reply_text(f"⚡ *SCANNING @{username}...*")
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        report = [f"👑 *DOSSIER:* @{username}", f"━━━━━━━━━━━━━━━━━━━━"]
        violations, max_chance = [], 0
        for i, post in enumerate(profile.get_posts()):
            if i >= 10: break
            check = check_content_policy(post.caption)
            if not check["is_safe"]:
                max_chance = max(max_chance, check["top_risks"][0]['chance'])
                violations.extend(check["suggested_reports"])
        
        violations = list(set(violations)) if violations else ["Spam"]
        report.append(f"📊 AI Risk: {max_chance}%")
        report.append(f"\n📝 *TAKEDOWN PROMPT:* \n`[CRITICAL] Account @{username} violating protocols: {', '.join(violations)}. Termination required.`")
        await scan_msg.edit_text("\n".join(report), parse_mode="Markdown")
    except Exception as e:
        await scan_msg.edit_text(f"❌ *Scan Failed:* {str(e)}\nUse `/start` to login first.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
    
