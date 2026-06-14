import os, time, asyncio, gc, instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from moderator import check_content_policy

# 1. Config & Setup
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

L = instaloader.Instaloader(
    save_metadata=False, compress_json=False, sleep=True,
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 2. Utilities
async def show_cooldown(msg, action):
    for i in range(3, 0, -1):
        await msg.edit_text(f"⏳ {action} in {i} seconds...")
        await asyncio.sleep(1)

def get_risk_score(profile, violations_count):
    score = 10 + (violations_count * 15)
    if profile.followers < 100: score += 20
    if not profile.is_verified: score += 10
    return min(score, 99)

# 3. Message Handler (A-to-Z Data)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.split('/')[-2] if "instagram.com" in update.message.text else update.message.text.replace("@", "").strip()
    context.user_data['username'] = username
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        context.user_data['userid'] = profile.userid
        res = (f"👤 *A-Z Profile Forensics*\n🆔 @{profile.username}\n📛 Name: {profile.full_name}\n"
               f"📈 Followers: {profile.followers:,} | Following: {profile.followees:,}\n"
               f"🖼 Total Posts: {profile.mediacount} | Verified: {'Yes' if profile.is_verified else 'No'}\n"
               f"🏢 Category: {profile.business_category_name or 'N/A'}\n"
               f"🌐 URL: {profile.external_url or 'N/A'}\n"
               f"📝 Bio: {profile.biography[:80]}...")
        
        kb = [[InlineKeyboardButton("🛡️ Initiate Full Deep Scan", callback_data='start_scan')]]
        await update.message.reply_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# 4. Deep Scan Engine
async def start_deep_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_cooldown(query.message, "Starting Deep Forensic Scan")
    
    profile = instaloader.Profile.from_username(L.context, context.user_data['username'])
    violations, count = [], 0
    msg = await query.edit_message_text("📡 Analyzing content...")
    
    for post in profile.get_posts():
        count += 1
        res = check_content_policy(post.caption or "")
        if not res.get("is_safe", True): violations.extend(res.get("suggested_reports", []))
        if count % 10 == 0:
            await msg.edit_text(f"📡 Scanning: {count} posts checked...")
            await asyncio.sleep(1)
            gc.collect()
            
    context.user_data['risks'] = list(set(violations))
    context.user_data['risk_pct'] = get_risk_score(profile, len(violations))
    
    res = f"✅ *Scan Complete!*\n📊 Risk Level: {context.user_data['risk_pct']}%\n⚠️ Issues: {len(context.user_data['risks'])}"
    kb = [[InlineKeyboardButton("💀 Generate Takedown Prompt", callback_data='prompt')]]
    await msg.edit_message_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# 5. Prompt Handler
async def generate_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_cooldown(query.message, "Compiling Google-Style Report")
    
    user = context.user_data['username']
    risks = ", ".join(context.user_data.get('risks', ['Community Guidelines Violation']))
    
    prompt = (f"🌐 *OFFICIAL TAKEDOWN REQUEST*\n\nTo Meta Safety Team,\n\n"
              f"I am reporting @{user} (ID: {context.user_data['userid']}) "
              f"for violating terms. Risks: {risks}.\n\n"
              f"Please terminate this account immediately.\n\nRegards,\nSafety Monitor Bot.")
    
    await query.edit_message_text(prompt, parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CallbackQueryHandler(start_deep_scan, pattern='start_scan'))
    app.add_handler(CallbackQueryHandler(generate_prompt, pattern='prompt'))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
    
