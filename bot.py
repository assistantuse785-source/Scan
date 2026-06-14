import os
import re
import logging
import instaloader
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from moderator import check_content_policy

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
L = instaloader.Instaloader()
is_logged_in = False

# States
WAITING_USER, WAITING_PASS, WAITING_CODE = 1, 2, 3

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Connected" if is_logged_in else "❌ Not Connected"
    await update.message.reply_text(
        f"🔥 *ULTIMATE INSTAGRAM TRACKER (FIXED)* 🔥\n\n"
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

    # --- LOGIN LOGIC (Original Simple Method) ---
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

    # --- SCAN LOGIC (Fixed for 'Does Not Exist' error) ---
    username = text.split('/')[-1].split('?')[0].replace("@", "")
    scan_msg = await update.message.reply_text(f"⚡ *SCANNING @{username}...*", parse_mode="Markdown")

    try:
        # Use the logged-in context to fetch profile
        profile = instaloader.Profile.from_username(L.context, username)
        
        report = [
            f"👑 *DOSSIER:* @{username}",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"📈 Followers: {profile.followers:,}",
            f"🖼️ Total Posts: {profile.mediacount}\n",
            f"🔥 *AI RISK ANALYSIS:*",
        ]
        
        violations, max_chance = [], 0
        posts = profile.get_posts()
        for i, post in enumerate(posts):
            if i >= 10: break
            check = check_content_policy(post.caption)
            if not check["is_safe"]:
                max_chance = max(max_chance, check["top_risks"][0]['chance'])
                violations.extend(check["suggested_reports"])
                report.append(f"🚫 *Post {i+1}:* {check['top_risks'][0]['category']} ({check['top_risks'][0]['chance']}%)")

        violations = list(set(violations)) if violations else ["Spam / Guidelines"]
        report.append(f"\n💀 *OVERALL RISK:* {max_chance}%")
        report.append(f"\n📝 *TAKEDOWN PROMPT:* \n`[CRITICAL] Account @{username} violating safety protocols: {', '.join(violations)}. Termination required.`")
        
        await scan_msg.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)
        
    except Exception as e:
        await scan_msg.edit_text(f"❌ *Scan Failed:* {str(e)}\n\n*Tip:* Use `/login` again if the session expired.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('login', login_start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
        
