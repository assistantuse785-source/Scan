import os
import asyncio
import logging
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from moderator import check_content_policy

# Logging - Structured
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# 1. OPTIMIZED INSTALOADER (Memory-Safe)
# save_metadata=False aur compress_json=False is mandatory for Railway
L = instaloader.Instaloader(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    save_metadata=False,
    compress_json=False,
    sleep=True
)

# 2. CORE LOGIC CLASS
class ScannerEngine:
    async def get_deep_info(self, username):
        profile = instaloader.Profile.from_username(L.context, username)
        return {
            "username": profile.username,
            "full_name": profile.full_name,
            "followers": profile.followers,
            "following": profile.followees,
            "posts": profile.mediacount,
            "is_private": profile.is_private,
            "bio": profile.biography,
            "is_verified": profile.is_verified,
            "category": profile.business_category_name
        }

    async def scan_all_posts(self, username):
        profile = instaloader.Profile.from_username(L.context, username)
        violations = []
        count = 0
        
        # Generator for memory efficiency
        for post in profile.get_posts():
            count += 1
            res = check_content_policy(post.caption or "")
            if not res.get("is_safe", True):
                violations.extend(res.get("suggested_reports", []))
            
            # Yield every 10 posts to update Telegram and free up loop
            if count % 10 == 0:
                yield {"status": "scanning", "count": count}
                await asyncio.sleep(2.5) # Crucial delay
        
        yield {"status": "finished", "total": count, "risks": list(set(violations))[:3]}

engine = ScannerEngine()

# 3. HANDLERS
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 *Deep Scanner Active*\nSend username to start analysis.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.replace("@", "").strip()
    msg = await update.message.reply_text("🔍 Fetching A-to-Z Data...")
    
    # Detailed Info
    info = await engine.get_deep_info(username)
    context.user_data['username'] = username
    
    res = (f"👤 *@{info['username']}*\n📛 *Name:* {info['full_name']}\n"
           f"📈 *Followers:* {info['followers']} | *Following:* {info['following']}\n"
           f"📝 *Bio:* {info['bio'][:50]}...\n"
           f"✅ *Verified:* {info['is_verified']}\n\n"
           f"Ready to scan {info['posts']} posts?")
    
    kb = [[InlineKeyboardButton("🛡️ Start Full Deep Scan", callback_data='start_scan')]]
    await msg.edit_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    username = context.user_data.get('username')
    
    if query.data == 'start_scan':
        async for progress in engine.scan_all_posts(username):
            if progress['status'] == 'scanning':
                await query.edit_message_text(f"🚀 Scanning @{username}...\n📊 Posts Processed: {progress['count']}")
            else:
                context.user_data['risks'] = progress['risks']
                res = f"✅ *Scan Finished!*\nTotal: {progress['total']}\nRisks: {', '.join(progress['risks'])}"
                kb = [[InlineKeyboardButton("💀 Make Prompt", callback_data='prompt'),
                       InlineKeyboardButton("💡 View Method", callback_data='method')]]
                await query.edit_message_text(res, reply_markup=InlineKeyboardMarkup(kb))

# (Add your logic for 'prompt' and 'method' callback here)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler('start', start_command))
app.add_handler(CallbackQueryHandler(callback_handler))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
app.run_polling()
  
