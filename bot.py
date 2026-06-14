import os
import logging
import instaloader
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from moderator import check_content_policy

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
L = instaloader.Instaloader()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ *Welcome to Instagram Tracker Bot* ✨\n\n"
        "I can scan any public Instagram account for policy violations.\n\n"
        "👉 *How to use:* Just send me the Instagram username (e.g., `cristiano`)",
        parse_mode="Markdown"
    )

async def scan_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip().replace("@", "")
    status_msg = await update.message.reply_text(f"🔍 *Scanning @{username}...*\nFetching profile and posts. Please wait.", parse_mode="Markdown")

    try:
        # Load profile
        profile = instaloader.Profile.from_username(L.context, username)
        
        if profile.is_private:
            await status_msg.edit_text(f"❌ *Error:* The account `@{username}` is **Private**.\nI can only scan Public accounts.")
            return

        report = [
            f"📊 *Scan Report for @{username}*",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"👤 *Followers:* {profile.followers:,}",
            f"👥 *Following:* {profile.followees:,}",
            f"📝 *Total Posts:* {profile.mediacount}",
            f"📖 *Bio:* {profile.biography if profile.biography else 'None'}\n",
            f"🔍 *Policy Check Results:*",
        ]
        
        violations_found = 0
        flagged_details = []

        # Scan posts (limiting to latest 50 for stability, can be changed)
        posts = profile.get_posts()
        count = 0
        for post in posts:
            count += 1
            if count > 50: break # Safety limit to prevent long hangs
            
            check = check_content_policy(post.caption)
            if not check["is_safe"]:
                violations_found += 1
                flagged_details.append(f"🚫 *Post {count}:* {', '.join(check['violations']).title()}")
                flagged_details.append(f"🔗 [View Post](https://instagram.com/p/{post.shortcode})")
                if check["suggested_reports"]:
                    flagged_details.append(f"📢 *Suggested Report:* {', '.join(set(check['suggested_reports']))}\n")

        if violations_found == 0:
            report.append("✅ *Clean:* No major violations found in recent posts.")
        else:
            report.extend(flagged_details)
            report.append(f"⚠️ *Warning:* Found {violations_found} potential violations.")
            report.append("🚨 *Status:* This account is at **High Risk** of suspension.")

        await status_msg.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)

    except instaloader.exceptions.ProfileNotExistsException:
        await status_msg.edit_text(f"❌ *Error:* Profile `@{username}` does not exist.")
    except instaloader.exceptions.QueryReturnedBadRequestException:
        await status_msg.edit_text("❌ *Error:* Instagram blocked the request. Try again later.")
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ *Error:* Something went wrong. Make sure the account is public.")

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN not found!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), scan_account))
        print("Bot is running...")
        app.run_polling()
        
