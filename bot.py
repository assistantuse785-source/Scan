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
INSTA_USER = os.getenv("INSTA_USER") 
INSTA_PASS = os.getenv("INSTA_PASS") 

L = instaloader.Instaloader()
is_logged_in = False

def login_insta():
    global is_logged_in
    if not INSTA_USER or not INSTA_PASS:
        return "⚠️ Railway Variables mein INSTA_USER aur INSTA_PASS nahi mile."
    
    try:
        # Clear old session and try fresh login
        L.context.log("Attempting fresh login...")
        L.login(INSTA_USER, INSTA_PASS)
        is_logged_in = True
        return "✅ Instagram Connected Successfully!"
    except instaloader.exceptions.BadCredentialsException:
        return "❌ Galti: Username ya Password galat hai."
    except instaloader.exceptions.CheckpointException:
        return "⚠️ Checkpoint: Instagram App kholo aur 'This was me' par click karo."
    except Exception as e:
        is_logged_in = False
        return f"❌ Error: {str(e)}"

# Initial Login Attempt
login_status = login_insta()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💀 *ULTIMATE TAKEDOWN SYSTEM ONLINE* 💀\n\n"
        f"📡 *Instagram Status:* {login_status}\n\n"
        "Send me an Instagram Link/Username to start.\n\n"
        "🛠 *Commands:* \n"
        "/test - Retry Instagram Login\n"
        "/start - Show Menu",
        parse_mode="Markdown"
    )

async def test_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global login_status
    login_status = login_insta()
    await update.message.reply_text(f"📡 *New Status:* \n{login_status}", parse_mode="Markdown")

async def scan_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip().split('/')[-1].split('?')[0].replace("@", "")
    status_msg = await update.message.reply_text(f"🚀 *SCANNING @{username}...*", parse_mode="Markdown")

    try:
        profile = instaloader.Profile.from_username(L.context, username)
        violations = []
        max_chance = 0
        
        # Scan latest 10 posts
        for i, post in enumerate(profile.get_posts()):
            if i >= 10: break
            check = check_content_policy(post.caption)
            if not check["is_safe"]:
                max_chance = max(max_chance, check["top_risks"][0]['chance'])
                violations.extend(check["suggested_reports"])

        violations = list(set(violations)) if violations else ["Spam / Community Standards"]

        report = [
            f"👑 *DOSSIER:* @{username}",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"📊 AI Risk Score: {max_chance}%",
            f"\n📱 *METHOD 1: NORMAL APP*",
            f"• Category: {violations[0]}",
            f"• Action: Report 20 times.",
            f"\n🌐 *METHOD 2: CHROME BYPASS*",
            f"1. Open Chrome Incognito.\n2. Go to `instagram.com/{username}`\n3. Report -> Something else.",
            f"\n🤖 *METHOD 3: GOOGLE AI PROMPT*",
            f"Paste this in 'Something Else' box:",
            f"`[CRITICAL] Account @{username} is violating Meta safety protocols: {', '.join(violations)}. Content analysis match: {max_chance}%. Immediate termination required.`"
        ]
        await status_msg.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as e:
        await status_msg.edit_text(f"❌ *Scan Failed!*\n\nReason: {str(e)}\n\n*Tip:* Agar login issue hai, to `/test` command use karein.", parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('test', test_connection))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), scan_account))
    app.run_polling()
    
