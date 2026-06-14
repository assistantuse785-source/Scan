import os
import re
import logging
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from moderator import check_content_policy

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
L = instaloader.Instaloader()
is_logged_in = False

# Login States
WAITING_USER, WAITING_PASS, WAITING_CODE = 1, 2, 3

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Connected" if is_logged_in else "❌ Not Connected"
    keyboard = [
        [InlineKeyboardButton("🔐 Login to Instagram", callback_data='start_login')],
        [InlineKeyboardButton("📊 Check Status", callback_data='check_status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔥 *ULTIMATE INSTAGRAM TRACKER (PRO)* 🔥\n\n"
        f"📡 *Status:* {status}\n\n"
        "I provide deep violation analysis and ban strategies.\n\n"
        "👉 *Click below to login or send a link to scan!*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'start_login':
        context.user_data['state'] = WAITING_USER
        await query.edit_message_text("👤 *Step 1:* Please send your Instagram **Username**.")
    
    elif query.data == 'check_status':
        status = "✅ Connected" if is_logged_in else "❌ Not Connected"
        await query.edit_message_text(f"📡 *Current Status:* {status}\n\nUse `/start` to return to menu.")

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
        status_msg = await update.message.reply_text("📡 *Attempting login...*")
        try:
            L.login(insta_user, text)
            is_logged_in = True
            context.user_data['state'] = None
            await status_msg.edit_text(f"✅ *Success!* Bot connected as `@{insta_user}`.")
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            context.user_data['state'] = WAITING_CODE
            await status_msg.edit_text("🔐 *2FA Required:* Instagram sent a code to your phone/email.\n\n👉 *Please enter the 6-digit code:*")
        except Exception as e:
            await status_msg.edit_text(f"❌ *Failed:* {str(e)}")
            context.user_data['state'] = None
        return

    if state == WAITING_CODE:
        status_msg = await update.message.reply_text("📡 *Verifying Code...*")
        try:
            L.two_factor_login(text)
            is_logged_in = True
            context.user_data['state'] = None
            await status_msg.edit_text("✅ *OTP Verified!* Connection Established.")
        except Exception as e:
            await status_msg.edit_text(f"❌ *Code Failed:* {str(e)}")
        return

    # Scan Logic
    username = text.split('/')[-1].split('?')[0].replace("@", "")
    scan_msg = await update.message.reply_text(f"⚡ *SCANNING @{username}...*", parse_mode="Markdown")

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

        violations = list(set(violations)) if violations else ["Spam / Guidelines"]
        report.append(f"📊 AI Risk Score: {max_chance}%")
        report.append(f"\n📱 *METHOD 1: MASS REPORT*\n• Category: {violations[0]}")
        report.append(f"\n🤖 *METHOD 2: AI TAKEDOWN PROMPT*\n`[CRITICAL] Account @{username} violating safety protocols: {', '.join(violations)}. Match: {max_chance}%. Termination required.`")
        
        await scan_msg.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await scan_msg.edit_text(f"❌ *Scan Failed:* {str(e)}\n\n*Tip:* Use `/start` to login first.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
    
