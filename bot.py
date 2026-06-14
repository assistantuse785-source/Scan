import os
import re
import logging
import instaloader
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from moderator import check_content_policy

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# Using a very common User-Agent to look like a real phone
L = instaloader.Instaloader(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1")
is_logged_in = False

def extract_username(text):
    """
    Super Robust Username Extraction.
    Handles:
    - https://instagram.com/user.name/
    - https://www.instagram.com/user_name?igsh=...
    - @user.name
    - user_name
    """
    text = text.strip()
    # Remove trailing slashes and spaces
    text = text.rstrip('/')
    
    # If it's a URL
    if "instagram.com" in text:
        # Split by / and take the last part that isn't empty
        parts = [p for p in text.split('/') if p]
        last_part = parts[-1]
        # Remove query parameters like ?igsh=...
        username = last_part.split('?')[0]
        return username
    
    # If it's a simple username or @username
    return text.replace("@", "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Connected" if is_logged_in else "❌ Not Connected"
    await update.message.reply_text(
        f"🔥 *ULTIMATE TRACKER: FIXED EDITION* 🔥\n\n"
        f"📡 *Status:* {status}\n\n"
        "👉 *Instructions:* \n"
        "1. Use `/login` if not connected.\n"
        "2. Send any Profile Link or Username.\n"
        "3. I now support usernames with `.` and `_` perfectly.",
        parse_mode="Markdown"
    )

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 1 # WAITING_USER
    await update.message.reply_text("👤 *Step 1:* Enter your Instagram **Username**.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_logged_in
    state = context.user_data.get('state')
    text = update.message.text.strip()

    # --- LOGIN LOGIC ---
    if state == 1: # WAITING_USER
        context.user_data['insta_user'] = text
        context.user_data['state'] = 2 # WAITING_PASS
        await update.message.reply_text(f"🔑 *Step 2:* Enter **Password** for `@{text}`.")
        return

    if state == 2: # WAITING_PASS
        insta_user = context.user_data['insta_user']
        status_msg = await update.message.reply_text("📡 *Logging in...*")
        try:
            L.login(insta_user, text)
            is_logged_in = True
            context.user_data['state'] = None
            await status_msg.edit_text(f"✅ *Success!* Connected as `@{insta_user}`.")
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            context.user_data['state'] = 3 # WAITING_CODE
            await status_msg.edit_text("🔐 *OTP Required:* Enter the 6-digit code.")
        except Exception as e:
            await status_msg.edit_text(f"❌ *Failed:* {str(e)}")
            context.user_data['state'] = None
        return

    if state == 3: # WAITING_CODE
        try:
            L.two_factor_login(text)
            is_logged_in, context.user_data['state'] = True, None
            await update.message.reply_text("✅ *OTP Verified!*")
        except Exception as e:
            await update.message.reply_text(f"❌ *Error:* {str(e)}")
        return

    # --- SCAN LOGIC (The Fixed Part) ---
    username = extract_username(text)
    if not username:
        await update.message.reply_text("❌ Please send a valid Username or Link.")
        return

    scan_msg = await update.message.reply_text(f"⚡ *SCANNING @{username}...*", parse_mode="Markdown")

    try:
        # Check if session is still alive
        if is_logged_in:
            try:
                L.test_login()
            except:
                is_logged_in = False
                await scan_msg.edit_text("⚠️ *Session Expired!* Please `/login` again.")
                return

        # Fetch profile
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
            time.sleep(1) # Human-like delay

        violations = list(set(violations)) if violations else ["Spam / Guidelines"]
        report.append(f"\n💀 *OVERALL RISK:* {max_chance}%")
        report.append(f"\n📝 *TAKEDOWN PROMPT:* \n`[CRITICAL] Account @{username} violating safety protocols: {', '.join(violations)}. Termination required.`")
        
        await scan_msg.edit_text("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)
        
    except Exception as e:
        await scan_msg.edit_text(f"❌ *Scan Failed:* {str(e)}\n\n*Possible Reason:* Instagram is blocking the request or the username `{username}` is incorrect.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('login', login_start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
    
