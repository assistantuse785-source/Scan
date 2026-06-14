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
# Pro Setup: Custom User Agent to bypass blocks
L = instaloader.Instaloader(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
is_logged_in = False

# States
WAITING_USER, WAITING_PASS, WAITING_CODE = 1, 2, 3

def extract_username(text):
    """Robust username extraction from any Instagram URL."""
    text = text.strip()
    # Pattern for various Instagram URL styles
    patterns = [
        r"instagram\.com/([^/?#& ]+)",
        r"instagram\.com/reels/([^/?#& ]+)",
        r"instagram\.com/p/([^/?#& ]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match: return match.group(1)
    return text.replace("@", "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Connected" if is_logged_in else "❌ Not Connected"
    keyboard = [[InlineKeyboardButton("🔐 Login to Instagram", callback_data='start_login')],
                [InlineKeyboardButton("📊 Check Status", callback_data='check_status')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🚀 *INSTAGRAM TRACKER PRO (FIXED)* 🚀\n\n"
        f"📡 *Status:* {status}\n\n"
        "👉 *If login is successful, just send the Profile Link or Username to scan!*",
        reply_markup=reply_markup, parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'start_login':
        context.user_data['state'] = WAITING_USER
        await query.edit_message_text("👤 *Step 1:* Send your Instagram **Username**.")
    elif query.data == 'check_status':
        status = "✅ Connected" if is_logged_in else "❌ Not Connected"
        await query.edit_message_text(f"📡 *Current Status:* {status}")

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

    # --- SCAN LOGIC ---
    username = extract_username(text)
    scan_msg = await update.message.reply_text(f"⚡ *DEEP SCANNING @{username}...*", parse_mode="Markdown")

    try:
        # Verify session before scanning
        if is_logged_in:
            try: L.test_login()
            except: is_logged_in = False
        
        profile = instaloader.Profile.from_username(L.context, username)
        
        if profile.is_private:
            await scan_msg.edit_text(f"🔒 *Error:* Account `@{username}` is **Private**.")
            return

        report = [f"👑 *DOSSIER:* @{username}", f"━━━━━━━━━━━━━━━━━━━━", f"📈 Followers: {profile.followers:,}\n"]
        violations, max_chance = [], 0
        
        for i, post in enumerate(profile.get_posts()):
            if i >= 10: break
            check = check_content_policy(post.caption)
            if not check["is_safe"]:
                max_chance = max(max_chance, check["top_risks"][0]['chance'])
                violations.extend(check["suggested_reports"])
                report.append(f"🚫 *Post {i+1}:* {check['top_risks'][0]['category']} ({check['top_risks'][0]['chance']}%)")
            time.sleep(1) # Small delay to avoid rate limit

        violations = list(set(violations)) if violations else ["Spam / Guidelines"]
        report.append(f"\n💀 *OVERALL RISK:* {max_chance}%")
        report.append(f"\n🤖 *AI TAKEDOWN PROMPT:* \n`[CRITICAL] Account @{username} violating safety protocols: {', '.join(violations)}. Termination required.`")
        
        await scan_msg.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await scan_msg.edit_text(f"❌ *Scan Failed:* {str(e)}\n\n*Solution:* Re-login using `/start` or check if the username is correct.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
        
