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

# States for manual login
WAITING_FOR_USER = 1
WAITING_FOR_PASS = 2

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💀 *ULTIMATE TAKEDOWN SYSTEM* 💀\n\n"
        "🛠 *Commands:* \n"
        "/login - Start Manual Instagram Login\n"
        "/status - Check if bot is connected\n"
        "/start - Show Menu\n\n"
        "👉 *After login, just send any Username/Link to scan.*",
        parse_mode="Markdown"
    )

async def status_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_logged_in
    msg = "✅ *Connected to Instagram*" if is_logged_in else "❌ *Not Connected*"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = WAITING_FOR_USER
    await update.message.reply_text("👤 *Step 1:* Please send your Instagram **Username**.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_logged_in
    state = context.user_data.get('state')
    text = update.message.text.strip()

    if state == WAITING_FOR_USER:
        context.user_data['insta_user'] = text
        context.user_data['state'] = WAITING_FOR_PASS
        await update.message.reply_text(f"🔑 *Step 2:* Got it. Now send the **Password** for `@{text}`.\n\n*(Note: Delete your password message after sending for security)*")
        return

    if state == WAITING_FOR_PASS:
        insta_user = context.user_data.get('insta_user')
        insta_pass = text
        context.user_data['state'] = None # Reset state
        
        status_msg = await update.message.reply_text(f"📡 *Attempting login for @{insta_user}...*")
        
        try:
            L.login(insta_user, insta_pass)
            is_logged_in = True
            await status_msg.edit_text(f"✅ *Login Successful!* \nBot is now connected as `@{insta_user}`. You can now scan accounts.")
        except instaloader.exceptions.BadCredentialsException:
            await status_msg.edit_text("❌ *Login Failed:* Wrong Username or Password.")
        except instaloader.exceptions.CheckpointException:
            await status_msg.edit_text("⚠️ *Checkpoint:* Instagram blocked this login. \n\n*Fix:* Open Instagram App on your phone, look for 'Was this you?' and click **'This was me'**. Then try `/login` again.")
        except Exception as e:
            await status_msg.edit_text(f"❌ *Error:* {str(e)}")
        return

    # If not in login state, treat as Scan request
    username = text.split('/')[-1].split('?')[0].replace("@", "")
    scan_status = await update.message.reply_text(f"🚀 *SCANNING @{username}...*", parse_mode="Markdown")

    try:
        profile = instaloader.Profile.from_username(L.context, username)
        violations = []
        max_chance = 0
        for i, post in enumerate(profile.get_posts()):
            if i >= 10: break
            check = check_content_policy(post.caption)
            if not check["is_safe"]:
                max_chance = max(max_chance, check["top_risks"][0]['chance'])
                violations.extend(check["suggested_reports"])

        violations = list(set(violations)) if not violations else list(set(violations))
        if not violations: violations = ["Spam / Guidelines"]

        report = [
            f"👑 *DOSSIER:* @{username}",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"📊 AI Risk: {max_chance}%",
            f"\n📱 *METHOD 1: NORMAL APP*",
            f"• Category: {violations[0]}",
            f"\n🌐 *METHOD 2: CHROME BYPASS*",
            f"1. Chrome Incognito -> `instagram.com/{username}`\n2. Report -> Something else.",
            f"\n🤖 *METHOD 3: GOOGLE AI PROMPT*",
            f"`[CRITICAL] Account @{username} violating safety protocols: {', '.join(violations)}. Match: {max_chance}%. Terminate.`"
        ]
        await scan_status.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await scan_status.edit_text(f"❌ *Scan Failed:* {str(e)}\n\n*Tip:* Use `/login` to connect an account first.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('login', login_start))
    app.add_handler(CommandHandler('status', status_check))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
    
