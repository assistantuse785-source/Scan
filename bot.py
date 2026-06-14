import os
import asyncio
import logging
import time
import gc
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from moderator import check_content_policy

# Logging & Config
logging.basicConfig(level=logging.INFO)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# Optimized Instaloader (Memory-Safe)
L = instaloader.Instaloader(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    save_metadata=False, compress_json=False, sleep=True
)

def get_session_path(u): return os.path.join(SESSION_DIR, f"{u}.session")

# --- CORE SCAN ENGINE ---
async def start_deep_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    username = context.user_data.get('username')
    
    # 1. Estimate Time (2.5s per post for safety)
    profile = instaloader.Profile.from_username(L.context, username)
    total_posts = profile.mediacount
    est_sec = total_posts * 2.5
    msg = await query.edit_message_text(f"⏳ *Estimating:* {int(est_sec//60)}m {int(est_sec%60)}s for {total_posts} posts.\n🚀 Scanning started...")
    
    start_time = time.time()
    violations, count = [], 0
    
    # 2. Scanning Loop
    for post in profile.get_posts():
        count += 1
        res = check_content_policy(post.caption or "")
        if not res.get("is_safe", True):
            violations.extend(res.get("suggested_reports", []))
        
        if count % 5 == 0:
            elapsed = time.time() - start_time
            rem = max(0, est_sec - elapsed)
            await msg.edit_text(f"🚀 *Scanning @{username}*\n📊 {count}/{total_posts} posts done\n⏳ Left: {int(rem//60)}m {int(rem%60)}s")
            await asyncio.sleep(2.5)
            gc.collect() # RAM Clear

    # 3. Final Report
    context.user_data['risks'] = list(set(violations))
    res = f"✅ *Scan Complete!*\n📦 {count} posts checked in {int((time.time()-start_time)//60)}m.\n⚠️ Risks Found: {len(context.user_data['risks'])}"
    kb = [[InlineKeyboardButton("💀 Make Prompt", callback_data='prompt'),
           InlineKeyboardButton("💡 View Method", callback_data='method')]]
    await msg.edit_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- HANDLERS ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.replace("@", "").split('/')[0].strip()
    context.user_data['username'] = username
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        info = f"👤 *@{username}*\n📈 Followers: {profile.followers}\n🖼️ Posts: {profile.mediacount}"
        kb = [[InlineKeyboardButton("🛡️ Start Full Deep Scan", callback_data='start_scan')]]
        await update.message.reply_text(info, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'start_scan': await start_deep_scan(update, context)
    elif query.data == 'prompt':
        risks = ", ".join(context.user_data.get('risks', ['Spam']))
        await query.message.reply_text(f"💀 *Takedown Prompt*\n\n`Account @{context.user_data['username']} violates safety: {risks}. Terminate.`", parse_mode="Markdown")
    elif query.data == 'method':
        await query.message.reply_text("💡 *Method:* Report post-by-post using the prompt provided.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', lambda u, c: u.message.reply_text("Send username to scan.")))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
    
