import os
import instaloader
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from moderator import check_content_policy

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
L = instaloader.Instaloader()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! Instagram username bhejo scan karne ke liye.")

async def scan_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip().replace("@", "")
    await update.message.reply_text(f"🔍 Scanning @{username}... Sabhi posts check ho rahe hain.")
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        report = [f"📋 *Report for @{username}*", f"👤 Followers: {profile.followers}", f"👤 Total Posts: {profile.mediacount}\n"]
        
        violations_found = 0
        for i, post in enumerate(profile.get_posts()):
            check = check_content_policy(post.caption)
            if not check["is_safe"]:
                violations_found += 1
                report.append(f"🚫 *Post {i+1} Flagged:* {', '.join(check['violations'])}")
                report.append(f"🔗 Link: https://instagram.com/p/{post.shortcode}")
                report.append(f"📢 Report as: {', '.join(set(check['suggested_reports']))}\n")
        
        if violations_found == 0: report.append("✅ Sab sahi hai, koi violation nahi mili.")
        else: report.append(f"🚨 Total {violations_found} violations milin. Account khatre mein hai!")
        
        await update.message.reply_text("\n".join(report), parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Error! Account private ho sakta hai ya Instagram ne block kiya hai.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), scan_account))
    app.run_polling()
  
