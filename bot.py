import os
import time
import logging
import asyncio
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, 
                          CallbackQueryHandler, filters, ContextTypes)
from moderator import check_content_policy

# 1. Logging Setup (Professional Level)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 2. Advanced Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

class InstaloaderManager:
    def __init__(self):
        self.L = instaloader.Instaloader(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            sleep=True
        )
    
    def get_session_file(self, username):
        return os.path.join(SESSION_DIR, f"{username}.session")

manager = InstaloaderManager()

# --- CORE LOGIC ---
async def deep_scan_engine(username, context):
    """Heavy duty analysis engine"""
    profile = instaloader.Profile.from_username(manager.L.context, username)
    violations = []
    posts_count = 0
    
    for post in profile.get_posts():
        posts_count += 1
        # Analysis
        result = check_content_policy(post.caption or "")
        if not result.get("is_safe", True):
            violations.extend(result.get("suggested_reports", []))
            
        # UI Update (Non-blocking)
        if posts_count % 10 == 0:
            yield {"status": "scanning", "count": posts_count}
        
        await asyncio.sleep(1.5) # Anti-ban delay

    yield {"status": "complete", "total": posts_count, "violations": list(set(violations))}

# --- BOT HANDLERS ---
async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.split()[-1].replace("@", "")
    msg = await update.message.reply_text(f"🔍 Initializing deep scan for @{username}...")
    
    try:
        async for progress in deep_scan_engine(username, context):
            if progress['status'] == 'scanning':
                await msg.edit_text(f"🚀 Scanning @{username}...\n📊 Posts Processed: {progress['count']}")
            else:
                context.user_data['results'] = progress
                kb = [
                    [InlineKeyboardButton("💀 Make Takedown Prompt", callback_data=f'prompt_{username}')],
                    [InlineKeyboardButton("⚖️ View Method", callback_data=f'method_{username}')]
                ]
                await msg.edit_text(f"✅ Scan Complete!\nTotal: {progress['total']}\nRisks: {len(progress['violations'])}", 
                                   reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        await msg.edit_text(f"❌ Critical Error: {str(e)}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, user = query.data.split('_')
    
    if action == 'prompt':
        risks = ", ".join(context.user_data['results']['violations'][:3])
        text = f"💀 *CRITICAL TAKEDOWN REQUEST*\n\nUser: @{user}\nViolations: {risks}\nAction: Termination Required."
        await query.message.reply_text(text, parse_mode="Markdown")
    elif action == 'method':
        await query.message.reply_text("💡 *Methodology:*\nFollow strict reporting guidelines. Ensure report timing is spread out.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('scan', scan_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling()
    
