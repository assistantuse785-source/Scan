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
    if INSTA_USER and INSTA_PASS:
        try:
            L.login(INSTA_USER, INSTA_PASS)
            is_logged_in = True
            return "✅ Login Successful"
        except Exception as e:
            is_logged_in = False
            return f"❌ Login Failed: {str(e)}"
    return "⚠️ No Credentials Found"

login_insta()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💀 *ULTIMATE INSTAGRAM TAKEDOWN SYSTEM* 💀\n\n"
        "Send me a Username or Link to get the full report and ban methods.\n\n"
        "🛠 *Commands:* \n"
        "/test - Check Instagram Connection\n"
        "/start - Show this menu\n\n"
        "👉 *Send Link Now!*",
        parse_mode="Markdown"
    )

async def test_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = login_insta()
    await update.message.reply_text(f"📡 *Connection Status:* \n{res}", parse_mode="Markdown")

async def scan_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    input_text = update.message.text
    username = input_text.strip().split('/')[-1].split('?')[0].replace("@", "")
    status_msg = await update.message.reply_text(f"🚀 *OP SCANNING @{username}...*", parse_mode="Markdown")

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
            f"👑 *TAKEDOWN DOSSIER:* @{username}",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"📈 Followers: {profile.followers:,}",
            f"📊 AI Risk Score: {max_chance}%",
            f"\n📱 *METHOD 1: NORMAL APP REPORT*",
            f"• Category: {violations[0]}",
            f"• Frequency: 15x - 20x Times",
            f"\n🌐 *METHOD 2: CHROME BYPASS (OP)*",
            f"1. Open Chrome Incognito Mode.",
            f"2. Go to `instagram.com/{username}`",
            f"3. Click 3 dots -> Report -> Something else.",
            f"4. Paste the AI Prompt below.",
            f"\n🤖 *METHOD 3: GOOGLE AI PROMPT*",
            f"Copy this in 'Something Else' box:",
            f"`[CRITICAL] Account @{username} is flagged for multiple safety violations including {', '.join(violations)}. Content analysis shows a high match with illegal activities. Immediate suspension required.`"
        ]
        
        await status_msg.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "login" in error_msg.lower():
            hint = "Login Required! Check INSTA_USER/PASS in Railway."
        elif "404" in error_msg:
            hint = "Account not found or Username wrong."
        else:
            hint = "Instagram blocked the request. Try again in 10 mins."
        
        await status_msg.edit_text(f"❌ *Scan Failed!*\n\n*Reason:* {error_msg}\n*Solution:* {hint}", parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('test', test_connection))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), scan_account))
    app.run_polling()
