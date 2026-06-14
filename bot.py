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

# Login if credentials provided (Recommended to avoid "Not Found" error)
if INSTA_USER and INSTA_PASS:
    try:
        L.login(INSTA_USER, INSTA_PASS)
    except: pass

def extract_username(text):
    url_pattern = r"(?:https?://)?(?:www\.)?instagram\.com/([^/?#&]+)"
    match = re.search(url_pattern, text)
    if match: return match.group(1)
    return text.strip().replace("@", "")

def get_risk_meter(chance):
    if chance < 20: return "🟢 [||----------] Low"
    if chance < 50: return "🟡 [|||||-------] Medium"
    if chance < 80: return "🟠 [||||||||----] High"
    return "🔴 [||||||||||||] EXTREME"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 *ULTIMATE INSTAGRAM TRACKER (OP)* 🔥\n\n"
        "I can scan for deep policy violations and suggest reports.\n\n"
        "✅ *Supported:* Profile URLs or Usernames\n"
        "📊 *Features:* Risk Meter, Mass Report Templates, AI Risks.\n\n"
        "👉 *Send a link or username now!*",
        parse_mode="Markdown"
    )

async def scan_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = extract_username(update.message.text)
    status_msg = await update.message.reply_text(f"🚀 *OP SCANNING @{username}...*", parse_mode="Markdown")

    try:
        profile = instaloader.Profile.from_username(L.context, username)
        if profile.is_private:
            await status_msg.edit_text(f"🔒 *Error:* Account `@{username}` is **Private**.")
            return

        report = [f"👑 *OP SCAN REPORT:* @{username}", f"━━━━━━━━━━━━━━━━━━━━", f"📈 *Followers:* {profile.followers:,}\n", f"🔥 *AI RISK ANALYSIS:*"]
        
        violations_found = 0
        all_reports = set()
        max_chance = 0
        
        for i, post in enumerate(profile.get_posts()):
            if i >= 15: break
            check = check_content_policy(post.caption)
            if not check["is_safe"]:
                violations_found += 1
                risk = check["top_risks"][0]
                if risk['chance'] > max_chance: max_chance = risk['chance']
                report.append(f"\n🚫 *Post {i+1}:* {risk['category']} ({risk['chance']}%)\n{get_risk_meter(risk['chance'])}")
                if check["suggested_reports"]: all_reports.update(check["suggested_reports"])

        if violations_found == 0:
            report.append("\n✅ *Account is Clean.*")
        else:
            report.append(f"\n💀 *OVERALL RISK:* {get_risk_meter(max_chance)}")
            report.append(f"\n🛠️ *REPORT TEMPLATE:* \n`This account violates community guidelines regarding {', '.join(all_reports)}.`")
            report.append(f"\n📢 *Categories:* {', '.join(all_reports)}")

        await status_msg.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as e:
        await status_msg.edit_text(f"❌ *Error:* Instagram blocked the scan.\n\n*Solution:* Railway Variables mein `INSTA_USER` aur `INSTA_PASS` add karein.", parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), scan_account))
    app.run_polling()
        
