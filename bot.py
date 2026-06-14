import os, time, asyncio, gc, instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from moderator import check_content_policy

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
L = instaloader.Instaloader(save_metadata=False, compress_json=False, sleep=True)

# --- COOL-DOWN ANIMATION UTILITY ---
async def show_cooldown(msg, action_name):
    for i in range(3, 0, -1):
        await msg.edit_text(f"⏳ {action_name} in {i} seconds...")
        await asyncio.sleep(1)

# --- CORE SCAN ---
async def start_deep_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Cooldown step
    await show_cooldown(query.message, "Starting Deep Analysis")
    
    username = context.user_data.get('username')
    profile = instaloader.Profile.from_username(L.context, username)
    
    msg = await query.edit_text("🚀 Scanning initialized...")
    violations, count = [], 0
    
    for post in profile.get_posts():
        count += 1
        res = check_content_policy(post.caption or "")
        if not res.get("is_safe", True):
            violations.extend(res.get("suggested_reports", []))
        
        if count % 10 == 0:
            await msg.edit_text(f"📡 Processing: {count} posts scanned...")
            await asyncio.sleep(1.5)
            gc.collect()

    context.user_data['risks'] = list(set(violations))
    res = f"✅ *Analysis Complete*\n📦 Total: {count}\n⚠️ Risks Found: {len(context.user_data['risks'])}"
    kb = [[InlineKeyboardButton("💀 Generate Takedown Prompt", callback_data='prompt')]]
    await msg.edit_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- PROMPT HANDLER ---
async def generate_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_cooldown(query.message, "Generating Google-style Report")
    
    risks = ", ".join(context.user_data.get('risks', ['Inappropriate Content']))
    user = context.user_data.get('username')
    
    prompt = (f"🌐 *OFFICIAL TAKEDOWN REQUEST*\n\n"
              f"To Meta Safety Team,\n\n"
              f"I am writing to report the account @{user} for multiple violations of community guidelines.\n"
              f"The identified risks include: {risks}.\n\n"
              f"Please perform a manual review and initiate account termination to protect users.\n\n"
              f"Regards,\nSafety Monitor Bot.")
    
    await query.edit_message_text(prompt, parse_mode="Markdown")

# --- HANDLER ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # Extract username from URL or text
    username = text.split('/')[-2] if "instagram.com" in text else text.replace("@", "")
    context.user_data['username'] = username
    
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        info = (f"👤 *Profile Identified:* @{username}\n"
                f"📈 Followers: {profile.followers} | Posts: {profile.mediacount}\n"
                f"🔗 Status: {'Private' if profile.is_private else 'Public'}")
        kb = [[InlineKeyboardButton("🛡️ Initiate Full Scan", callback_data='start_scan')]]
        await update.message.reply_text(info, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CallbackQueryHandler(start_deep_scan, pattern='start_scan'))
    app.add_handler(CallbackQueryHandler(generate_prompt, pattern='prompt'))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
    
