import os, time, asyncio, gc, instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from moderator import check_content_policy

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
L = instaloader.Instaloader(save_metadata=False, compress_json=False, sleep=True)

# --- ANIMATION UTILITY ---
async def show_cooldown(msg, action_name):
    for i in range(3, 0, -1):
        await msg.edit_text(f"⏳ {action_name} in {i} seconds...")
        await asyncio.sleep(1)

# --- DEEP SCAN ENGINE ---
async def start_deep_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await show_cooldown(query.message, "Initializing Deep Analysis")
    username = context.user_data.get('username')
    profile = instaloader.Profile.from_username(L.context, username)
    
    msg = await query.edit_message_text("📡 Commencing deep forensic scan...")
    violations, count = [], 0
    
    # Scanning loop
    for post in profile.get_posts():
        count += 1
        res = check_content_policy(post.caption or "")
        if not res.get("is_safe", True):
            violations.extend(res.get("suggested_reports", []))
        
        if count % 10 == 0:
            await msg.edit_text(f"📡 Deep Scanning... {count} posts analyzed.")
            await asyncio.sleep(1.5)
            gc.collect()

    context.user_data['risks'] = list(set(violations))
    res = f"✅ *Scan Complete!*\n📦 Total Posts Analyzed: {count}\n⚠️ Risks Found: {len(context.user_data['risks'])}"
    kb = [[InlineKeyboardButton("💀 Generate Takedown Prompt", callback_data='prompt')]]
    await msg.edit_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- DATA FETCHING (A TO Z) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    username = text.split('/')[-2] if "instagram.com" in text else text.replace("@", "")
    context.user_data['username'] = username
    
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        
        # A-Z Data Dictionary
        res = (
            f"👤 *A-Z Profile Forensics*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 *Username:* @{profile.username}\n"
            f"📛 *Full Name:* {profile.full_name}\n"
            f"👤 *User ID:* `{profile.userid}`\n"
            f"📈 *Followers:* {profile.followers:,}\n"
            f"👥 *Following:* {profile.followees:,}\n"
            f"🖼 *Total Posts:* {profile.mediacount}\n"
            f"🔐 *Private Account:* {'Yes' if profile.is_private else 'No'}\n"
            f"✅ *Verified:* {'Yes' if profile.is_verified else 'No'}\n"
            f"🏢 *Business Category:* {profile.business_category_name or 'N/A'}\n"
            f"🌐 *External URL:* {profile.external_url or 'N/A'}\n"
            f"📍 *IGTV Posts:* {profile.igtvcount}\n"
            f"🎞 *Highlights:* {profile.highlights_count}\n"
            f"📝 *Biography:* {profile.biography}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        
        kb = [[InlineKeyboardButton("🛡️ Initiate Full Deep Scan", callback_data='start_scan')]]
        await update.message.reply_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# --- PROMPT HANDLER ---
async def generate_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_cooldown(query.message, "Compiling Report")
    
    user = context.user_data.get('username')
    risks = ", ".join(context.user_data.get('risks', ['Violation of Community Standards']))
    
    prompt = (f"🌐 *OFFICIAL TAKEDOWN NOTICE*\n\n"
              f"To Meta Integrity Team,\n\n"
              f"Reporting account @{user} (ID: {context.user_data.get('userid')}) for severe policy violations.\n"
              f"Specific Risks Identified: {risks}.\n\n"
              f"Requesting immediate manual review for account termination.\n\n"
              f"Safety Monitor Bot.")
    
    await query.edit_message_text(prompt, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CallbackQueryHandler(start_deep_scan, pattern='start_scan'))
    app.add_handler(CallbackQueryHandler(generate_prompt, pattern='prompt'))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
