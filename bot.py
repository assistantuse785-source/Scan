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

def extract_username(text):
    """Extracts username from Instagram URL or plain text."""
    url_pattern = r"(?:https?://)?(?:www\.)?instagram\.com/([^/?#&]+)"
    match = re.search(url_pattern, text)
    if match:
        return match.group(1)
    return text.strip().replace("@", "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 *Instagram Policy Tracker Bot* 🚀\n\n"
        "I scan accounts for illegal content and suspension risks.\n\n"
        "✅ *Supported:* Profile URLs or Usernames\n"
        "📊 *Results:* Top 3 Risks, Violation Chances, and Reporting Guides.\n\n"
        "👉 *Send a link or username now!*",
        parse_mode="Markdown"
    )

async def scan_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    input_text = update.message.text
    username = extract_username(input_text)
    
    status_msg = await update.message.reply_text(f"📡 *Fetching @{username}...*\nAnalyzing profile and posts for high-risk violations.", parse_mode="Markdown")

    try:
        profile = instaloader.Profile.from_username(L.context, username)
        
        if profile.is_private:
            await status_msg.edit_text(f"🔒 *Error:* Account `@{username}` is **Private**.\nScanning is only possible for Public accounts.")
            return

        report = [
            f"👤 *Profile:* @{username}",
            f"📈 *Followers:* {profile.followers:,}",
            f"🖼️ *Total Posts:* {profile.mediacount}\n",
            f"🔥 *High-Risk Violation Analysis:*",
            f"━━━━━━━━━━━━━━━━━━━━"
        ]
        
        violations_found = 0
        all_suggested_reports = set()
        
        posts = profile.get_posts()
        for i, post in enumerate(posts):
            if i >= 20: break # Scan latest 20 posts for performance
            
            check = check_content_policy(post.caption)
            if not check["is_safe"]:
                violations_found += 1
                report.append(f"\n🚫 *Post {i+1} Violation:*")
                for risk in check["top_risks"]:
                    report.append(f"  ⚡ {risk['category']}: {risk['chance']}%")
                
                report.append(f"🔗 [Post Link](https://instagram.com/p/{post.shortcode})")
                if check["suggested_reports"]:
                    all_suggested_reports.update(check["suggested_reports"])

        if violations_found == 0:
            report.append("\n✅ *Account looks safe.* No major policy violations detected.")
        else:
            report.append(f"\n🚨 *Summary:* {violations_found} high-risk posts found.")
            report.append(f"🛠️ *Best Reporting Categories:*")
            for r in all_suggested_reports:
                report.append(f"  ✅ {r}")
            report.append("\n⚠️ *Verdict:* High probability of suspension if reported correctly.")

        await status_msg.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)

    except instaloader.exceptions.ProfileNotExistsException:
        await status_msg.edit_text(f"❌ *Error:* Profile `@{username}` not found.")
    except Exception as e:
        await status_msg.edit_text(f"❌ *Error:* Unable to fetch data. Try again later.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), scan_account))
    app.run_polling()
            
