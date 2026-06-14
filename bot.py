import os
import re
import logging
import instaloader
import asyncio
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
    if INSTA_USER and INSTA_PASS:
        try:
            L.login(INSTA_USER, INSTA_PASS)
            is_logged_in = True
            return "✅ Connected"
        except: 
            is_logged_in = False
            return "❌ Login Failed"
    return "⚠️ No Credentials"

login_insta()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💀 *ULTIMATE TAKEDOWN SYSTEM ONLINE* 💀\n\n"
        "Send me an Instagram Link/Username to start.\n\n"
        "🛠 *Commands:* \n"
        "/test - Check Connection\n"
        "/start - Menu",
        parse_mode="Markdown"
    )

async def test_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = login_insta()
    await update.message.reply_text(f"📡 *Status:* {res}", parse_mode="Markdown")

async def scan_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    input_text = update.message.text
    username = input_text.strip().split('/')[-1].split('?')[0].replace("@", "")
    status_msg = await update.message.reply_text(f"🚀 *SCANNING @{username}...*", parse_mode="Markdown")

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

        violations = list(set(violations)) if violations else ["Spam / Community Standards"]

        report = [
            f"👑 *DOSSIER:* @{username}",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"📊 AI Risk: {max_chance}%",
            f"\n📱 *METHOD 1: NORMAL APP*",
            f"• Category: {violations[0]}",
            f"• Repeat: 20 Times",
            f"\n🌐 *METHOD 2: CHROME BYPASS*",
            f"1. Open Chrome Incognito.",
            f"2. Go to `instagram.com/{username}`",
            f"3. Report -> Something else.",
            f"\n🤖 *METHOD 3: GOOGLE AI PROMPT*",
            f"Paste this in 'Something Else' box:",
            f"`[CRITICAL] Account @{username} violates safety protocols: {', '.join(violations)}. Content match: {max_chance}%. Termination required.`"
        ]
        await status_msg.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as e:
        await status_msg.edit_text(f"❌ *Scan Failed!* \n\nReason: {str(e)}", parse_mode="Markdown")

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        print("❌ CRITICAL ERROR: TELEGRAM_TOKEN is missing!")
    else:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
            app.add_handler(CommandHandler('start', start))
            app.add_handler(CommandHandler('test', test_connection))
            app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), scan_account))
            print("🚀 Bot is starting...")
            app.run_polling()
        except Exception as e:
            print(f"❌ BOT CRASHED: {e}")
            
